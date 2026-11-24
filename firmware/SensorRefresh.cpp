#include "SensorRefresh.h"
#include "PowerMonitor.h"
#include <helpers/SensorManager.h>
#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <semphr.h>
#include <string.h>
extern pm::PowerMonitor power_monitor;
namespace pm {
namespace {
struct Refresh {
  bool active=false;uint32_t started=0,utc=0;
  uint8_t permissions=0,data[163];size_t size=0;
  float battery=0,mcu=NAN;TelemetryPage::Page page=TelemetryPage::LIVE;
  SensorManager* sensors=nullptr;SemaphoreHandle_t done=nullptr;
} job;
TaskHandle_t worker=nullptr;

void sampleTelemetry(){
  CayenneLPP result(sizeof(job.data));
  if(!result.getBuffer())return;
  result.addVoltage(1,job.battery);
  if(job.permissions&TELEM_PERM_ENVIRONMENT){
    power_monitor.refreshTelemetry(job.utc);
    power_monitor.appendTelemetry(result,job.permissions,job.page);
  }
  if(job.page!=TelemetryPage::POWER){
    job.sensors->querySensors(job.permissions,result);
    if(isfinite(job.mcu))result.addTemperature(1,job.mcu);
  }
  job.size=result.getSize();memcpy(job.data,result.getBuffer(),job.size);
}

void run(void*){
  for(;;){
    ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
    sampleTelemetry(); // Frees the encoder buffer before publishing completion.
    xSemaphoreGive(job.done);
  }
}
}
bool freshBusy(){return job.active;}
const char* freshStatus(){return !job.active?"idle":(uint32_t)(millis()-job.started)>5000?"sensor stalled; bus isolated":"sampling";}
bool startFresh(SensorManager& sensors,uint8_t permissions,TelemetryPage::Page page,uint32_t utc,float battery,float mcu){
  if(job.active)return false;
  if(!job.done)job.done=xSemaphoreCreateBinary();
  if(!job.done)return false;
  // Same 16-KiB allocation as the independently verified OTA worker. Keeping
  // this out of the 4-KiB Arduino loop stack also isolates library call frames.
  // Match Arduino's low-priority loop task. Its yield() does not schedule
  // lower-priority tasks, so an idle-priority worker could starve forever.
  if(!worker && xTaskCreate(run,"pm-sensors",4096,nullptr,tskIDLE_PRIORITY+1,&worker)!=pdPASS)return false;
  job.sensors=&sensors;job.permissions=permissions;job.page=page;
  job.utc=utc;job.battery=battery;job.mcu=mcu;job.started=millis();job.active=true;job.size=0;
  xTaskNotifyGive(worker);
  return true;
}
bool collectFresh(uint8_t* destination,size_t capacity,size_t& size){
  if(!job.active||xSemaphoreTake(job.done,0)!=pdTRUE)return false;
  size=job.size<=capacity?job.size:0;
  if(size)memcpy(destination,job.data,size);
  job.active=false;return true;
}
}
