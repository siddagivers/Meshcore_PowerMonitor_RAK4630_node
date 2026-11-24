"""Exercise the actual INA228 monitor with absent/stalled/reconnected I2C devices.

Host compiler only; substitutes hardware and filesystem, not monitor logic.
Set CXX_JSON to a JSON command array to use a non-default compiler.
"""
import json, os, subprocess, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
headers={
'Arduino.h':r'''#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
extern uint32_t nowMs;
inline uint32_t millis(){return nowMs;}
inline void delay(unsigned ms){nowMs+=ms;}
''',
'Wire.h':r'''#pragma once
#include <stdint.h>
struct WireMock {
 bool ina=true,mcp=true,ready=true;unsigned requests=0;uint8_t address=0,reg=0,index=0;uint32_t value=0;unsigned bytes=0;
 void beginTransmission(uint8_t a){address=a;index=0;}
 void write(uint8_t v){if(!index)reg=v;++index;}
 int endTransmission(bool=true){return (address==0x18?mcp:ina)?0:4;}
 int requestFrom(int a,int n){++requests;address=a;bytes=n;index=0;
  if(!(a==0x18?mcp:ina))return 0;
  if(a==0x18)value=reg==6?0x54:reg==7?0x400:reg==5?0x190:0;
  else value=reg==0x3e?0x5449:reg==0x3f?0x2280:reg==0xb?(ready?2:0):reg==4?(320u<<4):(20480u<<4);
  return n;
 }
 int read(){return (value>>(8*(bytes-1-index++)))&255;}
};
extern WireMock Wire;
inline unsigned long pmWireTimeoutCount(){return 0;}
inline const char* pmWireLastTimeoutStage(){return "none";}
''',
'CayenneLPP.h':r'''#pragma once
#include <vector>
struct CayenneLPP {
 std::vector<unsigned> temperatures,volts;
 void addTemperature(unsigned id,float){temperatures.push_back(id);}
 void addVoltage(unsigned id,float){volts.push_back(id);}
 void addCurrent(unsigned,float){}
 void addAnalogInput(unsigned,float){}
 void addGenericSensor(unsigned,float){}
 void addPercentage(unsigned,float){}
};
''',
'InternalFileSystem.h':r'''#pragma once
#include <stddef.h>
#include <stdint.h>
#include <map>
#include <string>
#include <vector>
namespace Adafruit_LittleFS_Namespace {
struct File {std::vector<uint8_t>* data=nullptr;size_t position=0;
 operator bool()const{return data!=nullptr;} size_t size(){return data?data->size():0;}
 int read(){return data&&position<data->size()?(*data)[position++]:-1;}
 int read(uint8_t* out,size_t n){size_t i=0;for(;data&&i<n&&position<data->size();++i)out[i]=(*data)[position++];return i;}
 size_t write(const uint8_t* in,size_t n){if(!data)return 0;data->insert(data->end(),in,in+n);return n;} void close(){};};
}
#define FILE_O_READ 0
#define FILE_O_WRITE 1
struct FS {std::map<std::string,std::vector<uint8_t>> files;
 bool exists(const char* name){return files.count(name);}
 bool remove(const char* name){return files.erase(name);}
 Adafruit_LittleFS_Namespace::File open(const char* name,int mode){if(!mode&&!exists(name))return {};return {&files[name],0};}};
extern FS InternalFS;
''',
'Mesh.h':'#pragma once\n',
'helpers/SensorManager.h':'#pragma once\n#define TELEM_PERM_ENVIRONMENT 2\n',
'PowerMonitor.h':'#include "Ina228PowerMonitor.h"\n',
'SensorRefresh.h':'#pragma once\nnamespace pm {inline bool freshBusy(){return false;} inline const char* freshStatus(){return "idle";}}\n',
}
source=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include "PowerMonitor.h"
#include "TelemetryPage.h"
#include <InternalFileSystem.h>
uint32_t nowMs=0;WireMock Wire;FS InternalFS;
pm::TelemetryPage pm::telemetry_page;
int main(){
 pm::PowerMonitor monitor;char reply[512];
 monitor.begin(false);
 monitor.poll(0,1700000000);nowMs=20;monitor.poll(nowMs,1700000000);
 nowMs=300;monitor.poll(nowMs,1700000000);
 monitor.handleCommand("pm temp",reply,sizeof(reply));assert(strstr(reply,"OK T=25.0000C"));
 monitor.handleCommand("pm sensors",reply,sizeof(reply));assert(strstr(reply,"solar41:OK battery40:OK; mcp18:OK"));
 pm::telemetry_page.page=pm::TelemetryPage::ENVIRONMENT;
 CayenneLPP env;monitor.appendTelemetry(env,2);assert(env.temperatures.size()==1&&env.temperatures[0]==102&&env.volts.empty());
 CayenneLPP denied;monitor.appendTelemetry(denied,0);assert(denied.temperatures.empty());
 Wire.ready=false;unsigned requests=Wire.requests;
 for(nowMs=301;nowMs<320;++nowMs)monitor.poll(nowMs,1700000000);
 assert(Wire.requests==requests); // no conversion-ready hot loop
 nowMs=521;monitor.poll(nowMs,1700000000);
 monitor.handleCommand("pm sensors",reply,sizeof(reply));assert(strstr(reply,"battery40:MISSING"));
 Wire.ready=true;nowMs=10001;monitor.poll(nowMs,1700000010);
 nowMs=10021;monitor.poll(nowMs,1700000010);
 monitor.handleCommand("pm sensors",reply,sizeof(reply));assert(strstr(reply,"battery40:OK"));
 monitor.handleCommand("pm ina off",reply,sizeof(reply));
 Wire.mcp=false;nowMs=60300;monitor.poll(nowMs,1700000060);
 monitor.handleCommand("pm temp",reply,sizeof(reply));assert(strstr(reply,"MISSING"));
 requests=Wire.requests;
 for(nowMs=60301;nowMs<70300;++nowMs)monitor.poll(nowMs,1700000060);
 assert(Wire.requests==requests); // disabled INAs and missing MCP do not flood bus
 Wire.mcp=true;nowMs=70300;monitor.poll(nowMs,1700000070);
 nowMs=70600;monitor.poll(nowMs,1700000070);
 monitor.handleCommand("pm sensors",reply,sizeof(reply));assert(strstr(reply,"solar41:DISABLED battery40:DISABLED; mcp18:OK"));
 monitor.handleCommand("pm ina on",reply,sizeof(reply));
 monitor.handleCommand("pm battery continuous off",reply,sizeof(reply));
 monitor.refreshTelemetry(1700000070);
 monitor.handleCommand("pm load",reply,sizeof(reply));assert(strstr(reply,"age=0s")&&strstr(reply,"single shot"));
 Wire.ina=false;monitor.refreshTelemetry(1700000070);
 monitor.handleCommand("pm load",reply,sizeof(reply));assert(strstr(reply,"No valid"));
 Wire.ina=true;
 // The old snapshot layout is read and converted; a midnight checkpoint
 // writes the new layout, and the completed day survives a second boot.
 struct OldHistory {pm::Ina228History::Bucket buckets[121];uint32_t day,lastUtc;pm::Ina228History::DayMean today;};
 struct OldState {uint32_t magic,sequence;OldHistory histories[2];uint32_t check;};
 OldState old{};old.magic=0x228501;old.sequence=7;
 uint32_t midnight=(1700000000u/86400+1)*86400;
 for(auto& h:old.histories){h.day=midnight/86400-1;h.lastUtc=midnight-1;h.today.add(4,.1,.4,60000);}
 uint32_t crc=2166136261;auto* bytes=(uint8_t*)&old;
 for(size_t i=0;i<offsetof(OldState,check);++i){crc^=bytes[i];crc*=16777619;}
 old.check=crc;InternalFS.files["/pm228.a"]=std::vector<uint8_t>(bytes,bytes+sizeof(old));
 pm::PowerMonitor migrated;migrated.begin(true);migrated.poll(nowMs,midnight);
 migrated.handleCommand("pm history solar prevday",reply,sizeof(reply));assert(strstr(reply,"4.0000V 0.100000A 0.400000W"));
 assert(InternalFS.files["/pm228.a"].size()>sizeof(old));
 pm::PowerMonitor restored;restored.begin(true);restored.poll(nowMs,midnight);
 restored.handleCommand("pm history solar prevday",reply,sizeof(reply));assert(strstr(reply,"measured=60000ms"));
 puts("PASS actual monitor: stalled ADC backoff, retry recovery, MCP independent of INA disable, environment page and permissions");
}
'''
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder)
 for name,data in headers.items():
  dest=p/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(data)
 (p/'test.cpp').write_text(source)
 # Match injection: the alternative implementation is installed beside the
 # selected PowerMonitor.h, rather than the legacy header in firmware/.
 (p/'PowerMonitor.cpp').write_text((root/'firmware/Ina228PowerMonitor.cpp').read_text())
 compiler=json.loads(os.environ.get('CXX_JSON','["g++"]'))
 exe=p/('test.exe' if os.name=='nt' else 'test')
 subprocess.run(compiler+['-std=c++17','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
  '-DPM_VERSION="review"','-DPM_SOURCE_SHA="review"','-I',str(p),'-I',str(root/'firmware'),
  str(p/'PowerMonitor.cpp'),str(p/'test.cpp'),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
