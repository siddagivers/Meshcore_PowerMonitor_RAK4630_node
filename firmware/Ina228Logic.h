#pragma once
#include <stdint.h>
#include <math.h>
namespace pm {
inline int32_t ina228Signed20(uint32_t raw) {
  const uint32_t value=(raw>>4)&0xfffff;
  return value&0x80000?(int32_t)value-1048576:(int32_t)value;
}
inline bool ina228Decode(uint32_t shunt,uint32_t bus,float ohms,bool battery,float& v,float& a,float& w) {
  if(!isfinite(ohms)||ohms<=0)return false;
  const int32_t s=ina228Signed20(shunt), b=ina228Signed20(bus);
  if(b<0 || s<=-524287 || s>=524287)return false;
  v=b*0.0001953125f;
  a=s*0.0000003125f/ohms*(battery?-1:1);
  w=v*a;
  return isfinite(w)&&v<=85;
}
struct Ina228Mean {
  float vs=0,as=0,ws=0; uint32_t ms=0;
  void add(float v,float a,float w,uint32_t dt){vs+=v*dt;as+=a*dt;ws+=w*dt;ms+=dt;}
  void merge(const Ina228Mean& other){vs+=other.vs;as+=other.as;ws+=other.ws;ms+=other.ms;}
  float v()const{return ms?vs/ms:NAN;}
  float a()const{return ms?as/ms:NAN;}
  float w()const{return ms?ws/ms:NAN;}
};
struct Ina228History {
  struct DayMean {
    double vs=0,as=0,ws=0;uint32_t ms=0;
    void add(float v,float a,float w,uint32_t dt){vs+=(double)v*dt;as+=(double)a*dt;ws+=(double)w*dt;ms+=dt;}
    Ina228Mean result()const{Ina228Mean out;out.vs=vs;out.as=as;out.ws=ws;out.ms=ms;return out;}
  };
  struct Bucket {uint32_t minute=0;Ina228Mean mean;};
  Bucket buckets[121];
  uint32_t day=0,lastUtc=0;DayMean today;
  void add(uint32_t utc,float v,float a,float w,uint32_t dt){
    if(utc<1700000000 || !dt)return;
    if(lastUtc && utc<lastUtc){for(auto& b:buckets)b=Bucket{};today=DayMean{};day=0;}
    lastUtc=utc;
    if(day!=utc/86400){day=utc/86400;today=DayMean{};}
    const uint32_t minute=utc/30;auto& b=buckets[minute%121];
    if(b.minute!=minute){b.minute=minute;b.mean=Ina228Mean{};}
    b.mean.add(v,a,w,dt);today.add(v,a,w,dt);
  }
  Ina228Mean get(uint32_t utc,unsigned seconds)const{
    Ina228Mean out;
    if(!seconds)return day==utc/86400?today.result():out;
    // Exclude the oldest partially overlapping 30-second bucket. The current
    // bucket contains observations only up to now and can safely be included.
    for(const auto& b:buckets)if(b.minute && b.minute*30>=utc-seconds && b.minute*30<=utc)out.merge(b.mean);
    return out;
  }
};
struct Ina228Schedule {
  bool continuous=true,pending=false,valid=false,detected=false;
  uint32_t next=0,triggered=0,last=0,quiet=0;float v=NAN,a=NAN,w=NAN;uint32_t errors=0;
  void solarDecision(uint32_t now){
    if(!continuous && fabsf(a)>=0.002f){continuous=true;quiet=0;}
    else if(continuous){
      if(fabsf(a)>0.0005f)quiet=0;
      else if(!quiet)quiet=now;
      else if((uint32_t)(now-quiet)>=30000){continuous=false;quiet=0;}
    }
  }
};
}
