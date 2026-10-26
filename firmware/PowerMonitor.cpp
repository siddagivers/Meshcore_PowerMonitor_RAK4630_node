#include "PowerMonitor.h"
#include <Mesh.h>
#include <Adafruit_LittleFS.h>
#include <InternalFileSystem.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
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
  mcp_found_=probe(MCP);
  if(mcp_found_) readMcp();
  const uint32_t now=millis();
  next_sample_=next_temperature_=next_report_=next_checkpoint_=now;
  if(checkpoint_enabled_)restore();
}
void PowerMonitor::sample(Channel& channel) {
  if(!channel.detected){channel.counter.gap(millis());return;}
  uint16_t raw_shunt=0,raw_bus=0;
  const bool ok=read16(channel.address,INA_SHUNT,raw_shunt)
             &&read16(channel.address,INA_BUS,raw_bus);
  const uint32_t now=millis();
  // Overflow bit is 1; bit 2 (conversion ready) can be 0 in normal operation.
  if(!ok || (raw_bus&0x02U) || channel.shunt_ohms<=0) {
    channel.failures++;channel.counter.gap(now);return;
  }
  const float shunt_v=(float)(int16_t)raw_shunt*0.00001f;
  const float bus_v=(float)((raw_bus>>3)&0x1FFFU)*0.004f;
  channel.volts=bus_v+shunt_v;
  channel.milliamps=1000.0f*shunt_v/channel.shunt_ohms*channel.sign;
  channel.milliwatts=channel.volts*channel.milliamps;
  const double old=channel.counter.total_mwh;
  channel.counter.add(now,channel.milliwatts);
  const double delta=channel.counter.total_mwh-old;
  if(&channel==&solar_)today_solar_+=delta;else today_load_+=delta;
}
void PowerMonitor::readMcp() {
  uint16_t raw=0;
  if(!mcp_found_||!read16(MCP,0x05,raw)){mcp_temperature_=NAN;return;}
  float t=(float)(raw&0x0FFF)/16.0f;
  if(raw&0x1000)t-=256.0f;
  mcp_temperature_=t;
}
void PowerMonitor::summary(char* out,size_t cap,bool compact) const {
  if(compact)
    snprintf(out,cap,"PM15 S=%.3fmWh L=%.3fmWh D=%.2f/%.2f T=%.1fC V=%.2f/%.2f C=%u/%u%%",
      solar_.counter.window_mwh,load_.counter.window_mwh,
      today_solar_,today_load_,mcp_temperature_,solar_.volts,load_.volts,
      solar_.counter.coverage(),load_.counter.coverage());
  else
    snprintf(out,cap,"S=%.4f/%.4fmWh L=%.4f/%.4fmWh V=%.2f/%.2f I=%.1f/%.1fmA",
      solar_.counter.window_mwh,solar_.counter.total_mwh,
      load_.counter.window_mwh,load_.counter.total_mwh,
      solar_.volts,load_.volts,solar_.milliamps,load_.milliamps);
}
void PowerMonitor::sendReport(uint32_t now,Publisher p) {
  char buf[150];summary(buf,sizeof(buf),true);
  if(p&&p(buf)) {
    next_report_=now;
    solar_.counter.resetWindow();load_.counter.resetWindow();
  }
  last_retry_=now;
}
void PowerMonitor::poll(uint32_t now,uint32_t utc,Publisher publisher) {
  if((uint32_t)(now-next_sample_)>=PM_SAMPLE_MS) {
    next_sample_=now;
    sample(solar_);sample(load_);
  }
  if((uint32_t)(now-next_temperature_)>=PM_TEMPERATURE_MS) {
    next_temperature_=now;if(mcp_found_)readMcp();
  }
  if(utc>=1700000000UL) {
    const uint32_t day=utc/86400UL;
    if(!utc_day_) utc_day_=day;
    else if(day>utc_day_) {
      utc_day_=day;today_solar_=0;today_load_=0;
      if(checkpoint_enabled_)save();
    }
  }
  if(checkpoint_enabled_&&(uint32_t)(now-next_checkpoint_)>=PM_REPORT_MS) {
    next_checkpoint_=now;save();
  }
  if(auto_report_&&(uint32_t)(now-next_report_)>=PM_REPORT_MS
      &&(uint32_t)(now-last_retry_)>=30000UL) sendReport(now,publisher);
}
void PowerMonitor::clear() {
  solar_.counter=Integrator{};load_.counter=Integrator{};
  today_solar_=today_load_=0;next_report_=millis();
  if(checkpoint_enabled_)save();
}
bool PowerMonitor::handleCommand(const char* c,char* out,size_t cap) {
  if(strncmp(c,"pm",2)!=0 || (c[2]&&c[2]!=' '))return false;
  if(!strcmp(c,"pm")||!strcmp(c,"pm status"))summary(out,cap,false);
  else if(!strcmp(c,"pm sensors"))
    snprintf(out,cap,"solar40:%s load41:%s mcp18:%s T=%.2fC errs=%lu/%lu cov=%u/%u%%",
      solar_.detected?"OK":"MISSING",load_.detected?"OK":"MISSING",
      mcp_found_?"OK":"MISSING",mcp_temperature_,
      (unsigned long)solar_.failures,(unsigned long)load_.failures,
      solar_.counter.coverage(),load_.counter.coverage());
  else if(!strcmp(c,"pm day"))
    snprintf(out,cap,"UTCday=%lu solar=%.3fmWh load=%.3fmWh restore=%lu",
      (unsigned long)utc_day_,today_solar_,today_load_,(unsigned long)restores_);
  else if(!strcmp(c,"pm report"))summary(out,cap,true);
  else if(!strcmp(c,"pm report on")){auto_report_=true;snprintf(out,cap,"OK reporting on");}
  else if(!strcmp(c,"pm report off")){auto_report_=false;snprintf(out,cap,"OK reporting off");}
  else if(!strcmp(c,"pm reset YES")){clear();snprintf(out,cap,"OK energy counters cleared");}
  else if(!strcmp(c,"pm version"))
    snprintf(out,cap,"power-monitor %s git %s",PM_VERSION,PM_SOURCE_SHA);
  else if(!strcmp(c,"pm info"))
    snprintf(out,cap,"v=%s 20ms solar=0x40 load=0x41 MCP=0x18 R=%.3f/%.3f",
      PM_VERSION,(double)solar_.shunt_ohms,(double)load_.shunt_ohms);
  else snprintf(out,cap,"pm status|sensors|day|report|version|info|report on|report off|reset YES");
  return true;
}
bool PowerMonitor::restore() {
  Snapshot best{};bool valid=false;
  for(unsigned i=0;i<2;i++) {
    File f=InternalFS.open(slotName(i),FILE_O_READ);
    if(!f)continue;
    Snapshot s{};
    const int n=f.read((uint8_t*)&s,sizeof(s));f.close();
    if(n!=(int)sizeof(s)||s.magic!=SNAP_MAGIC||s.version!=2)continue;
    if(crc32fnv((const uint8_t*)&s,offsetof(Snapshot,crc))!=s.crc)continue;
    if(!valid||(int32_t)(s.sequence-best.sequence)>0){best=s;valid=true;}
  }
  if(!valid)return false;
  solar_.counter.total_mwh=best.total_solar;
  load_.counter.total_mwh=best.total_load;
  today_solar_=best.day_solar;today_load_=best.day_load;
  utc_day_=best.utc_day;sequence_=best.sequence;restores_++;return true;
}
bool PowerMonitor::save() {
  if(!checkpoint_enabled_)return false;
  Snapshot s{};
  s.magic=SNAP_MAGIC;s.version=2;s.sequence=++sequence_;s.utc_day=utc_day_;
  s.total_solar=solar_.counter.total_mwh;s.total_load=load_.counter.total_mwh;
  s.day_solar=today_solar_;s.day_load=today_load_;
  s.crc=crc32fnv((const uint8_t*)&s,offsetof(Snapshot,crc));
  File f=InternalFS.open(slotName(s.sequence&1U),FILE_O_WRITE);
  if(!f)return false;
  const size_t bytes=f.write((const uint8_t*)&s,sizeof(s));f.close();
  return bytes==sizeof(s);
}
}
