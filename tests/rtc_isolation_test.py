"""Exercise the actual RTC overlay, including rapid software-clock reads."""
from pathlib import Path
import sys,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
from inject import replace_one
from pm_async_telemetry import patch_clock
header=r'''#pragma once
#include <stdint.h>
extern uint32_t ticks;
namespace mesh {struct RTCClock {
 uint32_t value=1000,at=0;
 uint32_t getCurrentTime(){return value+(ticks-at)/1000;}
 void setCurrentTime(uint32_t v){value=v;at=ticks;}
};}
class AutoDiscoverRTCClock {
  mesh::RTCClock* _fallback;
public:
 AutoDiscoverRTCClock(mesh::RTCClock& f):_fallback(&f){}
 uint32_t getCurrentTime();void setCurrentTime(uint32_t);
};
'''
cpp=r'''#include "AutoDiscoverRTCClock.h"
static bool ds3231_success=false,rv3028_success=false,rtc_8563_success=false,rtc_8130_success=false;
uint32_t hardware=0;unsigned hardwareReads=0,hardwareWrites=0;
void enableHardware(uint32_t value){ds3231_success=true;hardware=value;}
uint32_t AutoDiscoverRTCClock::getCurrentTime() {
 if(ds3231_success){++hardwareReads;return hardware;}
 return _fallback->getCurrentTime();
}
void AutoDiscoverRTCClock::setCurrentTime(uint32_t time) {
 ++hardwareWrites;hardware=time;
}
'''
test=r'''
#include "AutoDiscoverRTCClock.h"
#include <cassert>
#include <cstdio>
namespace pm {bool active=false;bool freshBusy(){return active;}}
uint32_t ticks=0;extern unsigned hardwareReads,hardwareWrites;extern uint32_t hardware;
void enableHardware(uint32_t);
int main(){
 mesh::RTCClock fallback;AutoDiscoverRTCClock clock(fallback);
 for(ticks=0;ticks<100000;++ticks)assert(clock.getCurrentTime()==1000+ticks/1000);
 assert(clock.getCurrentTime()==1100); // must not reset fractional time each read
 enableHardware(2000);assert(clock.getCurrentTime()==2000);unsigned old=hardwareReads;
 pm::active=true;ticks+=3000;assert(clock.getCurrentTime()==2003);assert(hardwareReads==old);
 clock.setCurrentTime(4000);assert(clock.getCurrentTime()==4000);assert(hardwareWrites==0);
 pm::active=false;assert(clock.getCurrentTime()==4000);assert(hardwareWrites==1&&hardware==4000);
 puts("PASS RTC: rapid reads advance time, external mirror advances during sampling, hardware reads/writes isolated and clock writes deferred");
}
'''
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory);folder=p/'src/helpers';folder.mkdir(parents=True)
 (folder/'AutoDiscoverRTCClock.h').write_text(header)
 (folder/'AutoDiscoverRTCClock.cpp').write_text(cpp)
 patch_clock(p,replace_one)
 (p/'test.cpp').write_text(test)
 subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(folder),str(folder/'AutoDiscoverRTCClock.cpp'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
