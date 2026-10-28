#pragma once
#include <stdint.h>
#include <math.h>

namespace pm {
struct InaReading { float volts, milliamps, milliwatts; bool math_overflow; };
inline bool decodeIna219(uint16_t shunt,uint16_t bus,float ohms,int sign,InaReading& out) {
  if(!isfinite(ohms)||ohms<=0)return false;
  // INA219 datasheet: bit 1 = conversion READY; bit 0 = calibrated-math
  // overflow. Neither invalidates the raw shunt/bus ADC values used here.
  const float shunt_v=(float)(int16_t)shunt*0.00001f;
  out.volts=(float)(bus>>3)*0.004f+shunt_v;
  out.milliamps=1000.0f*shunt_v/ohms*(sign<0?-1:1);
  out.milliwatts=out.volts*out.milliamps;
  out.math_overflow=(bus&1U)!=0;
  return true;
}
inline bool isMcp9808(uint16_t manufacturer,uint16_t device) {
  return manufacturer==0x0054 && (device&0xFF00U)==0x0400;
}
inline bool decodeMcp9808(uint16_t raw,float& temperature) {
  temperature=(float)(raw&0x0FFFU)/16.0f;
  if(raw&0x1000U)temperature-=256.0f;
  return temperature>=-40.0f && temperature<=125.0f;
}
}
