#include "ota/OtaVerify.h"
#include <vector>
#include <fstream>
#include <iterator>
#include <cassert>
#include <cstdio>
using namespace mesh::ota;
struct Store:OtaStore {
  std::vector<uint8_t> data;
  bool begin(uint32_t)override{return false;}
  bool write(uint32_t,const uint8_t*,uint32_t)override{return false;}
  bool read(uint32_t o,uint8_t* b,uint32_t n)const override{if((uint64_t)o+n>data.size())return false;memcpy(b,data.data()+o,n);return true;}
  uint32_t capacity()const override{return data.size();}
  uint32_t staged_size()const override{return data.size();}
  void clear()override{}
};
int main(int argc,char** argv) {
  assert(argc==2);std::ifstream f(argv[1],std::ios::binary);Store store;
  store.data=std::vector<uint8_t>(std::istreambuf_iterator<char>(f),{});
  assert(store.data.size()>1000);SignerAllowlist allow;allow.add(store.data.data()+8+97);
  assert(ota_verify(store,allow).auto_appliable());
  SignerAllowlist empty;assert(!ota_verify(store,empty).auto_appliable());
  store.data[8+129]^=1;assert(!ota_verify(store,allow).auto_appliable());store.data[8+129]^=1;
  store.data[store.data.size()-6]^=1;assert(!ota_verify(store,allow).auto_appliable());store.data[store.data.size()-6]^=1;
  store.data[205]^=1;assert(!ota_verify(store,allow).auto_appliable());store.data[205]^=1;
  store.data.pop_back();assert(!ota_verify(store,allow).auto_appliable());
  puts("PASS: actual device streaming verifier accepts signed package; rejects untrusted signer, signature/data/Merkle damage and truncation");
}
