#pragma once
#include <stdint.h>
#include <string.h>
namespace pm {
static const char OTA_TARGET_NAME[]="RAK4631_PM_RAK15001_C_OTAFIX2412";
// Exact published 40-KiB bootloader from the official RAK4631 auto 2.4.12
// S140 6.1.1 combined DFU ZIP. Unknown/recovery builds are not equivalent.
static const uint8_t OTAFIX_2412_RAK4631_SHA256[32]={
  0xec,0x86,0x0f,0xb4,0x66,0x97,0xac,0x4b,0x45,0x8f,0x4b,0x96,0x1d,0xec,0x69,0xb4,
  0x28,0x38,0x0b,0xe1,0xce,0x31,0xa2,0x26,0xcf,0xf6,0x02,0x98,0xf3,0x28,0x15,0x45};
inline uint8_t selectOtaBootHandoff(bool present,uint16_t abi,uint16_t codecs,
                                   uint8_t storage,uint16_t softdevice,const uint8_t hash[32]) {
  if(!present||abi<2||!(codecs&1)||!(storage&4)||softdevice!=0x00B6||
     memcmp(hash,OTAFIX_2412_RAK4631_SHA256,32))return 0;
  // Unified RAK loader: 0x52 selects RAK15001 CS=P0.26.
  // 0x51 selects the separate W25Q16 CS=P0.31 and must never be used here.
  return 0x52;
}
}
