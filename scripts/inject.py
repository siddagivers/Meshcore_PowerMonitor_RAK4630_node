#!/usr/bin/env python3
"""Strict pinned-upstream overlay for a MeshCore RAK4631 energy monitor."""
from pathlib import Path
import argparse
import re
import shutil

def replace_one(source, anchor, replacement, label):
    count = source.count(anchor)
    if count != 1:
        raise RuntimeError(f"Upstream integration changed ({label}: {count} matches)")
    return source.replace(anchor, replacement, 1)

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("upstream",type=Path)
    cli.add_argument("--storage",choices=["rak15001","w25q16","unified"],default="rak15001")
    cli.add_argument("--version",default="0.1.0-local")
    cli.add_argument("--source-sha",default="unknown")
    args=cli.parse_args()
    for label,value in [("version",args.version),("SHA",args.source_sha)]:
        if not re.fullmatch(r"[a-zA-Z0-9.+_-]{1,64}",value):
            raise SystemExit(f"Invalid {label}")
    root=Path(__file__).resolve().parent.parent
    main_file=args.upstream/"examples/simple_repeater/main.cpp"
    text=main_file.read_text()
    text=replace_one(text,'#include "MyMesh.h"',
        '#include "MyMesh.h"\n#include "PowerMonitor.h"\nstatic pm::PowerMonitor power_monitor;',
        "main includes")
    text=replace_one(text,'  sensors.begin();\n  mesh::hilStartupTrace("sensors_ready");',
        '  sensors.begin();\n  power_monitor.begin(!volatile_primary_fs);\n  mesh::hilStartupTrace("sensors_ready");',
        "sensor setup")
    needle='    char reply[160];\n    reply[0] = 0;\n    if (strlen(command) == static_cast<size_t>(len))'
    repl='''    char reply[160];
    reply[0] = 0;
    if (power_monitor.handleCommand(command,reply,sizeof(reply))) {
      console.printf("  -> %s\\r\\n",reply);
      command[0]=0;
      return;
    }
    if (strlen(command) == static_cast<size_t>(len))'''
    text=replace_one(text,needle,repl,"serial CLI")
    needle='void loop() {\n  mesh::serviceUsbLoggingPort();'
    repl='''static bool publishPowerReport(const char* message) {
  // Use MeshCore's own encrypted Repeaters group and duty-cycle-aware queue.
  char cmd[182];
  const int n=snprintf(cmd,sizeof(cmd),"send text.flood %s",message);
  if(n<0 || n>=(int)sizeof(cmd))return false;
  char reply[160]={};
  the_mesh.handleUsbCommand(cmd,reply);
  return strncmp(reply,"OK",2)==0;
}
void loop() {
  mesh::serviceUsbLoggingPort();'''
    text=replace_one(text,needle,repl,"MeshCore report hook")
    text=replace_one(text,"  the_mesh.loop();\n  sensors.loop();",
        "  the_mesh.loop();\n  power_monitor.poll(millis(),rtc_clock.getCurrentTime(),publishPowerReport);\n  sensors.loop();",
        "sensor polling")
    text=replace_one(text,"  if (can_power_save) {\n    uint32_t sleep_secs =",
        "  // The high-rate diagnostic sampler requires MCU uptime.\n  can_power_save=false;\n  if (can_power_save) {\n    uint32_t sleep_secs =",
        "disable long sleep")
    main_file.write_text(text)
    for file in ("PowerMonitor.h","PowerMonitor.cpp","EnergyIntegrator.h"):
        shutil.copyfile(root/"firmware"/file,main_file.parent/file)
    # Generated for every build. Both source revision and numeric version are
    # accessible via local MeshCore USB CLI: pm version.
    header=main_file.parent/"PowerMonitorBuild.h"
    header.write_text('#pragma once\n#define PM_VERSION "'+args.version+'"\n#define PM_SOURCE_SHA "'+args.source_sha[:12]+'"\n')
    cpp=main_file.parent/"PowerMonitor.cpp"
    cpp.write_text('#include "PowerMonitorBuild.h"\n'+cpp.read_text())
    bases={
        "rak15001":"RAK_4631_repeater_rak15001_slot_c_lora_ota",
        "w25q16":"RAK_4631_repeater_w25q16_lora_ota",
        "unified":"RAK_4631_repeater_unified_lora_ota",
    }
    base=bases[args.storage]
    ini=args.upstream/"variants/rak4631/platformio.ini"
    ini.write_text(ini.read_text() + (
        "\n; RAK4631 power monitor overlay (2 INA219 + MCP9808)\n"
        "[env:RAK_4631_repeater_power_monitor]\n"
        "extends = env:"+base+"\n"
        "build_flags = ${env:"+base+".build_flags}\n"
        "  -DPM_SAMPLE_MS=20\n"
        "  -DPM_REPORT_MS=900000\n"
        "  -DPM_TEMPERATURE_MS=60000\n"
        "  -DPM_SOLAR_SHUNT_OHMS=0.100f\n"
        "  -DPM_LOAD_SHUNT_OHMS=0.100f\n"
        "  -DPM_SOLAR_SIGN=1\n"
        "  -DPM_LOAD_SIGN=1\n"
        "  -UENV_INCLUDE_INA260\n"
        "  -DENV_INCLUDE_INA260=0\n"
    ))
    print("Patched MeshCore",args.version,"storage",args.storage,"upstream",args.upstream)

if __name__=="__main__":
    main()
