"""Test the real asynchronous worker's ownership and completion protocol."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
headers={
'Arduino.h':'''#pragma once
#include <stdint.h>
#include <math.h>
extern uint32_t ticks;inline uint32_t millis(){return ticks;}
''',
'FreeRTOS.h':'''#pragma once
#define pdTRUE 1
#define pdPASS 1
#define tskIDLE_PRIORITY 0
#define portMAX_DELAY 0xffffffffu
''',
'semphr.h':'''#pragma once
struct Semaphore {bool value=false;};using SemaphoreHandle_t=Semaphore*;
inline SemaphoreHandle_t xSemaphoreCreateBinary(){return new Semaphore;}
inline void xSemaphoreGive(SemaphoreHandle_t s){s->value=true;}
inline int xSemaphoreTake(SemaphoreHandle_t s,int wait){if(wait)return 0;if(!s->value)return 0;s->value=false;return 1;}
''',
'task.h':'''#pragma once
struct WaitingForRequest {};
using TaskHandle_t=void*;
extern void (*scheduled)(void*);extern bool allocationFails;
extern unsigned tasksCreated,notifications;
inline int xTaskCreate(void(*fn)(void*),const char*,unsigned stack,void*,unsigned priority,TaskHandle_t* handle){
 if(stack!=4096||priority!=1||allocationFails)return 0;
 scheduled=fn;*handle=&tasksCreated;++tasksCreated;return 1;
}
inline void xTaskNotifyGive(TaskHandle_t){++notifications;}
inline unsigned ulTaskNotifyTake(int,unsigned){if(!notifications)throw WaitingForRequest{};return notifications--;}
''',
'PowerMonitor.h':'''#pragma once
#include <CayenneLPP.h>
#include "TelemetryPage.h"
namespace pm {struct PowerMonitor {unsigned refreshes=0;void refreshTelemetry(uint32_t){++refreshes;}
 void appendTelemetry(CayenneLPP& lpp,uint8_t,TelemetryPage::Page page){if(page!=TelemetryPage::ENVIRONMENT)lpp.addVoltage(100,1);}};}
''',
'CayenneLPP.h':'''#pragma once
#include <stdint.h>
#include <stddef.h>
extern unsigned liveEncoders;
extern bool encoderAllocationFails;
struct CayenneLPP {uint8_t data[163];unsigned size=0;CayenneLPP(unsigned){++liveEncoders;}
 ~CayenneLPP(){--liveEncoders;}
 void addVoltage(unsigned,float){data[size++]=1;}
 void addTemperature(unsigned,float){data[size++]=2;}
 unsigned getSize(){return size;}uint8_t* getBuffer(){return encoderAllocationFails?nullptr:data;}};
''',
'helpers/SensorManager.h':'''#pragma once
#include <CayenneLPP.h>
#define TELEM_PERM_ENVIRONMENT 4
struct SensorManager {unsigned queries=0;void querySensors(uint8_t permission,CayenneLPP& lpp){++queries;if(permission&4)lpp.addTemperature(2,25);}};
'''
}
source=r'''
#include "SensorRefresh.h"
#include "PowerMonitor.h"
#include <helpers/SensorManager.h>
#include <task.h>
#include <cassert>
#include <cstring>
#include <cstdio>
uint32_t ticks=0;void (*scheduled)(void*)=nullptr;bool allocationFails=false;
unsigned tasksCreated=0,notifications=0,liveEncoders=0;bool encoderAllocationFails=false;
pm::PowerMonitor power_monitor;
void processRequest(){
 try{scheduled(nullptr);assert(false);}catch(const WaitingForRequest&){}
 assert(!liveEncoders);
}
int main(){
 SensorManager sensors;uint8_t output[163];size_t size=99;
 assert(!pm::freshBusy());allocationFails=true;
 assert(!pm::startFresh(sensors,4,pm::TelemetryPage::POWER,1,4,25));assert(!pm::freshBusy());
 allocationFails=false;assert(pm::startFresh(sensors,4,pm::TelemetryPage::POWER,1,4,25));
 assert(pm::freshBusy());assert(!pm::startFresh(sensors,4,pm::TelemetryPage::LIVE,1,4,25));
 // A worker that makes no progress never blocks the main task's polling.
 for(unsigned i=0;i<100000;++i)assert(!pm::collectFresh(output,sizeof(output),size));
 ticks=6000;assert(strstr(pm::freshStatus(),"isolated"));
 processRequest();assert(pm::collectFresh(output,sizeof(output),size));
 assert(!pm::freshBusy()&&size==2&&sensors.queries==0&&power_monitor.refreshes==1);
 assert(!pm::collectFresh(output,sizeof(output),size));
 assert(pm::startFresh(sensors,4,pm::TelemetryPage::ENVIRONMENT,1,4,25));processRequest();
 assert(pm::collectFresh(output,sizeof(output),size));assert(size==3&&sensors.queries==1);
 assert(pm::startFresh(sensors,0,pm::TelemetryPage::POWER,1,4,25));processRequest();
 assert(pm::collectFresh(output,sizeof(output),size));assert(size==1&&power_monitor.refreshes==2);
 for(unsigned i=0;i<256;++i){
  assert(pm::startFresh(sensors,4,pm::TelemetryPage::LIVE,1,4,25));processRequest();
  assert(pm::collectFresh(output,sizeof(output),size)&&size==4);
 }
 assert(tasksCreated==1);
 encoderAllocationFails=true;
 assert(pm::startFresh(sensors,4,pm::TelemetryPage::LIVE,1,4,25));processRequest();
 assert(pm::collectFresh(output,sizeof(output),size)&&size==0&&!pm::freshBusy());
 puts("PASS async worker: polling, exclusive ownership, filters, one reused task, released buffers and allocation failures");
}
'''
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory)
 for name,data in headers.items():
  dest=p/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(data)
 for name in ('SensorRefresh.cpp','SensorRefresh.h','TelemetryPage.h'):
  (p/name).write_text((root/'firmware'/name).read_text())
 (p/'test.cpp').write_text(source)
 subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(p),str(p/'SensorRefresh.cpp'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
