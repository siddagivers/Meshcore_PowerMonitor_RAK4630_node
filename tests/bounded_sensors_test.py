from pathlib import Path
import importlib.util, subprocess, tempfile
spec=importlib.util.spec_from_file_location('bounded',Path(__file__).resolve().parents[1]/'scripts/pm_bounded_sensors.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
aht='bool aht(){'+('while (getStatus() & AHTX0_STATUS_BUSY) { delay(10); }'*3)+'return true;}'
sht='bool sht(){uint8_t readbuffer[6]; while (!i2c_dev->read(readbuffer, sizeof(readbuffer))) { delay(1); } return true;}'
source=r'''
#include <stdint.h>
#include <cassert>
#define AHTX0_STATUS_BUSY 0x80
uint32_t ticks=0; int mode=0;
uint32_t millis(){return ticks;}
void delay(unsigned n){ticks+=n;}
uint8_t getStatus(){return mode==0?0:mode==1?0xff:0x80;}
struct Device {bool read(uint8_t*,unsigned){return mode==0;}} device;
Device* i2c_dev=&device;
'''+module.patch(aht,3)+module.patch(sht,1)+r'''
int main(){assert(aht());assert(sht());mode=1;ticks=0;assert(!aht());assert(ticks==0);
ticks=0;assert(!sht());assert(ticks==500);mode=2;ticks=0;assert(!aht());assert(ticks==500);
mode=0;assert(aht());assert(sht());}
'''
assert module.patch(module.patch(aht,3),3)==module.patch(aht,3)
try:module.patch('unexpected dependency',3)
except RuntimeError:pass
else:raise AssertionError('unsupported source accepted')
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory);(p/'test.cpp').write_text(source)
 subprocess.run(['g++','-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: AHT read error, permanent busy, SHT NACK, recovery, idempotence and source guard')
