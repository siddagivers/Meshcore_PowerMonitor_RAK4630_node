#pragma once
#include <InternalFileSystem.h>
namespace pm {
using namespace Adafruit_LittleFS_Namespace;
inline bool loadInaEnabled(bool fs){
  if(!fs)return true;
  auto f=InternalFS.open("/pm-ina.enable",FILE_O_READ);
  if(!f)return true;int value=f.read();f.close();return value!=0;
}
inline bool saveInaEnabled(bool fs,bool enabled){
  if(!fs)return false;
  if(InternalFS.exists("/pm-ina.enable")&&!InternalFS.remove("/pm-ina.enable"))return false;
  auto f=InternalFS.open("/pm-ina.enable",FILE_O_WRITE);
  uint8_t value=enabled?1:0;bool ok=f&&f.write(&value,1)==1;f.close();
  return ok&&loadInaEnabled(fs)==enabled;
}
}
