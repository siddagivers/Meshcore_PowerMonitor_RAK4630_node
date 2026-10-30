#include "OtaTransfer.h"
#include <vector>
#include <cassert>
#include <cstdio>
struct Store {
  std::vector<uint8_t> bytes;bool fail=false;
  bool begin(uint32_t n){bytes.assign(n,255);return true;}
  bool write(uint32_t off,const uint8_t* p,size_t n){if(fail)return false;memcpy(bytes.data()+off,p,n);return true;}
  bool read(uint32_t off,uint8_t* p,size_t n){memcpy(p,bytes.data()+off,n);return true;}
  bool finalize(){return !fail;}
};
int main() {
  Store s;pm::OtaTransfer<Store> t(s);uint8_t hash[32]={1},data[40]={7};
  assert(!t.begin(0,hash)&&!t.begin(UINT32_MAX,hash));assert(t.begin(240,hash));
  assert(!t.data(40,data,40));assert(t.data(0,data,40));assert(t.next==40);
  assert(t.data(0,data,40)&&t.next==40); // ACK loss: exact retransmit is idempotent
  data[0]=8;assert(!t.data(0,data,40));data[0]=7;
  assert(t.checkpoint()&&t.durable==40);assert(t.begin(240,hash)&&t.next==40);
  assert(!t.data(UINT32_MAX,data,40)&&!t.data(40,data,41));
  while(t.next<240){assert(t.data(t.next,data,40));}
  assert(t.complete());
  t.verified=true;assert(!t.data(200,data,40));
  hash[0]=2;assert(t.begin(240,hash)&&t.next==0&&!t.verified);
  s.fail=true;assert(!t.data(0,data,40)&&t.failed&&!t.complete());
  uint8_t out[2];assert(pm::decodeHex("fF01",out,2)&&out[0]==255&&out[1]==1);
  assert(!pm::decodeHex("ff0g",out,2)&&!pm::decodeHex("ff",out,2));
  uint32_t n;assert(pm::decodeNumber("4294967295",n)&&n==UINT32_MAX);
  assert(!pm::decodeNumber("4294967296",n)&&!pm::decodeNumber("-1",n));
  puts("PASS: OTA bounds, exact retransmission, conflict rejection, ordering, checkpoints and failed I/O");
}
