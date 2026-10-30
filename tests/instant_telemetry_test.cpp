#include "PowerTelemetry.h"
#include <cassert>
#include <cmath>
#include <cstdio>
struct Encoder {
  float voltage=NAN,current=NAN,analog=NAN,power=NAN;
  void addVoltage(uint8_t,float v){voltage=v;}
  void addCurrent(uint8_t,float v){current=v;}
  void addAnalogInput(uint8_t,float v){analog=v;}
  void addPower(uint8_t,float v){power=v;}
};
int main() {
  Encoder discharge;
  pm::appendInstantReading(discharge,101,3.84f,9,34.56f,true);
  assert(std::fabs(discharge.current+0.009f)<0.000001f);
  assert(discharge.analog<0 && discharge.power>0);
  Encoder charge;
  pm::appendInstantReading(charge,101,3.89f,-265,-1030.85f,true);
  assert(std::fabs(charge.current-0.265f)<0.000001f);
  assert(charge.analog>0 && charge.power>0);
  Encoder reverseSolar;
  pm::appendInstantReading(reverseSolar,100,0.09f,-0.1f,-0.009f,false);
  assert(reverseSolar.current<0 && reverseSolar.analog<0 && reverseSolar.power>0);
  Encoder zero;
  pm::appendInstantReading(zero,100,0,0,0,false);
  assert(zero.current==0 && zero.power==0);
  Encoder overflow;
  pm::appendInstantReading(overflow,100,5,40000,200000,false);
  assert(std::isnan(overflow.current));
  assert(overflow.analog==200 && overflow.power==200);
  Encoder invalid;
  pm::appendInstantReading(invalid,100,NAN,NAN,NAN,false);
  assert(std::isnan(invalid.current)&&std::isnan(invalid.power));
  puts("PASS: battery charge/discharge polarity, signed solar current, zero and range handling");
}
