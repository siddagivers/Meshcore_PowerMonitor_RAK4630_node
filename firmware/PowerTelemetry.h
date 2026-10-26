#pragma once
#include "SolarHistory.h"

namespace pm {
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
