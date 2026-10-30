#pragma once
#include "SolarHistory.h"

namespace pm {
// Raw battery flow is discharge-positive; display charge-positive without
// changing the persisted discharge-energy counter's historical convention.
inline float displayFlow(float value,bool battery) { return battery?-value:value; }
template<class Encoder>
void appendInstantReading(Encoder& lpp,uint8_t channel,float volts,float milliamps,float milliwatts,bool battery) {
  if(isfinite(volts)&&volts>=0&&volts<=327.67f)lpp.addVoltage(channel,volts);
  const float amps=displayFlow(milliamps,battery)/1000;
  // CayenneLPP getTypeSigned(LPP_CURRENT) is true (signed 16-bit, 1 mA).
  if(isfinite(amps)&&amps>=-32.768f&&amps<=32.767f)lpp.addCurrent(channel,amps);
  const float watts=displayFlow(milliwatts,battery)/1000;
  if(isfinite(watts)&&watts>=-327.68f&&watts<=327.67f)lpp.addAnalogInput(channel,watts);
  // Native power is unsigned: magnitude stays visible in both directions.
  // Direction is conveyed by native Current and signed analog watts.
  if(isfinite(watts)&&fabsf(watts)<=65535)lpp.addPower(channel,fabsf(watts));
}
// Native Cayenne energy is kWh at 1-Wh resolution and power is integer W.
// Also supply generic mWh and signed analog W for low-power solar nodes.
template<class Encoder>
void appendSolarReading(Encoder& lpp,uint8_t channel,const SolarHistory::Reading& r) {
  lpp.addPercentage(channel,r.coverage());
  if(!r.covered_ms)return;
  if(r.mwh>=0 && r.mwh<4294967000.0) {
    lpp.addGenericSensor(channel,(float)r.mwh);
    lpp.addEnergy(channel,(float)(r.mwh/1000000.0));
  }
  const double watts=r.watts();
  if(isfinite(watts)&&watts>=-327.67&&watts<=327.67)
    lpp.addAnalogInput(channel,(float)watts);
}
}
