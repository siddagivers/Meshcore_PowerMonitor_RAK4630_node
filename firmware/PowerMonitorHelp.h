#pragma once
#include <stdio.h>
#include <string.h>
namespace pm {
inline bool powerHelp(const char* c,char* out,size_t cap,bool ina228){
  if(strcmp(c,"help")&&strcmp(c,"help pm")&&strncmp(c,"pm help",7))return false;
  const char* common[]={
    "pm version: firmware revision; pm diag: I2C timeout/uptime diagnostics; pm sensors: detection, errors and operating mode.",
    "pm ina off: shut down both INA sensors and stop polling; pm ina on: enable/re-detect them. Choice survives reboot. Does not cut supply power.",
    "pm solar: latest solar V/A/W; pm load: latest battery V/A/W; pm channels: telemetry channel legend. Missing readings are not zero consumption.",
    "pm ota status: stage/provisioning; pm ota boot: bootloader compatibility; pm ota result: last verification/activation result.",
    "pm ota verify <id>: verify staged image; pm ota apply <id>: verify and activate/reset; pm ota cancel: DISCARD staged image. Use uploader's ID.",
    "pm ota pair RAK4631_RAK15001_C: pair hardware; pm ota trust <signer-key>: trust firmware signer. Both local USB only; pm ota test: build marker.",
    "pm ota begin/data: uploader transport commands; pm ota help: protocol summary. get radio: inspect LoRa settings; reboot: restart device.",
    "Radio stop: older custom firmware used radio off. This official base has NO radio off command; do not assume it stops forwarding."
  };
  const char* extended228[]={
    "pm battery continuous off: five-minute single shots; pm battery continuous on: continuous measurement. Saved choice; pm ina off overrides both.",
    "pm history solar 5m/15m/1h/day: observed mean V/A/W; replace solar with battery for battery history. day=current UTC day, not rolling 24h.",
    "Solar auto: check every 10min while idle; |I|>=2mA starts continuous; |I|<=0.5mA for 30s returns idle. History checkpoints every 15min.",
    "Telemetry: Current=signed A; Analog Input=signed W; Percentage=measured coverage; Generic Sensor on 100/101=age seconds. Gaps not extrapolated."
  };
  const char* extended219[]={
    "pm status (or pm): energy/power summary; pm day: UTC daily energy and restore count; pm info: sensor addresses/shunts and firmware version.",
    "pm solar 15m/1h/today/yesterday: observed solar energy/average power/coverage; pm temp: MCP9808 reading and identity diagnostics.",
    "pm i2c: address scan (disabled INA addresses skipped); pm reset YES: clear energy counters/history, LOCAL USB ONLY. Other settings unchanged.",
    "INA219 profile: continuous sampling only when enabled. For five-minute battery sampling and adaptive solar, install the INA228 test profile."
  };
  unsigned page=0;char extra;
  if(!strcmp(c,"help")||!strcmp(c,"help pm")||!strcmp(c,"pm help")){
    snprintf(out,cap,"PowerMonitor help: pm help 1..12 (one described page per reply). 1 diagnostics;2 INA enable;3 readings;4-7 OTA/radio;8 radio stop;9-12 profile.");return true;
  }
  if(sscanf(c,"pm help %u %c",&page,&extra)!=1||page<1||page>12){snprintf(out,cap,"Use pm help or pm help 1..12");return true;}
  snprintf(out,cap,"%s",page<=8?common[page-1]:(ina228?extended228[page-9]:extended219[page-9]));return true;
}
}
