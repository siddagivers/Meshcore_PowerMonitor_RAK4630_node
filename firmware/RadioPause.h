#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
namespace pm {
class RadioPause {
public:
  bool paused=false,armed=false,resume=false,failed=false;
  uint32_t scheduled=0,until=0,duration=0;
  bool command(const char* c,char* out,size_t cap,uint32_t now){
    if(!strcmp(c,"radio on")){
      armed=false;resume=paused;failed=false;snprintf(out,cap,"OK radio resume requested; pending pause cancelled");return true;}
    if(!strcmp(c,"radio status")){
      if(failed)snprintf(out,cap,"Radio pause/resume error; inspect locally; radio on retries resume");
      else if(paused)snprintf(out,cap,"Radio OFF; auto-resume in %lus",(unsigned long)((int32_t)(until-now)>0?(uint32_t)(until-now)/1000:0));
      else snprintf(out,cap,"Radio ON%s",armed?"; pause pending (10s delay, waiting for traffic to drain)":"");return true;}
    if(!strcmp(c,"radio help")){snprintf(out,cap,"radio off [1..86400 seconds] (default 180): pause after 10s/drain; radio on: resume/cancel; radio status. USB remains active.");return true;}
    if(strncmp(c,"radio off",9)|| (c[9]&&c[9]!=' '))return false;
    unsigned long seconds=180;char extra;
    if(c[9] && (sscanf(c+10,"%lu %c",&seconds,&extra)!=1 || seconds<1 || seconds>86400)){
      snprintf(out,cap,"Err use radio off [1..86400 seconds]");return true;}
    duration=(uint32_t)seconds*1000;failed=false;resume=false;
    if(paused){until=now+duration;snprintf(out,cap,"OK radio remains off for %lus from now",seconds);}
    else{armed=true;scheduled=now;snprintf(out,cap,"OK radio OFF in >=10s for %lus; waits for queue/TX, cancels if busy 60s",seconds);}
    return true;
  }
  int poll(uint32_t now,bool busy){
    if(paused&&(resume||(int32_t)(now-until)>=0)){resume=false;paused=false;return 2;}
    if(!armed)return 0;
    if((uint32_t)(now-scheduled)>=60000){armed=false;failed=true;return -1;}
    if((uint32_t)(now-scheduled)<10000||busy)return 0;
    armed=false;paused=true;until=now+duration;return 1;
  }
};
extern RadioPause radio_pause;
}
