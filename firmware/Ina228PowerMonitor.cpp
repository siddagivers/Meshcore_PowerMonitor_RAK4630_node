#include "PowerMonitor.h"
#include <InternalFileSystem.h>
#include <Mesh.h>
#include <memory>
#include <new>
#include <stdio.h>
#include <string.h>
using namespace Adafruit_LittleFS_Namespace;
namespace pm {
namespace {
constexpr float SHUNT[2]={0.100f,0.100f};
constexpr uint16_t ADC_CONT=0xBB69,ADC_ONCE=0x3B69; // 1052us VBUS/shunt, averaging 4
bool readReg(uint8_t address,uint8_t reg,uint32_t& result,unsigned bytes){
  Wire.beginTransmission(address);Wire.write(reg);
  if(Wire.endTransmission(false)!=0 || Wire.requestFrom((int)address,(int)bytes)!=(int)bytes)return false;
  result=0;for(unsigned i=0;i<bytes;i++){int b=Wire.read();if(b<0)return false;result=(result<<8)|(uint8_t)b;}return true;
}
bool writeReg(uint8_t address,uint8_t reg,uint16_t value){
  Wire.beginTransmission(address);Wire.write(reg);Wire.write((uint8_t)(value>>8));Wire.write((uint8_t)value);return Wire.endTransmission()==0;
}
uint32_t crc(const void* data,size_t size){const auto* p=(const uint8_t*)data;uint32_t c=2166136261;
  while(size--){c^=*p++;c*=16777619;}return c;}
struct State {uint32_t magic,sequence;Ina228History histories[2];uint32_t check;};
const char* path(unsigned slot){return slot?"/pm228.b":"/pm228.a";}
void emit(CayenneLPP& lpp,uint8_t id,float v,float a,float w){
  if(isfinite(v)&&v>=0&&v<=327.67f)lpp.addVoltage(id,v);
  if(isfinite(a)&&a>=-32.768f&&a<=32.767f)lpp.addCurrent(id,a);
  // Cayenne native power is unsigned/integer W: analog retains signed sub-W power.
  if(isfinite(w)&&w>=-327.68f&&w<=327.67f)lpp.addAnalogInput(id,w);
}
}
bool PowerMonitor::configure(unsigned i){
  uint32_t maker,device;
  if(!readReg(0x40+i,0x3e,maker,2)||maker!=0x5449
     ||!readReg(0x40+i,0x3f,device,2)||(device>>4)!=0x228)return false;
  // Explicit normal shunt range (+/-163.84mV). Derive signed current from raw
  // shunt voltage so calibration/current accumulator registers are not required.
  return writeReg(0x40+i,0,0)&&writeReg(0x40+i,1,channel_[i].continuous?ADC_CONT:0);
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
  filesystem_=fs;settings(false);restore();
  channel_[0].continuous=false;channel_[1].continuous=batteryContinuous_;
  for(unsigned i=0;i<2;i++)channel_[i].detected=configure(i);
  checkpoint_=millis();
}
void PowerMonitor::sample(unsigned i,uint32_t now){
  auto& c=channel_[i];const uint8_t address=0x40+i;
  const uint32_t interval=i?300000UL:600000UL;
  if(!c.detected)return;
  if(!c.pending && (int32_t)(now-c.next)<0)return;
  if(!c.continuous && !c.pending){
    c.valid=false;
    if(!writeReg(address,1,ADC_ONCE)){c.errors++;c.detected=false;return;}
    c.pending=true;c.triggered=now;return;
  }
  uint32_t diag;
  if(!readReg(address,0x0b,diag,2)){c.errors++;c.valid=false;c.pending=false;c.detected=false;return;}
  if(!(diag&2)){
    if(c.pending && (uint32_t)(now-c.triggered)>200){c.errors++;c.pending=false;c.valid=false;c.detected=false;writeReg(address,1,0);}
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
  bool was=c.continuous;if(i==0)c.solarDecision(now);
  if(was!=c.continuous)writeReg(address,1,c.continuous?ADC_CONT:0);
  c.next=now+(c.continuous?20:interval);
}
void PowerMonitor::poll(uint32_t now,uint32_t utc){
  utc_=utc;
  if((uint32_t)(now-probe_)>=10000){probe_=now;
    for(unsigned i=0;i<2;i++)if(!channel_[i].detected){channel_[i].detected=configure(i);channel_[i].pending=false;channel_[i].next=now;}}
  sample(0,now);sample(1,now);
  if(filesystem_&&(uint32_t)(now-checkpoint_)>=900000){checkpoint_=now;save();}
}
void PowerMonitor::appendTelemetry(CayenneLPP& lpp,uint8_t permissions)const{
  if(!(permissions&TELEM_PERM_ENVIRONMENT))return;
  // 120 bytes for all available V/A/signed-W groups + 24 bytes coverage.
  // Stock sensor additions remain subject to Cayenne buffer checks.
  const unsigned windows[]={300,900,3600,0};
  for(unsigned i=0;i<2;i++){
    const auto& c=channel_[i];if(c.valid)emit(lpp,100+i,c.v,c.a,c.w);
    for(unsigned j=0;j<4;j++){
      auto mean=history_[i].get(utc_,windows[j]);uint8_t id=110+i*10+j;
      if(mean.ms)emit(lpp,id,mean.v(),mean.a(),mean.w());
      uint32_t span=windows[j]?windows[j]*1000UL:(utc_%86400)*1000UL;
      lpp.addPercentage(id,span?fminf(100,mean.ms*100.0f/span):0);
    }
  }
}
bool PowerMonitor::handleCommand(const char* command,char* out,size_t cap){
  if(!strcmp(command,"help")||!strcmp(command,"help pm")||!strcmp(command,"pm help")){
    snprintf(out,cap,"INA228: pm version|diag|sensors|channels|battery continuous on/off|solar|load|history solar/battery 5m/15m/1h/day; pm ota help");return true;}
  if(strncmp(command,"pm",2)|| (command[2]&&command[2]!=' '))return false;
  if(!strcmp(command,"pm version"))snprintf(out,cap,"power-monitor %s git %s INA228",PM_VERSION,PM_SOURCE_SHA);
  else if(!strcmp(command,"pm channels"))snprintf(out,cap,"100 Solar actual;101 Battery actual;110-113 Solar 5m/15m/1h/UTCday;120-123 Battery same. Analog=W signed;V,A means;%%=measured coverage");
  else if(!strcmp(command,"pm diag"))snprintf(out,cap,"I2C timeouts=%lu last=%s; uptime=%lus",(unsigned long)pmWireTimeoutCount(),pmWireLastTimeoutStage(),(unsigned long)(millis()/1000));
  else if(!strcmp(command,"pm sensors")||!strcmp(command,"pm status"))snprintf(out,cap,"INA228 solar40:%s %s; battery41:%s %s; errors=%lu/%lu; history=%s",
    channel_[0].detected?"OK":"MISSING",channel_[0].continuous?"continuous":"10min idle",channel_[1].detected?"OK":"MISSING",batteryContinuous_?"continuous":"5min",(unsigned long)channel_[0].errors,(unsigned long)channel_[1].errors,filesystem_?"enabled":"RAM only");
  else if(!strcmp(command,"pm battery continuous on")||!strcmp(command,"pm battery continuous off")){
    bool desired=!strcmp(command,"pm battery continuous on");
    if(!writeReg(0x41,1,desired?ADC_CONT:0)){snprintf(out,cap,"Err INA228 write");return true;}
    batteryContinuous_=desired;channel_[1].continuous=desired;channel_[1].pending=false;channel_[1].last=0;channel_[1].next=millis();
    snprintf(out,cap,"OK battery %s; setting %s",desired?"continuous":"5-minute single shots",settings(true)?"saved":"not saved");
  }else if(!strcmp(command,"pm solar")||!strcmp(command,"pm load")){
    unsigned i=!strcmp(command,"pm load");const auto& c=channel_[i];
    if(c.valid)snprintf(out,cap,"%s INA228: %.4fV %.6fA %.6fW age=%lus %s",i?"Battery +charge/-discharge":"Solar",c.v,c.a,c.w,(unsigned long)((millis()-c.last)/1000),c.continuous?"continuous":"single shot");
    else snprintf(out,cap,"No valid INA228 observation");
  }else if(!strncmp(command,"pm history ",11)){
    char sensor[12],window[8],extra;unsigned seconds;
    if(sscanf(command+11,"%11s %7s %c",sensor,window,&extra)!=2){snprintf(out,cap,"pm history solar/battery 5m/15m/1h/day");return true;}
    unsigned i=!strcmp(sensor,"battery");
    if(strcmp(sensor,"solar")&&strcmp(sensor,"battery")){snprintf(out,cap,"Err sensor");return true;}
    if(!strcmp(window,"5m"))seconds=300;else if(!strcmp(window,"15m"))seconds=900;else if(!strcmp(window,"1h"))seconds=3600;else if(!strcmp(window,"day"))seconds=0;else{snprintf(out,cap,"Err window");return true;}
    auto mean=history_[i].get(utc_,seconds);
    if(mean.ms)snprintf(out,cap,"%s %s observed mean %.4fV %.6fA %.6fW measured=%lums energy=%.6fWh",sensor,window,mean.v(),mean.a(),mean.w(),(unsigned long)mean.ms,mean.ws/3600000.0);
    else snprintf(out,cap,"No measured history in this window yet");
  }else snprintf(out,cap,"pm help; readings are observations, gaps not extrapolated; MCP9808 not included in INA228 test");
  return true;
}
bool PowerMonitor::restore(){
  if(!filesystem_)return false;std::unique_ptr<State> state(new(std::nothrow) State);if(!state)return false;
  bool found=false;
  for(unsigned i=0;i<2;i++){
    File f=InternalFS.open(path(i),FILE_O_READ);if(!f)continue;
    bool ok=f.size()==sizeof(State)&&f.read((uint8_t*)state.get(),sizeof(State))==(int)sizeof(State);f.close();
    if(!ok||state->magic!=0x228501||crc(state.get(),offsetof(State,check))!=state->check)continue;
    if(!found||(int32_t)(state->sequence-sequence_)>0){sequence_=state->sequence;history_[0]=state->histories[0];history_[1]=state->histories[1];found=true;}
  }return found;
}
bool PowerMonitor::save(){
  if(!filesystem_)return false;std::unique_ptr<State> state(new(std::nothrow) State{});if(!state)return false;
  state->magic=0x228501;state->sequence=sequence_+1;state->histories[0]=history_[0];state->histories[1]=history_[1];state->check=crc(state.get(),offsetof(State,check));
  const char* destination=path(state->sequence&1);
  if(InternalFS.exists(destination)&&!InternalFS.remove(destination))return false;
  File f=InternalFS.open(destination,FILE_O_WRITE);bool ok=f&&f.write((uint8_t*)state.get(),sizeof(State))==sizeof(State);f.close();
  if(!ok)return false;File check=InternalFS.open(destination,FILE_O_READ);
  ok=check&&check.size()==sizeof(State)&&check.read((uint8_t*)state.get(),sizeof(State))==(int)sizeof(State);check.close();
  if(!ok||state->magic!=0x228501||state->sequence!=sequence_+1||crc(state.get(),offsetof(State,check))!=state->check)return false;
  sequence_=state->sequence;return true;
}
}
