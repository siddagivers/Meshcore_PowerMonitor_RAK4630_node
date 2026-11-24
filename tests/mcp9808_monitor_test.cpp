#include "Mcp9808Monitor.h"
#include <cassert>
#include <cstdio>
int main(){
  pm::Mcp9808Monitor m;
  bool connected=false;unsigned reads=0,writes=0;uint16_t raw=0x0190;
  auto read=[&](uint8_t address,uint8_t reg,uint16_t& out){
    assert(address==0x18);++reads;if(!connected)return false;
    out=reg==6?0x54:reg==7?0x0400:reg==1?0x0100:raw;return true;
  };
  auto write=[&](uint8_t address,uint8_t reg,uint16_t v){
    assert(address==0x18&&reg==1&&v==0);++writes;return connected;
  };
  m.tick(0,read,write);assert(!m.valid&&!m.detected&&m.errors==1);
  for(unsigned now=1;now<10000;++now)m.tick(now,read,write);
  assert(reads==1); // absent sensor never monopolizes the main loop
  connected=true;m.tick(10000,read,write);assert(m.detected&&!m.valid&&writes==1);
  m.tick(10299,read,write);assert(!m.valid);
  m.tick(10300,read,write);assert(m.valid&&m.temperature==25&&m.last==10300);
  unsigned old=reads;m.tick(70299,read,write);assert(reads==old);
  connected=false;m.tick(70300,read,write);assert(!m.valid&&!m.detected&&m.errors==2);
  m.tick(80299,read,write);assert(reads==old+1);
  connected=true;m.tick(80300,read,write);m.tick(80600,read,write);assert(m.valid);
  raw=0x1ff0;m.tick(140600,read,write);assert(m.valid&&m.temperature==-1);
  raw=0x0800;m.tick(200600,read,write);assert(!m.valid); // out-of-range rejected
  pm::Mcp9808Monitor wrap;
  raw=0x0190;wrap.tick(0xffffff80u,read,write);wrap.tick(172,read,write);assert(wrap.valid);
  puts("PASS MCP missing/reconnect, wake delay, read cadence, invalidation, signed temperature and clock wrap");
}
