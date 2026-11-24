from pathlib import Path
import importlib.util, subprocess, tempfile, os, json
spec=importlib.util.spec_from_file_location('bounded',Path(__file__).resolve().parents[1]/'scripts/pm_bounded_sensors.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
aht='bool aht(){'+('while (getStatus() & AHTX0_STATUS_BUSY) { delay(10); }'*3)+'return true;}'
sht='bool sht(){uint8_t readbuffer[6]; while (!i2c_dev->read(readbuffer, sizeof(readbuffer))) { delay(1); } return true;}'
source=r'''
#include <stdint.h>
#include <cassert>
#include <math.h>
#define AHTX0_STATUS_BUSY 0x80
#define LPS22HB_CTRL2_REG 0x11
uint32_t ticks=0; int mode=0;
uint32_t millis(){return ticks;}
void delay(unsigned n){ticks+=n;}
uint8_t getStatus(){return mode==0?0:mode==1?0xff:0x80;}
int i2cRead(int){return mode==0?0:mode==1?-1:1;}
bool isReadingCalibration(){return mode!=0;}
struct Device {bool read(uint8_t*,unsigned){return mode==0;}} device;
Device* i2c_dev=&device;
'''+module.patch(aht,3)+module.patch(sht,1)+module.patch_calibration('bool calibration(){while (isReadingCalibration())\n    delay(10); return true;}')+module.patch_barometer('float pressure(){while ((i2cRead(LPS22HB_CTRL2_REG) & 0x01) != 0) { yield(); } return 1;}')+r'''
int main(){assert(aht());assert(sht());mode=1;ticks=0;assert(!aht());assert(ticks==0);
ticks=0;assert(!sht());assert(ticks==500);mode=2;ticks=0;assert(!aht());assert(ticks==500);
ticks=0;assert(!calibration());assert(ticks==500);
ticks=0;assert(isnan(pressure()));assert(ticks>=499&&ticks<=500);
mode=1;ticks=0;assert(isnan(pressure()));assert(ticks==0);
mode=0;assert(aht());assert(sht());assert(calibration());assert(pressure()==1);}
'''
assert module.patch(module.patch(aht,3),3)==module.patch(aht,3)
try:module.patch('unexpected dependency',3)
except RuntimeError:pass
else:raise AssertionError('unsupported source accepted')
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory);(p/'test.cpp').write_text(source)
 exe=p/('test.exe' if os.name=='nt' else 'test')
 subprocess.run(json.loads(os.environ.get('CXX_JSON','["g++"]'))+['-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('PASS: AHT busy/read error, SHT NACK, BME calibration, LPS conversion/NACK timeout and recovery')
