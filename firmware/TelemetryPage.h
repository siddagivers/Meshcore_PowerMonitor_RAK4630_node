#pragma once
#include <stdio.h>
#include <string.h>
namespace pm {
class TelemetryPage {
public:
  enum Page {LIVE,POWER,ENVIRONMENT};
#if PM_SIDOROVO
  static constexpr Page bootPage=POWER;
#else
  static constexpr Page bootPage=LIVE;
#endif
  Page page=bootPage;
  bool live()const{return page==LIVE;}
  bool includePower()const{return page!=ENVIRONMENT;}
  bool includeEnvironment()const{return page!=POWER;}
  bool command(const char* c,char* out,size_t cap){
    if(strncmp(c,"pm telemetry",12)||(c[12]&&c[12]!=' '))return false;
    if(!strcmp(c,"pm telemetry live"))page=LIVE;
    else if(!strcmp(c,"pm telemetry power"))page=POWER;
    else if(!strcmp(c,"pm telemetry environment"))page=ENVIRONMENT;
    else if(strcmp(c,"pm telemetry status")){snprintf(out,cap,"pm telemetry live|power|environment|status; select page, then refresh app Telemetry");return true;}
    snprintf(out,cap,"Telemetry page: %s. Refresh app Telemetry. Global until changed; reboot defaults to %s.",page==LIVE?"live (latest INA + environment)":page==POWER?"power (all INA windows)":"environment",bootPage==POWER?"power":"live");return true;
  }
};
extern TelemetryPage telemetry_page;
}
