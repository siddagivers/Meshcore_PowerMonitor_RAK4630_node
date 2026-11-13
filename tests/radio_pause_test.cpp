#include "RadioPause.h"
#include <cassert>
#include <cstdio>
int main(){
 pm::RadioPause p;char reply[153];
 assert(!p.command("get radio",reply,sizeof(reply),0));
 assert(p.command("radio off 40",reply,sizeof(reply),100));
 assert(p.poll(10099,false)==0);assert(p.poll(10100,true)==0);
 assert(p.poll(11100,false)==1&&p.paused);
 assert(p.poll(51099,false)==0);assert(p.poll(51100,false)==2&&!p.paused);
 p.command("radio off 0",reply,sizeof(reply),0);assert(!p.armed);
 p.command("radio off -1",reply,sizeof(reply),0);assert(!p.armed);
 p.command("radio off 86401",reply,sizeof(reply),0);assert(!p.armed);
 p.command("radio off 40junk",reply,sizeof(reply),0);assert(!p.armed);
 p.command("radio off",reply,sizeof(reply),0);assert(p.duration==180000);
 assert(p.poll(60000,true)==-1&&!p.armed&&!p.paused);
 p.command("radio off 40",reply,sizeof(reply),0xfffff000);
 assert(p.poll((uint32_t)(0xfffff000+10000u),false)==1);
 p.command("radio on",reply,sizeof(reply),10000);assert(p.poll(10000,false)==2&&!p.paused);
 p.command("radio off 40",reply,sizeof(reply),0);p.command("radio on",reply,sizeof(reply),100);
 assert(p.poll(11000,false)==0&&!p.armed);
 puts("PASS timed radio pause, TX/queue guard, acknowledgement delay, duration, invalid input, busy abort, early resume and millis wrap");
}
