#include "PowerMonitorHelp.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
int main(){
 for(bool profile:{false,true}){
  char command[32],full[512],remote[153];
  for(unsigned i=1;i<=12;i++){
   snprintf(command,sizeof(command),"pm help %u",i);
   assert(pm::powerHelp(command,full,sizeof(full),profile));
   if(strlen(full)>152){printf("Help page too long: %u, %zu bytes\n",i,strlen(full));return 1;}
   assert(pm::powerHelp(command,remote,sizeof(remote),profile));assert(!strcmp(remote,full));
  }
  assert(pm::powerHelp("pm help",remote,sizeof(remote),profile));
  assert(pm::powerHelp("pm help 99",remote,sizeof(remote),profile));
  assert(!pm::powerHelp("pm ina off",remote,sizeof(remote),profile));
 }
 puts("PASS: both profiles' described help pages fit remote reply without truncation");
}
