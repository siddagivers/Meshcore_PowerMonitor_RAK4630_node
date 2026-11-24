#pragma once
#include <stddef.h>
#include <stdint.h>
#include "TelemetryPage.h"
class SensorManager;
namespace pm {
bool freshBusy();
const char* freshStatus();
bool startFresh(SensorManager&,uint8_t permissions,TelemetryPage::Page,uint32_t utc,float battery,float mcu);
bool collectFresh(uint8_t* destination,size_t capacity,size_t& size);
}
