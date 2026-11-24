#include "PowerMonitor.h"
#include "PowerMonitorHelp.h"
#include "InaEnable.h"
#include "TelemetryPage.h"
#include "SensorRefresh.h"
#include <InternalFileSystem.h>
#include <Mesh.h>
#include <helpers/SensorManager.h>
#include <memory>
#include <new>
#include <stdio.h>
#include <string.h>
using namespace Adafruit_LittleFS_Namespace;
namespace pm {
namespace {
constexpr float SHUNT[2]={0.100f,0.100f};
#if PM_SIDOROVO
constexpr uint8_t ADDRESS[2]={0x40,0x41}; // solar, battery
#else
constexpr uint8_t ADDRESS[2]={0x41,0x40}; // solar, battery
#endif
constexpr uint16_t ADC_CONT=0xBB69,ADC_ONCE=0x3B69; // 1052us VBUS/shunt, averaging 4
bool readReg(uint8_t address,uint8_t reg,uint32_t& result,unsigned bytes){
  Wire.beginTransmission(address);Wire.write(reg);
  if(Wire.endTransmission(false)!=0 || Wire.requestFrom((int)address,(int)bytes)!=(int)bytes)return false;
  result=0;for(unsigned i=0;i<bytes;i++){int b=Wire.read();if(b<0)return false;result=(result<<8)|(uint8_t)b;}return true;
}
bool writeReg(uint8_t address,uint8_t reg,uint16_t value){
  Wire.beginTransmission(address);Wire.write(reg);Wire.write((uint8_t)(value>>8));Wire.write((uint8_t)value);return Wire.endTransmission()==0;
}
bool readMcpReg(uint8_t address,uint8_t reg,uint16_t& result){
  uint32_t value=0;if(!readReg(address,reg,value,2))return false;
  result=(uint16_t)value;return true;
}
uint32_t crc(const void* data,size_t size){const auto* p=(const uint8_t*)data;uint32_t c=2166136261;
  while(size--){c^=*p++;c*=16777619;}return c;}
struct State {uint32_t magic,sequence;Ina228History histories[2];uint32_t check;};
struct LegacyHistory {Ina228History::Bucket buckets[121];uint32_t day,lastUtc;Ina228History::DayMean today;};
struct LegacyState {uint32_t magic,sequence;LegacyHistory histories[2];uint32_t check;};
const char* path(unsigned slot){
#if PM_SIDOROVO
  return slot?"/pm228-sw.b":"/pm228-sw.a";
#else
  return slot?"/pm228.b":"/pm228.a";
#endif
}
void emit(CayenneLPP& lpp,uint8_t id,float v,float a,float w){
  if(isfinite(v)&&v>=0&&v<=327.67f)lpp.addVoltage(id,v);
  if(isfinite(a)&&a>=-32.768f&&a<=32.767f)lpp.addCurrent(id,a);
  // Cayenne native power is unsigned/integer W: analog retains signed sub-W power.
  if(isfinite(w)&&w>=-327.68f&&w<=327.67f)lpp.addAnalogInput(id,w);
}
}
bool PowerMonitor::configure(unsigned i){
  auto& c=channel_[i];c.valid=false;c.pending=false;c.last=0;
  c.triggered=millis();c.next=c.triggered;
  uint32_t maker,device;
  if(!readReg(ADDRESS[i],0x3e,maker,2)||maker!=0x5449
     ||!readReg(ADDRESS[i],0x3f,device,2)||(device>>4)!=0x228)return false;
  // Explicit normal shunt range (+/-163.84mV). Derive signed current from raw
  // shunt voltage so calibration/current accumulator registers are not required.
  return writeReg(ADDRESS[i],0,0)&&writeReg(ADDRESS[i],1,inaEnabled_&&channel_[i].continuous?ADC_CONT:0);
}
bool PowerMonitor::settings(bool write){
  if(!filesystem_)return false;
  if(write){
    if(InternalFS.exists("/pm228.mode")&&!InternalFS.remove("/pm228.mode"))return false;
    File f=InternalFS.open("/pm228.mode",FILE_O_WRITE);uint8_t value=batteryContinuous_?1:0;
    bool ok=f&&f.write(&value,1)==1;f.close();return ok;
  }
  File f=InternalFS.open("/pm228.mode",FILE_O_READ);if(!f)return false;
  int value=f.read();f.close();if(value!=0&&value!=1)return false;batteryContinuous_=value==1;return true;
}
void PowerMonitor::begin(bool fs){
  filesystem_=fs;inaEnabled_=loadInaEnabled(fs);settings(false);historySaved_=restore();
  channel_[0].continuous=false;channel_[1].continuous=batteryContinuous_;
  for(unsigned i=0;i<2;i++)channel_[i].detected=configure(i);
  mcp_.tick(millis(),readMcpReg,writeReg);
  checkpoint_=millis();
}
void PowerMonitor::sample(unsigned i,uint32_t now){
  auto& c=channel_[i];const uint8_t address=ADDRESS[i];
  const uint32_t interval=i?300000UL:600000UL;
  if(!c.detected)return;
  // Bound polling even when the conversion-ready flag never arrives.
  if((int32_t)(now-c.next)<0)return;
  c.next=now+20;
  if(!c.continuous && !c.pending){
    c.valid=false;
    if(!writeReg(address,1,ADC_ONCE)){c.errors++;c.detected=false;return;}
    c.pending=true;c.triggered=now;return;
  }
  uint32_t diag;
  if(!readReg(address,0x0b,diag,2)){c.errors++;c.valid=false;c.pending=false;c.detected=false;return;}
  if(!(diag&2)){
    if((c.pending||c.continuous) && (uint32_t)(now-c.triggered)>200){c.errors++;c.pending=false;c.valid=false;c.detected=false;writeReg(address,1,0);}
    return;
  }
  uint32_t shunt,bus;
  if(!readReg(address,4,shunt,3)||!readReg(address,5,bus,3)
     ||!ina228Decode(shunt,bus,SHUNT[i],i==1,c.v,c.a,c.w)){
    c.errors++;c.valid=false;c.pending=false;c.detected=false;writeReg(address,1,0);return;
  }
  c.valid=true;
  // No extrapolation across unsampled gaps. A single-shot contributes only its
  // observation interval; displayed histories are averages of measured time.
  uint32_t dt=c.continuous&&c.last?now-c.last:20;
  if(dt>200)dt=20;
  history_[i].add(utc_,c.v,c.a,c.w,dt);
  c.last=now;c.pending=false;
  c.triggered=now;
  bool was=c.continuous;if(i==0)c.solarDecision(now);
  if(was!=c.continuous&&!writeReg(address,1,c.continuous?ADC_CONT:0)){
    c.errors++;c.valid=false;c.detected=false;return;
  }
  c.next=now+(c.continuous?20:interval);
}
void PowerMonitor::poll(uint32_t now,uint32_t utc){
  utc_=utc;
  mcp_.tick(now,readMcpReg,writeReg);
  const uint32_t oldDay=history_[0].day;
  for(auto& h:history_)h.advance(utc);
  if(filesystem_&&((uint32_t)(now-checkpoint_)>=900000 || (oldDay&&oldDay!=history_[0].day))){checkpoint_=now;historySaved_=save();}
  if(!inaEnabled_)return;
  if((uint32_t)(now-probe_)>=10000){probe_=now;
    for(unsigned i=0;i<2;i++)if(!channel_[i].detected){channel_[i].detected=configure(i);channel_[i].pending=false;channel_[i].next=now;}}
  sample(0,now);sample(1,now);
}
void PowerMonitor::appendTelemetry(CayenneLPP& lpp,uint8_t permissions)const{
  appendTelemetry(lpp,permissions,telemetry_page.page);
}
void PowerMonitor::refreshTelemetry(uint32_t utc){
  utc_=utc;for(auto& h:history_)h.advance(utc);
  mcp_.requestFresh();mcp_.tick(millis(),readMcpReg,writeReg);
  if(!inaEnabled_)return;
  for(unsigned i=0;i<2;i++){channel_[i].valid=false;channel_[i].next=millis();sample(i,millis());}
  // Single-shot ADCs convert concurrently; never wait in the radio loop.
  delay(20);
  for(unsigned i=0;i<2;i++)sample(i,millis());
}
void PowerMonitor::appendTelemetry(CayenneLPP& lpp,uint8_t permissions,TelemetryPage::Page page)const{
  if(!(permissions&TELEM_PERM_ENVIRONMENT))return;
  if(page!=TelemetryPage::POWER&&mcp_.valid)lpp.addTemperature(102,mcp_.temperature);
  if(page==TelemetryPage::ENVIRONMENT)return;
  // Reserve room for channel 1 and the environmental channels on a
  // combined reply. The dedicated power page still includes diagnostics.
  const bool diagnostics=page!=TelemetryPage::COMBINED;
  const unsigned windows[]={300,900,3600,0};
  for(unsigned i=0;i<2;i++){
    const auto& c=channel_[i];
    if(c.valid){
      emit(lpp,100+i,c.v,c.a,c.w);
      if(diagnostics)lpp.addGenericSensor(100+i,(millis()-c.last)/1000);
    }
    if(page==TelemetryPage::LIVE)continue;
    for(unsigned j=0;j<4;j++){
      auto mean=j==3?history_[i].yesterday(utc_):history_[i].get(utc_,windows[j]);uint8_t id=110+i*10+j;
      if(mean.ms)emit(lpp,id,mean.v(),mean.a(),mean.w());
      if(diagnostics){
        uint32_t span=windows[j]?windows[j]*1000UL:86400000UL;
        lpp.addPercentage(id,fminf(100,mean.ms*100.0f/span));
      }
    }
  }
}
bool PowerMonitor::handleCommand(const char* command,char* out,size_t cap){
  if(powerHelp(command,out,cap,true))return true;
  if(freshBusy()&&strncmp(command,"pm",2)==0&&strcmp(command,"pm version")&&strcmp(command,"pm diag")){
    snprintf(out,cap,"Sensor refresh busy (%s); MeshCore remains active; retry later",freshStatus());return true;
  }
  if(!strcmp(command,"pm ina off")||!strcmp(command,"pm ina on")){
    inaEnabled_=!strcmp(command,"pm ina on");bool ack=true;
    for(unsigned i=0;i<2;i++){
      auto& c=channel_[i];
      if(inaEnabled_)c.detected=configure(i);
      else if(c.detected&&!writeReg(ADDRESS[i],1,0))ack=false;
      c.valid=false;c.pending=false;c.last=0;c.quiet=0;c.next=millis();
    }
    snprintf(out,cap,"INA %s; setting %s; shutdown %s",inaEnabled_?"enabled":"disabled (no polling)",saveInaEnabled(filesystem_,inaEnabled_)?"saved":"NOT saved",ack?"OK/not needed":"NOT acknowledged");return true;
  }
  if(strncmp(command,"pm",2)|| (command[2]&&command[2]!=' '))return false;
  if(!strcmp(command,"pm version"))snprintf(out,cap,"power-monitor %s git %s INA228",PM_VERSION,PM_SOURCE_SHA);
  else if(!strcmp(command,"pm channels"))snprintf(out,cap,"100 Solar;101 Battery;102 MCP9808;110-113 Solar 5m/15m/1h/yesterdayUTC;120-123 Battery same. Analog=signed W;V,A means;%%=coverage");
  else if(!strcmp(command,"pm diag"))snprintf(out,cap,"I2C timeouts=%lu last=%s; uptime=%lus; refresh=%s",(unsigned long)pmWireTimeoutCount(),pmWireLastTimeoutStage(),(unsigned long)(millis()/1000),freshStatus());
  else if(!strcmp(command,"pm sensors")||!strcmp(command,"pm status"))snprintf(out,cap,"INA228 solar%02X:%s battery%02X:%s; mcp18:%s; errors=%lu/%lu/%lu; history=%s",
    (unsigned)ADDRESS[0],!inaEnabled_?"DISABLED":channel_[0].detected?"OK":"MISSING",(unsigned)ADDRESS[1],!inaEnabled_?"DISABLED":channel_[1].detected?"OK":"MISSING",mcp_.valid?"OK":mcp_.detected?"WARMING":"MISSING",(unsigned long)channel_[0].errors,(unsigned long)channel_[1].errors,(unsigned long)mcp_.errors,historySaved_?"saved":"not saved yet/FS error");
  else if(!strcmp(command,"pm temp"))snprintf(out,cap,"MCP9808 0x18: %s T=%.4fC manufacturer=0x%04X device=0x%04X raw=0x%04X age=%lus",
    mcp_.valid?"OK":mcp_.detected?"WARMING":"MISSING",mcp_.temperature,mcp_.manufacturer,mcp_.device,mcp_.raw,(unsigned long)((millis()-mcp_.last)/1000));
  else if(!strcmp(command,"pm battery continuous on")||!strcmp(command,"pm battery continuous off")){
    if(!inaEnabled_){snprintf(out,cap,"INA disabled: run pm ina on first");return true;}
    bool desired=!strcmp(command,"pm battery continuous on");
    if(!writeReg(ADDRESS[1],1,desired?ADC_CONT:0)){snprintf(out,cap,"Err INA228 write");return true;}
    batteryContinuous_=desired;channel_[1].continuous=desired;channel_[1].pending=false;channel_[1].last=0;channel_[1].next=millis();channel_[1].triggered=millis();
    snprintf(out,cap,"OK battery %s; setting %s",desired?"continuous":"5-minute single shots",settings(true)?"saved":"not saved");
  }else if(!strcmp(command,"pm solar")||!strcmp(command,"pm load")){
    if(!inaEnabled_){snprintf(out,cap,"INA disabled; run pm ina on to resume readings");return true;}
    unsigned i=!strcmp(command,"pm load");const auto& c=channel_[i];
    if(c.valid)snprintf(out,cap,"%s INA228: %.4fV %.6fA %.6fW age=%lus %s",i?"Battery +charge/-discharge":"Solar",c.v,c.a,c.w,(unsigned long)((millis()-c.last)/1000),c.continuous?"continuous":"single shot");
    else snprintf(out,cap,"No valid INA228 observation");
  }else if(!strncmp(command,"pm history ",11)){
    char sensor[12],window[8],extra;unsigned seconds;
    if(sscanf(command+11,"%11s %7s %c",sensor,window,&extra)!=2){snprintf(out,cap,"pm history solar/battery 5m/15m/1h/day/prevday");return true;}
    unsigned i=!strcmp(sensor,"battery");
    if(strcmp(sensor,"solar")&&strcmp(sensor,"battery")){snprintf(out,cap,"Err sensor");return true;}
    if(!strcmp(window,"5m"))seconds=300;else if(!strcmp(window,"15m"))seconds=900;else if(!strcmp(window,"1h"))seconds=3600;else if(!strcmp(window,"day")||!strcmp(window,"prevday"))seconds=0;else{snprintf(out,cap,"Err window");return true;}
    auto mean=!strcmp(window,"prevday")?history_[i].yesterday(utc_):history_[i].get(utc_,seconds);
    if(mean.ms)snprintf(out,cap,"%s %s observed mean %.4fV %.6fA %.6fW measured=%lums energy=%.6fWh",sensor,window,mean.v(),mean.a(),mean.w(),(unsigned long)mean.ms,mean.ws/3600000.0);
    else snprintf(out,cap,"No measured history in this window yet");
  }else snprintf(out,cap,"pm help; pm temp: MCP9808; readings are observations, gaps not extrapolated");
  return true;
}
bool PowerMonitor::restore(){
  if(!filesystem_)return false;std::unique_ptr<State> state(new(std::nothrow) State);if(!state)return false;
  bool found=false;
  for(unsigned i=0;i<2;i++){
    File f=InternalFS.open(path(i),FILE_O_READ);if(!f)continue;
    const bool legacy=f.size()==sizeof(LegacyState);
    bool ok=false;
    if(legacy){
      std::unique_ptr<LegacyState> old(new(std::nothrow) LegacyState);
      if(old&&f.read((uint8_t*)old.get(),sizeof(LegacyState))==(int)sizeof(LegacyState)
         &&old->magic==0x228501&&crc(old.get(),offsetof(LegacyState,check))==old->check){
        state->sequence=old->sequence;
        for(unsigned j=0;j<2;j++){
          state->histories[j].previousDay=0;state->histories[j].previous=Ina228History::DayMean{};
          memcpy(state->histories[j].buckets,old->histories[j].buckets,sizeof(old->histories[j].buckets));
          state->histories[j].day=old->histories[j].day;state->histories[j].lastUtc=old->histories[j].lastUtc;state->histories[j].today=old->histories[j].today;
        }ok=true;
      }
    }else ok=f.size()==sizeof(State)&&f.read((uint8_t*)state.get(),sizeof(State))==(int)sizeof(State)
      &&state->magic==0x228502&&crc(state.get(),offsetof(State,check))==state->check;
    f.close();if(!ok)continue;
    if(!found||(int32_t)(state->sequence-sequence_)>0){sequence_=state->sequence;history_[0]=state->histories[0];history_[1]=state->histories[1];found=true;}
  }return found;
}
bool PowerMonitor::save(){
  if(!filesystem_)return false;std::unique_ptr<State> state(new(std::nothrow) State{});if(!state)return false;
  state->magic=0x228502;state->sequence=sequence_+1;state->histories[0]=history_[0];state->histories[1]=history_[1];state->check=crc(state.get(),offsetof(State,check));
  const char* destination=path(state->sequence&1);
  if(InternalFS.exists(destination)&&!InternalFS.remove(destination))return false;
  File f=InternalFS.open(destination,FILE_O_WRITE);bool ok=f&&f.write((uint8_t*)state.get(),sizeof(State))==sizeof(State);f.close();
  if(!ok)return false;File check=InternalFS.open(destination,FILE_O_READ);
  ok=check&&check.size()==sizeof(State)&&check.read((uint8_t*)state.get(),sizeof(State))==(int)sizeof(State);check.close();
  if(!ok||state->magic!=0x228502||state->sequence!=sequence_+1||crc(state.get(),offsetof(State,check))!=state->check)return false;
  sequence_=state->sequence;return true;
}
}
