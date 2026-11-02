"""PlatformIO pre-script: project-local bounded Wire, no global core edits.

Generated Wire sources retain their original LGPL-2.1-or-later notices.
"""
from pathlib import Path
import json
import re
import shutil

HELPER=r'''
#include "BoundedWireWait.h"
static volatile uint32_t pm_wire_timeouts=0;
static const char* pm_wire_last_stage="none";
uint32_t pmWireTimeoutCount() { return pm_wire_timeouts; }
const char* pmWireLastTimeoutStage() { return pm_wire_last_stage; }
template<class Ready>
static bool pmBoundedTwimWait(NRF_TWIM_Type* twim,Ready ready,const char* stage) {
  if(pm::boundedWireWait(ready,[](){return micros();},50000,2000000))return true;
  ++pm_wire_timeouts;pm_wire_last_stage=stage;
  // A stuck STOP must not turn the timeout recovery into another endless wait.
  twim->TASKS_RESUME=1;twim->TASKS_STOP=1;
  for(unsigned i=0;i<1000 && !twim->EVENTS_STOPPED;++i)delayMicroseconds(1);
  const uint32_t enabled=twim->ENABLE;twim->ENABLE=0;
  twim->EVENTS_RXSTARTED=0;twim->EVENTS_LASTRX=0;
  twim->EVENTS_TXSTARTED=0;twim->EVENTS_LASTTX=0;
  twim->EVENTS_STOPPED=0;twim->EVENTS_SUSPENDED=0;
  twim->EVENTS_ERROR=0;twim->ERRORSRC=twim->ERRORSRC;
  twim->ENABLE=enabled;
  return false;
}
'''

def patch_source(source):
    anchor='#include <Adafruit_TinyUSB.h> // for Serial'
    if source.count(anchor)!=1:raise RuntimeError('Unsupported Wire include layout')
    source=source.replace(anchor,anchor+'\n'+HELPER)
    anchor='uint8_t TwoWire::endTransmission(bool stopBit)'
    if source.count(anchor)!=1:raise RuntimeError('Unsupported Wire transfer layout')
    rx,tx=source.split(anchor)
    for part,code,operations in (('rx',0,('RXSTARTED','LASTRX','STOPPED','SUSPENDED')),('tx',4,('TXSTARTED','LASTTX','STOPPED','SUSPENDED'))):
        text=rx if part=='rx' else tx
        for event in operations:
            error=' && !_p_twim->EVENTS_ERROR' if event not in ('STOPPED','SUSPENDED') else ''
            old=f'while(!_p_twim->EVENTS_{event}{error});'
            if text.count(old)!=1:raise RuntimeError('Unsupported Wire wait: '+old)
            condition=f'_p_twim->EVENTS_{event}'+(' || _p_twim->EVENTS_ERROR' if error else '')
            new=f'if(!pmBoundedTwimWait(_p_twim,[&](){{return {condition};}},"{part}-{event.lower()}"))return {code};'
            text=text.replace(old,new)
        if part=='rx':rx=text
        else:tx=text
    result=rx+anchor+tx
    if re.search(r'while\s*\(\s*!_p_twim->EVENTS_',result):raise RuntimeError('Unbounded Wire event wait remains')
    return result

def prepare(framework,project):
    original=framework/'libraries/Wire';dest=project/'lib/PMBoundedWire'
    dest.mkdir(parents=True,exist_ok=True)
    for path in original.iterdir():
        if path.is_file() and path.suffix in ('.h','.cpp','.c'):
            shutil.copy2(path,dest/path.name)
    target=dest/'Wire_nRF52.cpp';target.write_text(patch_source(target.read_text(encoding='utf-8')),encoding='utf-8')
    with (dest/'Wire.h').open('a',encoding='utf-8') as f:
        f.write('\nuint32_t pmWireTimeoutCount();\nconst char* pmWireLastTimeoutStage();\n')
    shutil.copy2(project/'examples/simple_repeater/BoundedWireWait.h',dest/'BoundedWireWait.h')
    (dest/'library.json').write_text(json.dumps({'name':'Wire','version':'1.0.0-pm-bounded','frameworks':['arduino'],'platforms':['nordicnrf52'],'build':{'srcDir':'.'}}),encoding='utf-8')
    print('PowerMonitor: generated project-local Wire with all 8 master waits bounded')

if 'Import' in globals():
    Import('env')
    prepare(Path(env.PioPlatform().get_package_dir('framework-arduinoadafruitnrf52')),Path(env.subst('$PROJECT_DIR')))
