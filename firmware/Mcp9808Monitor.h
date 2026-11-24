#pragma once
#include "SensorDecoders.h"
namespace pm {
// Transport uses the project's bounded Wire implementation. No conversion wait
// loops: a missing/failed device is retried after 10 seconds, not every loop.
class Mcp9808Monitor {
public:
  bool detected=false,valid=false;
  uint16_t manufacturer=0,device=0,raw=0;
  float temperature=NAN;
  uint32_t errors=0,last=0;
  void requestFresh(){if(detected&&!warming_)started_=false;}
  template<class Read,class Write>
  void tick(uint32_t now,Read read,Write write){
    const uint32_t interval=warming_?300UL:detected?60000UL:10000UL;
    if(started_ && (uint32_t)(now-attempt_)<interval)return;
    started_=true;attempt_=now;
    if(!detected){
      uint16_t config=0;
      if(!read(0x18,6,manufacturer)||!read(0x18,7,device)
         ||!isMcp9808(manufacturer,device)||!read(0x18,1,config)
         ||!write(0x18,1,config&~0x0100U)){fail();return;}
      detected=true;
      // Do not publish the old conversion immediately after waking from
      // shutdown. The next poll reads after at least the maximum conversion.
      valid=false;temperature=NAN;warming_=true;return;
    }
    float value;
    if(!read(0x18,5,raw)||!decodeMcp9808(raw,value)){fail();return;}
    temperature=value;valid=true;last=now;warming_=false;
  }
private:
  bool started_=false,warming_=false;
  uint32_t attempt_=0;
  void fail(){detected=false;valid=false;warming_=false;temperature=NAN;++errors;}
};
}
