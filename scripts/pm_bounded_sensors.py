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

def patch_calibration(text):
    if '// PM_CALIBRATION_DEADLINE' in text:return text
    old='while (isReadingCalibration())\n    delay(10);'
    if text.count(old)!=1:raise RuntimeError('Unexpected BME calibration wait')
    new='{ const uint32_t pm_started=millis(); while(isReadingCalibration()) { if((uint32_t)(millis()-pm_started)>=500)return false; delay(10); } }'
    return '// PM_CALIBRATION_DEADLINE\n'+text.replace(old,new)

def patch_barometer(text):
    if '// PM_LPS_DEADLINE' in text:return text
    pattern=r'while\s*\(\(i2cRead\(LPS22HB_CTRL2_REG\) & 0x01\) != 0\)\s*\{\s*yield\(\);\s*\}'
    replacement='''{ const uint32_t pm_started=millis(); unsigned pm_tries=0;
      for(;;) {
        const int pm_status=i2cRead(LPS22HB_CTRL2_REG);
        if(pm_status<0)return NAN;
        if(!(pm_status&1))break;
        if((uint32_t)(millis()-pm_started)>=500 || ++pm_tries>=500)return NAN;
        delay(1);
      }
    }'''
    text,count=re.subn(pattern,lambda _:replacement,text)
    if count!=1:raise RuntimeError('Unexpected LPS22HB conversion wait')
    return '// PM_LPS_DEADLINE\n#include <math.h>\n'+text

if 'Import' in globals():
    Import('env')
    base=Path(env.subst('$PROJECT_LIBDEPS_DIR'))/env.subst('$PIOENV')
    for directory,filename,count in [('Adafruit AHTX0','Adafruit_AHTX0.cpp',3),('Adafruit SHTC3 Library','Adafruit_SHTC3.cpp',1)]:
        path=base/directory/filename
        path.write_text(patch(path.read_text(encoding='utf-8'),count),encoding='utf-8')
    path=base/'Adafruit BME280 Library'/'Adafruit_BME280.cpp'
    path.write_text(patch_calibration(path.read_text(encoding='utf-8')),encoding='utf-8')
    path=base/'Arduino_LPS22HB'/'src'/'BARO.cpp'
    path.write_text(patch_barometer(path.read_text(encoding='utf-8')),encoding='utf-8')
