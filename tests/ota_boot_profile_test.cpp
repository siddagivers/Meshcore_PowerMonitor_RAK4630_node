#include "OtaBootProfile.h"
#include "ota/OtaBlInfo.h"
#include <Utils.h>
#include <vector>
#include <fstream>
#include <iterator>
#include <cassert>
#include <cstdio>
int main(int argc,char** argv) {
  uint8_t hash[32];memcpy(hash,pm::OTAFIX_2412_RAK4631_SHA256,32);
  assert(pm::selectOtaBootHandoff(true,3,5,0x1e,0xb6,hash)==0x52);
  assert(!pm::selectOtaBootHandoff(false,3,5,0x1e,0xb6,hash));
  assert(!pm::selectOtaBootHandoff(true,1,5,0x1e,0xb6,hash));
  assert(!pm::selectOtaBootHandoff(true,3,4,0x1e,0xb6,hash));
  assert(!pm::selectOtaBootHandoff(true,3,5,0x0a,0xb6,hash));
  assert(!pm::selectOtaBootHandoff(true,3,5,0x1e,0x140,hash));
  hash[0]^=1;assert(!pm::selectOtaBootHandoff(true,3,5,0x1e,0xb6,hash));
  if(argc==2) {
    std::ifstream f(argv[1],std::ios::binary);std::vector<uint8_t> boot(std::istreambuf_iterator<char>(f),{});
    assert(boot.size()==40960);mesh::Utils::sha256(hash,32,boot.data(),boot.size());
    auto c=mesh::ota::ota_bl_app_caps_scan(boot.data(),boot.size());
    assert(pm::selectOtaBootHandoff(c.present,c.apply_abi,c.codec_mask,c.storage_flags,0xb6,hash)==0x52);
    printf("PASS exact published bootloader: ABI=%u codec=%x storage=%x handoff=52\n",c.apply_abi,c.codec_mask,c.storage_flags);
  }
  puts("PASS: exact bootloader hash, SoftDevice and capability gates; RAK15001 selector 52; mismatches rejected");
}
