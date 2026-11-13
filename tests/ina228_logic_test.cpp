#include "Ina228Logic.h"
#include <cassert>
#include <cmath>
#include <cstdio>
using namespace pm;
int main(){
 assert(ina228Signed20(0xfffff0)==-1);assert(ina228Signed20(0x800000)==-524288);
 float v,a,w;
 assert(ina228Decode(32000u<<4,20480u<<4,.1f,false,v,a,w));
 assert(fabs(v-4)<.0001&&fabs(a-.1)<.0001&&fabs(w-.4)<.0001);
 assert(ina228Decode(32000u<<4,20480u<<4,.1f,true,v,a,w));assert(a<0&&w<0);
 assert(!ina228Decode(0x7ffff0,0,.1f,false,v,a,w));assert(!ina228Decode(0,0,0,false,v,a,w));
 Ina228Schedule solar;solar.continuous=false;solar.a=.003;solar.solarDecision(100);assert(solar.continuous);
 solar.a=0;solar.solarDecision(200);solar.solarDecision(30199);assert(solar.continuous);
 solar.solarDecision(30200);assert(!solar.continuous);
 Ina228History history;uint32_t utc=1700000040;utc-=utc%60;
 for(unsigned i=0;i<3000;i++)history.add(utc+i/50,4,.1,.4,20);
 auto mean=history.get(utc+60,300);assert(mean.ms==60000&&fabs(mean.w()-.4)<.001);
 assert(history.get(utc+4000,300).ms==0);
 auto day=history.get(utc+60,0);assert(day.ms==60000);
 history.add(utc+86400,5,.2,1,20);assert(history.get(utc+86400,0).ms==20);
 history.add(utc,4,.1,.4,20);assert(history.get(utc,0).ms==20);
 Ina228History longday;uint32_t start=1700000000/86400*86400;
 for(unsigned i=0;i<4000000;i++)longday.add(start+i/50,4,.031f,.124f,20);
 assert(fabs(longday.get(start+80000,0).w()-.124)<.000001);
 puts("PASS INA228 signed ADC, units, polarity, saturation, solar hysteresis, weighted histories, gaps, UTC rollover/rollback and full-day precision");
}
