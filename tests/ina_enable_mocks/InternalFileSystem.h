#pragma once
#include <stdint.h>
#include <stddef.h>
#include <vector>
namespace Adafruit_LittleFS_Namespace {
constexpr int FILE_O_READ=0,FILE_O_WRITE=1;
struct MockFS;
struct File {MockFS* fs;bool valid;explicit operator bool()const{return valid;}int read();size_t write(const uint8_t*,size_t);void close(){}};
struct MockFS {
 bool present=false,failRemove=false,failWrite=false;std::vector<uint8_t> data;
 bool exists(const char*){return present;}
 bool remove(const char*){if(failRemove)return false;data.clear();present=false;return true;}
 File open(const char*,int mode){if(mode==FILE_O_WRITE){present=true;return {this,true};}return {this,present};}
};
inline int File::read(){return valid&&!fs->data.empty()?fs->data[0]:-1;}
inline size_t File::write(const uint8_t* p,size_t n){if(!valid||fs->failWrite)return 0;fs->data.insert(fs->data.end(),p,p+n);return n;}
}
inline Adafruit_LittleFS_Namespace::MockFS InternalFS;
