#include "PowerMonitor.h"
#include "PowerTelemetry.h"
#include "SensorDecoders.h"
#include <Mesh.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <memory>
#include <new>
#include <helpers/SensorManager.h>
#if ENV_INCLUDE_INA260
#error "PowerMonitor requires INA260 disabled: INA219 load monitor owns address 0x41"
#endif
#if ENV_INCLUDE_INA219
#error "PowerMonitor owns both INA219 devices; disable the duplicate stock INA219 driver"
#endif
using namespace Adafruit_LittleFS_Namespace;

namespace pm {
namespace {
constexpr uint8_t SOLAR=0x40, LOAD=0x41, MCP=0x18, INA_CFG=0x00, INA_SHUNT=0x01, INA_BUS=0x02;
// INA219 32V bus, +/-320mV shunt range, 12bit bus+shunt continuous ADC.
constexpr uint16_t INA_CONTINUOUS=0x399F;
constexpr uint32_t SNAP_MAGIC=0x504D3135UL;
struct Snapshot {
  uint32_t magic;
  uint16_t version, spare;
  uint32_t sequence, utc_day;
  double total_solar, total_load, day_solar, day_load;
  SolarHistory::State solar_history;
  uint32_t crc;
};
uint32_t crc32fnv(const uint8_t* p, size_t n) {
  uint32_t h=2166136261UL;
  for(size_t i=0;i<n;i++) { h ^= p[i]; h *= 16777619UL; }
  return h;
}
const char* slotName(unsigned slot) {
  return slot ? "/pm_energy_b.bin" : "/pm_energy_a.bin";
}
}
bool PowerMonitor::probe(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission()==0;
}
bool PowerMonitor::read16(uint8_t a,uint8_t reg,uint16_t& out) {
  Wire.beginTransmission(a); Wire.write(reg);
  if(Wire.endTransmission(false)!=0) return false;
  if(Wire.requestFrom((int)a,2)!=2) return false;
  const int hi=Wire.read(), lo=Wire.read();
  if(hi<0||lo<0)return false;
  out=(uint16_t)(((unsigned)hi<<8)|(unsigned)lo);
  return true;
}
bool PowerMonitor::write16(uint8_t a,uint8_t reg,uint16_t v) {
  Wire.beginTransmission(a);Wire.write(reg);
  Wire.write((uint8_t)(v>>8));Wire.write((uint8_t)v);
  return Wire.endTransmission()==0;
}
void PowerMonitor::begin(bool allow_checkpoint) {
  checkpoint_enabled_=allow_checkpoint;
  // Shared I2C bus is initialized by MeshCore sensors.begin() before us.
  solar_.address=SOLAR; solar_.shunt_ohms=PM_SOLAR_SHUNT_OHMS;
  solar_.sign=PM_SOLAR_SIGN<0?-1:1;
  load_.address=LOAD;load_.shunt_ohms=PM_LOAD_SHUNT_OHMS;
  load_.sign=PM_LOAD_SIGN<0?-1:1;
  solar_.detected=probe(SOLAR)&&write16(SOLAR,INA_CFG,INA_CONTINUOUS);
  load_.detected=probe(LOAD)&&write16(LOAD,INA_CFG,INA_CONTINUOUS);
  detectMcp();
  if(mcp_found_) readMcp();
  const uint32_t now=millis();
  next_sample_=next_temperature_=next_checkpoint_=next_probe_=now;
  if(checkpoint_enabled_)restore();
}
void PowerMonitor::sample(Channel& channel,uint32_t utc) {
  channel.valid=false;
  if(!channel.detected){channel.counter.gap(millis());return;}
  uint16_t raw_shunt=0,raw_bus=0;
  const bool ok=read16(channel.address,INA_SHUNT,raw_shunt)
             &&read16(channel.address,INA_BUS,raw_bus);
  const uint32_t now=millis();
  InaReading reading{};
  if(!ok || !decodeIna219(raw_shunt,raw_bus,channel.shunt_ohms,channel.sign,reading)) {
    channel.failures++;channel.counter.gap(now);return;
  }
  channel.volts=reading.volts;
  channel.milliamps=reading.milliamps;
  channel.milliwatts=reading.milliwatts;
  channel.math_overflow=reading.math_overflow;
  channel.valid=true;
  const double old=channel.counter.total_mwh;
  const uint64_t old_covered=channel.counter.covered_ms;
  channel.counter.add(now,channel.milliwatts);
  const double delta=channel.counter.total_mwh-old;
  if(&channel==&solar_) {
    today_solar_+=delta;
    history_.add(utc,delta,(uint32_t)(channel.counter.covered_ms-old_covered));
  } else today_load_+=delta;
}
void PowerMonitor::detectMcp() {
  mcp_temperature_=NAN;mcp_found_=false;
  mcp_ack_=probe(MCP);mcp_manufacturer_=mcp_device_=0;
  if(!mcp_ack_ || !read16(MCP,0x06,mcp_manufacturer_)
      || !read16(MCP,0x07,mcp_device_) || !isMcp9808(mcp_manufacturer_,mcp_device_))return;
  uint16_t config=0;
  // Wake a confirmed MCP9808 while preserving its other configuration bits.
  mcp_found_=read16(MCP,0x01,config)&&write16(MCP,0x01,config&~0x0100U);
}
void PowerMonitor::readMcp() {
  float temperature=NAN;
  if(!mcp_found_||!read16(MCP,0x05,mcp_raw_)||!decodeMcp9808(mcp_raw_,temperature)) {
    mcp_temperature_=NAN;return;
  }
  mcp_temperature_=temperature;
}
void PowerMonitor::summary(char* out,size_t cap) const {
  snprintf(out,cap,"S=%.4f/%.4fmWh L=%.4f/%.4fmWh V=%.2f/%.2f I=%.1f/%.1fmA",
      solar_.counter.window_mwh,solar_.counter.total_mwh,
      load_.counter.window_mwh,load_.counter.total_mwh,
      solar_.volts,load_.volts,solar_.milliamps,load_.milliamps);
}
void PowerMonitor::appendTelemetry(CayenneLPP& lpp,uint8_t permissions) const {
  if(!(permissions&TELEM_PERM_ENVIRONMENT))return;
  // Emit the requested solar histories first, within the existing bounded
  // telemetry buffer. Ordinary sensors append afterwards using their checks.
  if(utc_>=1700000000UL) {
    appendSolarReading(lpp,110,history_.rolling(utc_,900));
    appendSolarReading(lpp,111,history_.rolling(utc_,3600));
    appendSolarReading(lpp,112,history_.today(utc_));
    appendSolarReading(lpp,113,history_.previous(utc_));
  }
  const Channel* channels[]={&solar_,&load_};
  for(unsigned i=0;i<2;i++) {
    const auto& c=*channels[i];const uint8_t id=100+i;
    if(c.valid) {
      appendInstantReading(lpp,id,c.volts,c.milliamps,c.milliwatts,i==1);
    }
    if((c.counter.good_samples || c.counter.total_mwh!=0) && c.counter.total_mwh>=0 && c.counter.total_mwh<4294967000000.0)
      lpp.addEnergy(id,(float)(c.counter.total_mwh/1000000.0));
  }
  if(isfinite(mcp_temperature_))lpp.addTemperature(102,mcp_temperature_);
}
void PowerMonitor::poll(uint32_t now,uint32_t utc) {
  utc_=utc;
  if((uint32_t)(now-next_probe_)>=5000UL) {
    next_probe_=now;
    if(!solar_.detected)solar_.detected=probe(SOLAR)&&write16(SOLAR,INA_CFG,INA_CONTINUOUS);
    if(!load_.detected)load_.detected=probe(LOAD)&&write16(LOAD,INA_CFG,INA_CONTINUOUS);
    if(!mcp_found_){detectMcp();if(mcp_found_)readMcp();}
  }
  const uint32_t old_day=history_.state.day;
  history_.advance(utc);
  if(utc>=1700000000UL) {
    const uint32_t day=utc/86400UL;
    if(utc_day_ && day!=utc_day_){today_solar_=0;today_load_=0;}
    utc_day_=day;
  }
  if((uint32_t)(now-next_sample_)>=PM_SAMPLE_MS) {
    next_sample_=now;
    sample(solar_,utc);sample(load_,utc);
  }
  if((uint32_t)(now-next_temperature_)>=PM_TEMPERATURE_MS) {
    next_temperature_=now;if(mcp_found_)readMcp();
  }
  if(checkpoint_enabled_&&((uint32_t)(now-next_checkpoint_)>=PM_CHECKPOINT_MS
       || (old_day && old_day!=history_.state.day))) {
    next_checkpoint_=now;save();
  }
}
void PowerMonitor::clear() {
  solar_.counter=Integrator{};load_.counter=Integrator{};
  today_solar_=today_load_=0;history_.clear();
  history_.advance(utc_);
  if(checkpoint_enabled_)save();
}
bool PowerMonitor::handleCommand(const char* c,char* out,size_t cap) {
  if(!strcmp(c,"help")||!strcmp(c,"help pm")) {
    snprintf(out,cap,"PowerMonitor: pm help; pm ota help; ota test (NEW TEST1 firmware marker); pm version. Sensor/energy commands: pm help");return true;
  }
  if(strncmp(c,"pm",2)!=0 || (c[2]&&c[2]!=' '))return false;
  if(!strcmp(c,"pm")||!strcmp(c,"pm status"))summary(out,cap);
  else if(!strcmp(c,"pm sensors"))
    snprintf(out,cap,"solar40:%s load41:%s mcp18:%s T=%.2fC errs=%lu/%lu cov=%u/%u%%",
      solar_.detected?"OK":"MISSING",load_.detected?"OK":"MISSING",
      mcp_found_?"OK":mcp_ack_?"WRONG_ID/IO":"MISSING",mcp_temperature_,
      (unsigned long)solar_.failures,(unsigned long)load_.failures,
      solar_.counter.coverage(),load_.counter.coverage());
  else if(!strcmp(c,"pm day"))
    snprintf(out,cap,"UTCday=%lu solar=%.3fmWh load=%.3fmWh restore=%lu",
      (unsigned long)utc_day_,today_solar_,today_load_,(unsigned long)restores_);
  else if(!strcmp(c,"pm channels"))
    snprintf(out,cap,"100 Solar;101 Battery(+charge/-discharge);102 Temp;110 Solar15m;111 Solar1h;112 TodayUTC;113 YesterdayUTC. Current=A;Analog=signed W;Power=abs W;Generic=mWh");
  else if(!strcmp(c,"pm solar")||!strcmp(c,"pm load")) {
    const bool solar=!strcmp(c,"pm solar");const auto& ch=solar?solar_:load_;
    if(!ch.valid)snprintf(out,cap,"%s INA219 0x%02X: %s; read_errors=%lu. Run pm i2c; check address/wiring.",
      solar?"Solar":"Battery",ch.address,ch.detected?"READ ERROR":"MISSING",(unsigned long)ch.failures);
    else snprintf(out,cap,"%s INA219 0x%02X: %.3fV %.2fmA %.2fmW total=%.3fmWh ADC=OK mathOVF=%u",
      solar?"Solar":"Battery (+charge/-discharge)",ch.address,ch.volts,displayFlow(ch.milliamps,!solar),displayFlow(ch.milliwatts,!solar),ch.counter.total_mwh,ch.math_overflow?1:0);
  }
  else if(!strcmp(c,"pm temp"))
    snprintf(out,cap,"MCP9808 0x18: %s T=%.3fC manufacturer=0x%04X device=0x%04X raw=0x%04X",
      mcp_found_?"IDENTIFIED":mcp_ack_?"WRONG_ID/IO":"MISSING",mcp_temperature_,mcp_manufacturer_,mcp_device_,mcp_raw_);
  else if(!strcmp(c,"pm i2c")) {
    size_t n=(size_t)snprintf(out,cap,"I2C ACK:");
    for(uint8_t a=8;a<0x78 && n+6<cap;a++)if(probe(a))n+=(size_t)snprintf(out+n,cap-n," %02X",a);
  }
  else if(!strcmp(c,"pm solar 15m")||!strcmp(c,"pm solar 1h")
       ||!strcmp(c,"pm solar today")||!strcmp(c,"pm solar yesterday")) {
    SolarHistory::Reading reading{};
    if(!strcmp(c,"pm solar 15m"))reading=history_.rolling(utc_,900);
    else if(!strcmp(c,"pm solar 1h"))reading=history_.rolling(utc_,3600);
    else if(!strcmp(c,"pm solar today"))reading=history_.today(utc_);
    else reading=history_.previous(utc_);
    snprintf(out,cap,"%s %.3fmWh avg=%.3fW cov=%u%% UTC checkpoint=%s",
      c+3,reading.mwh,reading.watts(),reading.coverage(),checkpoint_ok_?"OK":"unavailable");
  }
  else if(!strcmp(c,"pm reset YES")){clear();snprintf(out,cap,"OK energy counters cleared");}
  else if(!strcmp(c,"pm version"))
    snprintf(out,cap,"power-monitor %s git %s",PM_VERSION,PM_SOURCE_SHA);
  else if(!strcmp(c,"pm info"))
    snprintf(out,cap,"v=%s 20ms solar=0x40 load=0x41 MCP=0x18 R=%.3f/%.3f",
      PM_VERSION,(double)solar_.shunt_ohms,(double)load_.shunt_ohms);
  else snprintf(out,cap,"pm channels|solar|load|temp|i2c|sensors|version|status|day; solar 15m|1h|today|yesterday; pm ota help; ota test; reset YES (USB only)");
  return true;
}
bool PowerMonitor::restore() {
  std::unique_ptr<Snapshot> storage(new(std::nothrow) Snapshot{});
  if(!storage)return false;
  bool valid=false;
  for(unsigned i=0;i<2;i++) {
    File f=InternalFS.open(slotName(i),FILE_O_READ);
    if(!f)continue;
    Snapshot& s=*storage;
    const int n=f.read((uint8_t*)&s,sizeof(s));f.close();
    if(n!=(int)sizeof(s)||s.magic!=SNAP_MAGIC||s.version!=3)continue;
    if(crc32fnv((const uint8_t*)&s,offsetof(Snapshot,crc))!=s.crc)continue;
    if(!valid||(int32_t)(s.sequence-sequence_)>0) {
      solar_.counter.total_mwh=s.total_solar;load_.counter.total_mwh=s.total_load;
      today_solar_=s.day_solar;today_load_=s.day_load;
      history_.state=s.solar_history;
      utc_day_=s.utc_day;sequence_=s.sequence;valid=true;
    }
  }
  if(!valid)return false;
  restores_++;checkpoint_ok_=true;return true;
}
bool PowerMonitor::save() {
  if(!checkpoint_enabled_)return false;
  checkpoint_ok_=false;
  std::unique_ptr<Snapshot> storage(new(std::nothrow) Snapshot{});
  if(!storage)return false;
  Snapshot& s=*storage;
  s.magic=SNAP_MAGIC;s.version=3;s.sequence=sequence_+1;s.utc_day=utc_day_;
  s.total_solar=solar_.counter.total_mwh;s.total_load=load_.counter.total_mwh;
  s.day_solar=today_solar_;s.day_load=today_load_;
  s.solar_history=history_.state;
  s.crc=crc32fnv((const uint8_t*)&s,offsetof(Snapshot,crc));
  File f=InternalFS.open(slotName(s.sequence&1U),FILE_O_WRITE);
  if(!f)return false;
  const size_t bytes=f.write((const uint8_t*)&s,sizeof(s));f.close();
  if(bytes!=sizeof(s))return false;
  sequence_=s.sequence;checkpoint_ok_=true;return true;
}
}
