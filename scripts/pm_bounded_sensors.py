"""Bound high-level retries in project-private PlatformIO dependencies."""
from pathlib import Path
import re

def patch(text,expected):
    if '// PM_SENSOR_DEADLINES' in text:return text
    pattern=r'while\s*\((getStatus\(\) & AHTX0_STATUS_BUSY|!i2c_dev->read\(readbuffer, sizeof\(readbuffer\)\))\)\s*\{([^{}]*)\}'
    def replace(match):
        condition=match.group(1)
        # An AHT read failure is 0xff, which must not be mistaken for busy.
        test='true' if condition.startswith('getStatus') else condition
        body='const uint8_t pm_status=getStatus(); if(pm_status==0xff)return false; if(!(pm_status&AHTX0_STATUS_BUSY))break;' if test=='true' else ''
        return '{ const uint32_t pm_started=millis(); while('+test+') { '+body+' if((uint32_t)(millis()-pm_started)>=500)return false;'+match.group(2)+' } }'
    # Each original loop closes with a single brace after delay(). Add scope end.
    text,count=re.subn(pattern,replace,text,flags=re.S)
    if count!=expected:raise RuntimeError('Unexpected sensor retry layout: '+str(count))
    return '// PM_SENSOR_DEADLINES\n'+text

if 'Import' in globals():
    Import('env')
    base=Path(env.subst('$PROJECT_LIBDEPS_DIR'))/env.subst('$PIOENV')
    for directory,filename,count in [('Adafruit AHTX0','Adafruit_AHTX0.cpp',3),('Adafruit SHTC3 Library','Adafruit_SHTC3.cpp',1)]:
        path=base/directory/filename
        path.write_text(patch(path.read_text(encoding='utf-8'),count),encoding='utf-8')
