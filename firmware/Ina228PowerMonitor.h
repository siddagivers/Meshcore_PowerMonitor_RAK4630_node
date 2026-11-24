#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <CayenneLPP.h>
#include "Ina228Logic.h"
#include "Mcp9808Monitor.h"
#include "TelemetryPage.h"
namespace pm {
class PowerMonitor {
public:
  void begin(bool);void poll(uint32_t,uint32_t);
  bool handleCommand(const char*,char*,size_t);
  void appendTelemetry(CayenneLPP&,uint8_t)const;
  void appendTelemetry(CayenneLPP&,uint8_t,TelemetryPage::Page)const;
  void refreshTelemetry(uint32_t utc);
  bool checkpointNow(){return save();}
private:
  Ina228Schedule channel_[2];Ina228History history_[2];
  Mcp9808Monitor mcp_;
  bool filesystem_=false,batteryContinuous_=true,historySaved_=false,inaEnabled_=true;uint32_t utc_=0,checkpoint_=0,sequence_=0,probe_=0;
  bool save();bool restore();bool settings(bool write);
  bool configure(unsigned);void sample(unsigned,uint32_t);
};
}
