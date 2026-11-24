#pragma once
#include <stdio.h>
#include <string.h>
namespace pm {
class TelemetryPage {
public:
  enum Page {LIVE,POWER,ENVIRONMENT,COMBINED};
#if PM_SIDOROVO
  static constexpr Page bootPage=COMBINED;
#else
  static constexpr Page bootPage=LIVE;
#endif
  Page page=bootPage;
  bool live()const{return page==LIVE;}
  bool includePower()const{return page!=ENVIRONMENT;}
  bool includeEnvironment()const{return page!=POWER;}
  static const char* name(Page selected){
    switch(selected){
      case LIVE:return "live";
      case POWER:return "power";
      case ENVIRONMENT:return "environment";
      case COMBINED:return "combined";
    }
    return "unknown";
  }
  bool command(const char* c,char* out,size_t cap){
    if(strncmp(c,"pm telemetry",12)||(c[12]&&c[12]!=' '))return false;
    if(!strcmp(c,"pm telemetry live"))page=LIVE;
    else if(!strcmp(c,"pm telemetry power"))page=POWER;
    else if(!strcmp(c,"pm telemetry environment"))page=ENVIRONMENT;
#if PM_SIDOROVO
    else if(!strcmp(c,"pm telemetry combined"))page=COMBINED;
    else if(strcmp(c,"pm telemetry status")){snprintf(out,cap,"pm telemetry live|power|environment|combined|status; select page, then refresh app Telemetry");return true;}
#else
    else if(strcmp(c,"pm telemetry status")){snprintf(out,cap,"pm telemetry live|power|environment|status; select page, then refresh app Telemetry");return true;}
#endif
    snprintf(out,cap,"Telemetry page: %s. Refresh app Telemetry. Global until changed; reboot defaults to %s.",name(page),name(bootPage));return true;
  }
};
extern TelemetryPage telemetry_page;
}
