#include "SensorDecoders.h"
#include <cassert>
#include <cmath>
#include <cstdio>
int main() {
  pm::InaReading r{};
  // Regression: the normal conversion-ready bit must NOT discard a sample.
  const uint16_t bus=(1250U<<3)|2U; // 5 V, CNVR=1, OVF=0
  assert(pm::decodeIna219(1000,bus,0.1f,1,r));
  assert(std::fabs(r.volts-5.01f)<0.0001f);
  assert(std::fabs(r.milliamps-100)<0.001f);
  assert(std::fabs(r.milliwatts-501)<0.01f && !r.math_overflow);
  assert(pm::decodeIna219(1000,bus|1U,0.1f,1,r) && r.math_overflow);
  assert(std::fabs(r.milliwatts-501)<0.01f); // calibrated-math OVF is not raw-ADC failure
  assert(pm::decodeIna219((uint16_t)(int16_t)-1000,bus,0.1f,1,r));
  assert(std::fabs(r.milliamps+100)<0.001f && r.milliwatts<0);
  assert(!pm::decodeIna219(1000,bus,0,1,r));
  assert(!pm::decodeIna219(1000,bus,NAN,1,r));
  // An ACK alone is not an MCP9808 identity check.
  assert(pm::isMcp9808(0x0054,0x0400));
  assert(pm::isMcp9808(0x0054,0x0401));
  assert(!pm::isMcp9808(0x0000,0x0400));
  assert(!pm::isMcp9808(0x0054,0x1900));
  float temperature=0;
  assert(pm::decodeMcp9808(0x0194,temperature) && temperature==25.25f);
  assert(pm::decodeMcp9808(0xE194,temperature) && temperature==25.25f); // ignore alert flags
  assert(pm::decodeMcp9808(0x1F5E,temperature) && temperature==-10.125f);
  assert(pm::decodeMcp9808(0x1DC8,temperature) && temperature==-35.5f); // valid signed value; never abs()
  assert(!pm::decodeMcp9808(0x0800,temperature)); // outside rated range
  puts("PASS: INA219 ready/overflow bits, voltage/current units, MCP9808 IDs and signed temperatures");
}
