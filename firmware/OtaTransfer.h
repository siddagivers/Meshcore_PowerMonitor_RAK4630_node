#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace pm {
// Stop-and-wait transfer. No boot/flash activation belongs in this layer.
template<class Store> class OtaTransfer {
  Store& store_;
public:
  static const size_t CHUNK=40;
  uint32_t total=0,next=0,durable=0;
  uint8_t digest[32]={};
  bool verified=false,failed=false;
  explicit OtaTransfer(Store& store):store_(store){}
  bool begin(uint32_t size,const uint8_t hash[32]) {
    if(total && total==size && !memcmp(hash,digest,32) && !failed)return true;
    if(size<210 || size>720000 || !store_.begin(size))return false;
    total=size;next=durable=0;memcpy(digest,hash,32);verified=failed=false;return true;
  }
  bool matches(const uint8_t tag[4])const{return total && !memcmp(digest,tag,4);}
  bool data(uint32_t offset,const uint8_t* bytes,size_t len) {
    if(failed||verified||!total||!len||len>CHUNK||offset>total||len>total-offset)return false;
    if(offset<next) {
      uint8_t previous[CHUNK];
      return len<=next-offset && store_.read(offset,previous,len) && !memcmp(previous,bytes,len);
    }
    if(offset!=next)return false;
    if(!store_.write(offset,bytes,len)){failed=true;return false;}
    next+=len;
    return true;
  }
  bool checkpoint() {
    if(failed||!store_.finalize()){failed=true;return false;}
    durable=next;return true;
  }
  bool complete()const{return total && next==total && !failed;}
};
inline bool decodeHex(const char* text,uint8_t* out,size_t size) {
  if(strlen(text)!=size*2)return false;
  for(size_t i=0;i<size;i++) {
    unsigned value=0;
    for(size_t j=0;j<2;j++) {
      const char c=text[i*2+j];
      if(c>='0'&&c<='9')value=value*16+c-'0';
      else if(c>='a'&&c<='f')value=value*16+c-'a'+10;
      else if(c>='A'&&c<='F')value=value*16+c-'A'+10;
      else return false;
    }
    out[i]=(uint8_t)value;
  }
  return true;
}
inline bool decodeNumber(const char* text,uint32_t& out) {
  if(!*text)return false;
  uint64_t value=0;
  for(;*text;text++) {
    if(*text<'0'||*text>'9')return false;
    value=value*10+(*text-'0');if(value>UINT32_MAX)return false;
  }
  out=(uint32_t)value;return true;
}
}
