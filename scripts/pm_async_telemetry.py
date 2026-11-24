"""Project-local deferred telemetry: sensor worker never touches radio or ACL."""
from pathlib import Path
import shutil

def patch(upstream,root,replace):
    folder=upstream/'examples/simple_repeater'
    for name in ('SensorRefresh.h','SensorRefresh.cpp'):
        shutil.copyfile(root/'firmware'/name,folder/name)
    header=folder/'MyMesh.h'
    text=header.read_text()
    text=replace(text,'  CayenneLPP telemetry;', '''  struct PendingTelemetry {
    bool active=false,flood=false,scoped=false;
    uint32_t timestamp=0;
    uint8_t key[32],secret[32],path[MAX_PATH_SIZE],path_len=0,hash_size=1,permissions=0;
    TransportKey scope;
  } pm_pending;
  CayenneLPP telemetry;''','pending telemetry storage')
    text=replace(text,'  int handleRequest(ClientInfo* sender,',
        '  bool pmQueueTelemetry(mesh::Packet*,ClientInfo*,const uint8_t*,uint32_t,const uint8_t*,size_t);\n  int handleRequest(ClientInfo* sender,','deferred request interface')
    text=replace(text,'public:', 'public:\n  void pmPollTelemetry();','telemetry poll interface')
    header.write_text(text)
    cpp=folder/'MyMesh.cpp';text=cpp.read_text()
    text=replace(text,'#include "PowerMonitor.h"','#include "PowerMonitor.h"\n#include "SensorRefresh.h"','sensor worker include')
    anchor='      int reply_len = handleRequest(client, timestamp, &data[4], len - 4);'
    text=replace(text,anchor,'''      if(data[4]==REQ_TYPE_GET_TELEMETRY_DATA) {
        if(len<6)return;
        if(pmQueueTelemetry(packet,client,secret,timestamp,&data[4],len-4)) {
          client->last_timestamp=timestamp;
          client->last_activity=getRTCClock()->getCurrentTime();
        }
        return;
      }
'''+anchor,'defer authenticated telemetry')
    # Validate before looking at the request tag, including malformed peers.
    text=replace(text,'  if (type == PAYLOAD_TYPE_REQ) { // request (from a Known admin client!)',
        '  if (type == PAYLOAD_TYPE_REQ) { // request (from a Known admin client!)\n    if(len<5)return;','request length guard')
    text+='''
bool MyMesh::pmQueueTelemetry(mesh::Packet* packet,ClientInfo* client,const uint8_t* secret,
                             uint32_t timestamp,const uint8_t* payload,size_t length) {
  if(length<2||pm_pending.active||pm::freshBusy())return false;
  uint8_t permissions=~payload[1];
  if((client->permissions&PERM_ACL_ROLE_MASK)==PERM_ACL_GUEST)permissions=0;
  pm_pending.timestamp=timestamp;pm_pending.flood=packet->isRouteFlood();pm_pending.permissions=client->permissions;
  memcpy(pm_pending.key,client->id.pub_key,32);memcpy(pm_pending.secret,secret,32);
  pm_pending.path_len=packet->path_len;pm_pending.hash_size=packet->getPathHashSize();
  mesh::Packet::writePath(pm_pending.path,packet->path,packet->path_len);
  pm_pending.scoped=recv_pkt_region && !recv_pkt_region->isWildcard()
    && region_map.getTransportKeysFor(*recv_pkt_region,&pm_pending.scope,1)>0;
  if(!pm_pending.scoped&&!default_scope.isNull()){
    pm_pending.scope=default_scope;pm_pending.scoped=true;
  }
  if(!pm::startFresh(sensors,permissions,pm::telemetry_page.page,getRTCClock()->getCurrentTime(),
                    board.getBattMilliVolts()/1000.0f,board.getMCUTemperature()))return false;
  pm_pending.active=true;return true;
}
void MyMesh::pmPollTelemetry(){
  if(!pm_pending.active)return;
  size_t length=0;
  if(!pm::collectFresh(reply_data+4,sizeof(reply_data)-4,length))return;
  pm_pending.active=false;
  ClientInfo* client=acl.getClient(pm_pending.key,32);
  if(!client||!client->permissions||client->permissions!=pm_pending.permissions||!length)return;
  memcpy(reply_data,&pm_pending.timestamp,4);length+=4;
  auto flood=[&](mesh::Packet* packet){
    if(!packet)return;
    if(pm_pending.scoped)sendFloodScoped(pm_pending.scope,packet,SERVER_RESPONSE_DELAY,pm_pending.hash_size);
    else sendFlood(packet,SERVER_RESPONSE_DELAY,pm_pending.hash_size);
  };
  if(pm_pending.flood){
    mesh::Packet* path=createPathReturn(client->id,pm_pending.secret,pm_pending.path,pm_pending.path_len,
                                      PAYLOAD_TYPE_RESPONSE,reply_data,length);
    if(path){flood(path);return;}
    flood(createPathReturn(client->id,pm_pending.secret,pm_pending.path,pm_pending.path_len,0,nullptr,0));
  }
  mesh::Packet* reply=createDatagram(PAYLOAD_TYPE_RESPONSE,client->id,pm_pending.secret,reply_data,length);
  if(!reply)return;
  if(!pm_pending.flood&&client->out_path_len!=OUT_PATH_UNKNOWN)
    sendDirect(reply,client->out_path,client->out_path_len,SERVER_RESPONSE_DELAY);
  else flood(reply);
}
'''
    cpp.write_text(text)
    main=folder/'main.cpp';text=main.read_text()
    text=replace(text,'#include "PowerMonitor.h"','#include "PowerMonitor.h"\n#include "SensorRefresh.h"','main worker include')
    text=replace(text,'  power_monitor.poll(millis(),rtc_clock.getCurrentTime());\n  sensors.loop();',
        '  if(!pm::radio_pause.paused)the_mesh.pmPollTelemetry();\n  if(!pm::freshBusy()){\n    power_monitor.poll(millis(),rtc_clock.getCurrentTime());\n    sensors.loop();\n  }','isolate I2C worker from main polling')
    text=replace(text,'  ui_task.loop();','  if(!pm::freshBusy())ui_task.loop();','isolate display I2C')
    ota_poll='pm::otaPoll(the_mesh.hasPendingWork() || the_mesh.hasActiveTransmission());'
    if ota_poll not in text:ota_poll='pm::otaPoll(the_mesh.hasPendingWork());'
    text=replace(text,ota_poll,
        'pm::otaPoll(the_mesh.hasPendingWork() || the_mesh.hasActiveTransmission() || pm::freshBusy());','defer activation checkpoint during sensor writes')
    main.write_text(text)
    patch_clock(upstream,replace)

def patch_clock(upstream,replace):
    # An installed external RTC also shares Wire. During a refresh, radio
    # timestamps use a mirrored advancing software clock; writes are deferred.
    clock=upstream/'src/helpers/AutoDiscoverRTCClock.h'
    text=clock.read_text()
    text=replace(text,'  mesh::RTCClock* _fallback;',
        '  mesh::RTCClock* _fallback;\n  bool pm_set_pending=false;\n  uint32_t pmReadCurrentTime();\n  void pmSetHardware(uint32_t);','isolated RTC interface')
    clock.write_text(text)
    clock=upstream/'src/helpers/AutoDiscoverRTCClock.cpp';text=clock.read_text()
    text=replace(text,'#include "AutoDiscoverRTCClock.h"',
        '#include "AutoDiscoverRTCClock.h"\nnamespace pm { bool freshBusy(); }','RTC worker guard')
    text=replace(text,'uint32_t AutoDiscoverRTCClock::getCurrentTime() {', '''uint32_t AutoDiscoverRTCClock::getCurrentTime() {
  if(pm::freshBusy())return _fallback->getCurrentTime();
  if(pm_set_pending){pmSetHardware(_fallback->getCurrentTime());pm_set_pending=false;}
  const uint32_t value=pmReadCurrentTime();
  // Never reset the software clock to its own truncated seconds on every
  // read: frequent reads would discard fractions and stop time advancing.
  if((ds3231_success||rv3028_success||rtc_8563_success||rtc_8130_success)
      &&value!=_fallback->getCurrentTime())_fallback->setCurrentTime(value);
  return value;
}
uint32_t AutoDiscoverRTCClock::pmReadCurrentTime() {''','RTC read isolation')
    text=replace(text,'void AutoDiscoverRTCClock::setCurrentTime(uint32_t time) {', '''void AutoDiscoverRTCClock::setCurrentTime(uint32_t time) {
  _fallback->setCurrentTime(time);
  if(pm::freshBusy()){pm_set_pending=true;return;}
  pmSetHardware(time);pm_set_pending=false;
}
void AutoDiscoverRTCClock::pmSetHardware(uint32_t time) {''','RTC write isolation')
    clock.write_text(text)
