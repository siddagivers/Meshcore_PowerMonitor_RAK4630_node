#include "LoRaOta.h"
#include <stdio.h>
#include <string.h>
#ifdef PM_LORA_OTA
#include "PowerMonitor.h"
#include "OtaTransfer.h"
#include "ota/OtaStoreQspiNrf52.h"
#include "ota/OtaVerify.h"
#include "ota/OtaBlInfo.h"
#include "ota/OtaByteIO.h"
#include <Utils.h>
#include <Arduino.h>
#include <InternalFileSystem.h>
#include <SHA256.h>
#include <memory>
#include <new>
#include <nrf.h>
#include <nrf_soc.h>
#include <nrf_sdm.h>
using namespace Adafruit_LittleFS_Namespace;
using namespace mesh::ota;
extern pm::PowerMonitor power_monitor;
namespace pm {
namespace {
using Store=OtaStoreQspiNrf52;
struct Session {
  Store store;
  OtaTransfer<Store> transfer;
  Session():transfer(store){}
};
// Allocate the two 4-KiB staging buffers only when the operator requests OTA.
std::unique_ptr<Session> session;
uint32_t applyAfter=0,applyLimit=0;
const char* applyResult="No activation attempted this boot; check pm version after reconnecting";
const char* HW="RAK4631_RAK15001_C";
const char* TRUST="/pm-ota.pub";
const char* PAIR="/pm-ota.pair";
struct Journal {uint32_t magic,total,next;uint8_t hash[32],checksum[32];};
const uint32_t JOURNAL_MAGIC=0x504D4F54;
bool readExact(const char* name,void* out,size_t size) {
  File f=InternalFS.open(name,FILE_O_READ);
  const bool ok=f && f.size()==size && f.read((uint8_t*)out,size)==(int)size;
  f.close();return ok;
}
bool writeExact(const char* name,const void* bytes,size_t size) {
  // A torn record fails its hash on reboot. Losing progress causes retransmit,
  // never approval of unchecked bytes. Never overwrite the energy snapshots.
  InternalFS.remove(name);
  File f=InternalFS.open(name,FILE_O_WRITE);
  bool ok=f && f.write((const uint8_t*)bytes,size)==size;f.close();
  uint8_t check[sizeof(Journal)];
  return ok && size<=sizeof(check) && readExact(name,check,size) && !memcmp(check,bytes,size);
}
void journalName(char name[20],uint32_t next) {snprintf(name,20,"/pm-ota.%u",(unsigned)((next/4096)&1));}
void checksum(Journal& j) {mesh::Utils::sha256(j.checksum,32,(const uint8_t*)&j,offsetof(Journal,checksum));}
bool save() {
  auto& t=session->transfer;
  if(!t.checkpoint())return false;
  Journal j{};j.magic=JOURNAL_MAGIC;j.total=t.total;j.next=t.durable;memcpy(j.hash,t.digest,32);checksum(j);
  char name[20];journalName(name,j.next);return writeExact(name,&j,sizeof(j));
}
bool ensureSession() {
  if(session)return true;
  session.reset(new(std::nothrow) Session);if(!session)return false;
  Journal best{};
  for(unsigned i=0;i<2;i++) {
    char name[20];snprintf(name,sizeof(name),"/pm-ota.%u",i);Journal j{};
    if(!readExact(name,&j,sizeof(j))||j.magic!=JOURNAL_MAGIC||j.total<210||j.total>720000||j.next>j.total)continue;
    uint8_t hash[32];memcpy(hash,j.checksum,32);checksum(j);
    if(memcmp(hash,j.checksum,32)==0 && j.next>=best.next)best=j;
  }
  if(best.magic==JOURNAL_MAGIC && session->store.reopenPartial(best.total)) {
    auto& t=session->transfer;t.total=best.total;t.next=t.durable=best.next;memcpy(t.digest,best.hash,32);
  }
  return true;
}
bool paired() {char value[24]={};return readExact(PAIR,value,strlen(HW))&&!memcmp(value,HW,strlen(HW));}
bool bootCompatible() {
  const auto caps=ota_bootloader_app_caps();
  // Conservative fixed profile: no internal-flash or automatic-storage fallback.
  return caps.present&&caps.apply_abi>=2&&(caps.codec_mask&1)&&(caps.storage_flags&OTA_BL_STORAGE_QSPI)
    &&*(const volatile uint16_t*)(uintptr_t)0x300C==0x00B6;
}
bool verify(char* reply,size_t cap) {
  auto& t=session->transfer;
  if(!t.complete()||!save()){snprintf(reply,cap,"Err incomplete/checkpoint");return false;}
  uint8_t key[32],raw[MOTA_MFL],header[8],hash[32],buffer[256];
  if(!readExact(TRUST,key,32)){snprintf(reply,cap,"Err provision signer over local USB first");return false;}
  SHA256 sha;
  for(uint32_t offset=0;offset<t.total;) {
    uint32_t size=t.total-offset;if(size>sizeof(buffer))size=sizeof(buffer);
    if(!session->store.read(offset,buffer,size)){snprintf(reply,cap,"Err flash read");return false;}
    sha.update(buffer,size);offset+=size;
  }
  sha.finalize(hash,32);
  if(memcmp(hash,t.digest,32)){snprintf(reply,cap,"Err container SHA256");return false;}
  if(!session->store.read(0,header,8)||memcmp(header,MOTA_MAGIC,4)||rd_u32le(header+4)!=t.total
    ||!session->store.read(8,raw,sizeof(raw))){snprintf(reply,cap,"Err container framing");return false;}
  MotaManifest m;
  uint8_t hardware[32]={};memcpy(hardware,HW,strlen(HW));
  const char* targetName="RAK4631_PM_RAK15001_C";
  uint8_t target[4];mesh::Utils::sha256(target,4,(const uint8_t*)targetName,strlen(targetName));
  if(!mota_parse_manifest(raw,sizeof(raw),m)||m.is_bootloader()||!m.is_full()||m.codec_id!=CODEC_FULL
    ||!m.is_signed()||m.image_size!=m.payload_size||m.image_size<64||m.image_size>712704
    ||m.target_id!=rd_u32le(target)||memcmp(m.hw_id,hardware,32)||memcmp(raw+MOTA_OFF_APPROVAL,APPROVAL_NOT,4)) {
    snprintf(reply,cap,"Err signed full image/profile/size required");return false;
  }
  SignerAllowlist allow;allow.add(key);
  const auto result=ota_verify(session->store,allow,raw);
  if(!result.auto_appliable()){snprintf(reply,cap,"Err signature/signer/Merkle/image verification");return false;}
  // Independently require sane application vectors and matching signed EndF.
  const uint32_t payload=8+MOTA_MFL+m.block_count*4;
  uint8_t vectors[8],endf[ENDF_LEN];
  if(!session->store.read(payload,vectors,8)||!session->store.read(payload+m.image_size-ENDF_LEN,endf,ENDF_LEN)) {
    snprintf(reply,cap,"Err vector/EndF read");return false;
  }
  uint32_t sp=rd_u32le(vectors),pc=rd_u32le(vectors+4);
  if(sp<0x20000000||sp>0x20040000||(sp&7)||!(pc&1)||pc<0x26001||pc>=0x26000+m.image_size
    ||memcmp(endf,ENDF_MAGIC,4)||rd_u32le(endf+4)!=m.image_size-ENDF_LEN
    ||rd_u32le(endf+20)!=m.target_id||memcmp(endf+24,m.hw_id,32)) {
    snprintf(reply,cap,"Err vectors/EndF/profile");return false;
  }
  SHA256 bodySha;
  for(uint32_t offset=0;offset<m.image_size-ENDF_LEN;) {
    uint32_t size=m.image_size-ENDF_LEN-offset;if(size>sizeof(buffer))size=sizeof(buffer);
    if(!session->store.read(payload+offset,buffer,size)){snprintf(reply,cap,"Err body read");return false;}
    bodySha.update(buffer,size);offset+=size;
  }
  bodySha.finalize(hash,32);
  if(memcmp(hash,endf+8,8)){snprintf(reply,cap,"Err EndF body hash");return false;}
  memcpy(hash,t.digest,32);
  t.verified=true;snprintf(reply,cap,"OK verified %02x%02x%02x%02x; apply requires explicit command",hash[0],hash[1],hash[2],hash[3]);return true;
}
}
bool otaCommand(const char* command,char* reply,size_t cap,bool local) {
  if(strncmp(command,"pm ota",6)|| (command[6]&&command[6]!=' '))return false;
  char copy[160];if(strlen(command)>=sizeof(copy)){snprintf(reply,cap,"Err command too long");return true;}
  strcpy(copy,command);char* state=nullptr;strtok_r(copy," ",&state);strtok_r(nullptr," ",&state);
  char* op=strtok_r(nullptr," ",&state);char* a=strtok_r(nullptr," ",&state);char* b=strtok_r(nullptr," ",&state);char* c=strtok_r(nullptr," ",&state);char* extra=strtok_r(nullptr," ",&state);
  snprintf(reply,cap,"Err pm ota status|begin|data|verify|apply|cancel; pair/trust local USB only");
  if(!op||extra)return true;
  if(!strcmp(op,"result")&&!a){snprintf(reply,cap,"%s",applyResult);return true;}
  if(!strcmp(op,"trust")||!strcmp(op,"pair")) {
    if(!local){snprintf(reply,cap,"Err provisioning is local USB only");return true;}
    if(!a||b)return true;
    applyAfter=0;applyResult="Provisioning changed; pending activation cancelled";if(session)session->transfer.verified=false;
    if(!strcmp(op,"pair")) {
      if(strcmp(a,HW)||!bootCompatible()||!ensureSession()||session->store.capacity()!=2097152){snprintf(reply,cap,"Err exact RAK15001_C/S140v6/QSPI OTAFIX pairing required");return true;}
      snprintf(reply,cap,writeExact(PAIR,HW,strlen(HW))?"OK paired":"Err pair persistence");
    } else {
      uint8_t key[32];if(!decodeHex(a,key,32))return true;
      snprintf(reply,cap,writeExact(TRUST,key,32)?"OK signer provisioned":"Err trust persistence");
    }
    return true;
  }
  if(!ensureSession()){snprintf(reply,cap,"Err insufficient heap");return true;}
  auto& t=session->transfer;
  if(!strcmp(op,"status")&&!a) {
    snprintf(reply,cap,"OTA cli1 pair=%u boot=%u flash=%lu next=%lu/%lu durable=%lu id=%02x%02x%02x%02x verified=%u",
      paired(),bootCompatible(),(unsigned long)session->store.capacity(),(unsigned long)t.next,(unsigned long)t.total,(unsigned long)t.durable,t.digest[0],t.digest[1],t.digest[2],t.digest[3],t.verified);return true;
  }
  if(!strcmp(op,"cancel")&&!a) {
    applyAfter=0;applyResult="Activation cancelled by operator";
    if(!session->store.discard()){snprintf(reply,cap,"Err discard failed");return true;}
    InternalFS.remove("/pm-ota.0");InternalFS.remove("/pm-ota.1");session.reset();snprintf(reply,cap,"OK cancelled");return true;
  }
  if(applyAfter){snprintf(reply,cap,"Err apply already armed");return true;}
  if(!paired()||!bootCompatible()){snprintf(reply,cap,"Err local pairing/compatible QSPI OTAFIX required");return true;}
  if(!strcmp(op,"begin")&&a&&b&&!c) {
    uint32_t size;uint8_t hash[32];if(!decodeNumber(a,size)||!decodeHex(b,hash,32))return true;
    // Remove stale journals BEFORE beginning a different image. No old resume
    // record may be attached to newly erased bytes, even after a power loss.
    if(t.total!=size||memcmp(hash,t.digest,32)||t.failed) {
      InternalFS.remove("/pm-ota.0");InternalFS.remove("/pm-ota.1");
    }
    if(!t.begin(size,hash)){snprintf(reply,cap,"Err begin: %s",session->store.last_error());return true;}
    snprintf(reply,cap,"OK begin next=%lu",(unsigned long)t.next);return true;
  }
  uint8_t tag[4];if(!a||!decodeHex(a,tag,4)||!t.matches(tag))return true;
  if(!strcmp(op,"data")&&b&&c) {
    uint32_t offset;uint8_t bytes[40];size_t len=strlen(c)/2;
    if(!decodeNumber(b,offset)||!len||len>40||!decodeHex(c,bytes,len))return true;
    if(!t.data(offset,bytes,len)){snprintf(reply,cap,"Err data next=%lu",(unsigned long)t.next);return true;}
    if((t.next/4096!=t.durable/4096||t.complete())&&!save()){t.failed=true;snprintf(reply,cap,"Err checkpoint");return true;}
    snprintf(reply,cap,"OK data next=%lu",(unsigned long)t.next);return true;
  }
  if(b)return true;
  if(!strcmp(op,"verify")){verify(reply,cap);return true;}
  if(!strcmp(op,"apply")) {
    if(!verify(reply,cap))return true;
    // Approval is written only at the actual reset, after the reply drains.
    applyAfter=millis()+10000;applyLimit=millis()+60000;
    applyResult="Activation armed; waiting for queue and in-flight transmission";
    snprintf(reply,cap,"OK apply armed %02x%02x%02x%02x; reset after reply drains",tag[0],tag[1],tag[2],tag[3]);return true;
  }
  return true;
}
void otaPoll(bool radioPending) {
  if(!applyAfter)return;
  if((int32_t)(millis()-applyLimit)>=0){applyAfter=0;applyResult="Activation cancelled: radio busy for 60 seconds";return;}
  if((int32_t)(millis()-applyAfter)<0||radioPending)return;
  applyAfter=0;
  uint8_t enabled=0;if(sd_softdevice_is_enabled(&enabled)!=NRF_SUCCESS){applyResult="Activation aborted: SoftDevice query";return;}
  if(!power_monitor.checkpointNow()){applyResult="Activation aborted: power-monitor checkpoint failed";return;}
  if(!paired()||!bootCompatible()||!session||!session->transfer.verified||!session->store.approve_for_bootloader()){applyResult="Activation aborted: pairing/verification/flash approval";return;}
  if(enabled) {
    if(sd_power_gpregret_clr(1,0xffffffff)!=NRF_SUCCESS||sd_power_gpregret_set(1,GPREGRET2_OTA_STAGE_QSPI)!=NRF_SUCCESS
      ||sd_power_gpregret_clr(0,0xffffffff)!=NRF_SUCCESS||sd_power_gpregret_set(0,GPREGRET_OTA_APPLY)!=NRF_SUCCESS){applyResult="Activation aborted: reset handoff";return;}
  }else{NRF_POWER->GPREGRET2=GPREGRET2_OTA_STAGE_QSPI;NRF_POWER->GPREGRET=GPREGRET_OTA_APPLY;}
  NVIC_SystemReset();
}
}
#else
namespace pm {
bool otaCommand(const char* command,char* reply,size_t cap,bool) {
  if(strncmp(command,"pm ota",6))return false;
  snprintf(reply,cap,"Err LoRa OTA not enabled in this profile");return true;
}
void otaPoll(bool){}
}
#endif
