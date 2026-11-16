#include "TelemetryPage.h"
#include <cassert>
#include <cstdio>
int main(){
 pm::TelemetryPage p;char reply[153];
 assert(p.live()&&p.includePower()&&p.includeEnvironment());
 assert(!p.command("pm sensors",reply,sizeof(reply)));
 p.command("pm telemetry power",reply,sizeof(reply));assert(!p.live()&&p.includePower()&&!p.includeEnvironment());
 p.command("pm telemetry environment",reply,sizeof(reply));assert(!p.includePower()&&p.includeEnvironment());
 auto before=p.page;p.command("pm telemetry invalid",reply,sizeof(reply));assert(p.page==before);
 p.command("pm telemetry status",reply,sizeof(reply));assert(p.page==before);
 p.command("pm telemetry live",reply,sizeof(reply));assert(p.live());
 puts("PASS live/power/environment selection, validation and non-mutating status");
}
