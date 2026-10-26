#!/usr/bin/env python3
"""Pinned official meshcore-dev/MeshCore overlay, without LoRa OTA."""
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
    cli.add_argument("--version",default="0.3.0-local")
    cli.add_argument("--source-sha",default="unknown")
    args=cli.parse_args()
    for label,value in [("version",args.version),("SHA",args.source_sha)]:
        if not re.fullmatch(r"[a-zA-Z0-9.+_-]{1,64}",value):
            raise SystemExit(f"Invalid {label}")
    root=Path(__file__).resolve().parent.parent
    main_file=args.upstream/"examples/simple_repeater/main.cpp"
    text=main_file.read_text()
    text=replace_one(text,'#include "MyMesh.h"',
        '#include "MyMesh.h"\n#include "PowerMonitor.h"\npm::PowerMonitor power_monitor;',
        "main includes")
    text=replace_one(text,'  InternalFS.begin();',
        '  const bool pm_fs_ready=InternalFS.begin();',"filesystem initialization")
    text=replace_one(text,'  the_mesh.begin(fs);',
        '  the_mesh.begin(fs);\n  power_monitor.begin(pm_fs_ready);',"power monitor initialization")
    text=replace_one(text,'    reply[0] = 0;\n#ifdef ETHERNET_ENABLED',
        '    reply[0] = 0;\n    if (!power_monitor.handleCommand(command,reply,sizeof(reply))) {\n#ifdef ETHERNET_ENABLED',"local USB commands")
    text=replace_one(text,'#endif\n    if (reply[0]) {',
        '#endif\n    }\n    if (reply[0]) {',"local USB command block")
    text=replace_one(text,"  the_mesh.loop();\n  sensors.loop();",
        "  the_mesh.loop();\n  power_monitor.poll(millis(),rtc_clock.getCurrentTime());\n  sensors.loop();",
        "sensor polling")
    text=replace_one(text,'  if (the_mesh.getNodePrefs()->powersaving_enabled && !the_mesh.hasPendingWork()) {',
        '  // Continuous power sampling requires MCU uptime.\n  if (false && the_mesh.getNodePrefs()->powersaving_enabled && !the_mesh.hasPendingWork()) {',
        "disable long sleep")
    main_file.write_text(text)
    mesh_file=main_file.parent/"MyMesh.cpp"
    mesh_text=mesh_file.read_text()
    mesh_text=replace_one(mesh_text,'#include "MyMesh.h"',
        '#include "MyMesh.h"\n#include "PowerMonitor.h"\nextern pm::PowerMonitor power_monitor;',
        "telemetry includes")
    mesh_text=replace_one(mesh_text,'    sensors.querySensors(perm_mask, telemetry);',
        '    power_monitor.appendTelemetry(telemetry,perm_mask);\n    sensors.querySensors(perm_mask, telemetry);',
        "native telemetry response")
    # Upstream gates radio text CLI to authenticated admins. The hook follows
    # its optional companion prefix, preserving the reply prefix. Reset is
    # denied here even if a remote sender supplies a zero timestamp; only the
    # direct local USB hook above can reset energy counters.
    anchor='  // handle ACL related commands\n'
    hook='''  if (strncmp(command,"pm",2)==0 && (!command[2] || command[2]==' ')) {
    char* pm_end=command+strlen(command);
    while(pm_end>command && (pm_end[-1]==' ' || pm_end[-1]=='\\r' || pm_end[-1]=='\\n')) *--pm_end=0;
    if (strcmp(command,"pm reset YES")==0) {
      strcpy(reply,"Err - reset is local USB only");return;
    }
    if (power_monitor.handleCommand(command,reply,153))return;
  }
'''
    mesh_text=replace_one(mesh_text,anchor,hook+anchor,"on-demand admin diagnostics")
    mesh_file.write_text(mesh_text)
    for file in ("PowerMonitor.h","PowerMonitor.cpp","EnergyIntegrator.h","SolarHistory.h","PowerTelemetry.h"):
        shutil.copyfile(root/"firmware"/file,main_file.parent/file)
    # Generated for every build. Both source revision and numeric version are
    # accessible via local MeshCore USB CLI: pm version.
    header=main_file.parent/"PowerMonitorBuild.h"
    header.write_text('#pragma once\n#define PM_VERSION "'+args.version+'"\n#define PM_SOURCE_SHA "'+args.source_sha[:12]+'"\n')
    cpp=main_file.parent/"PowerMonitor.cpp"
    cpp.write_text('#include "PowerMonitorBuild.h"\n'+cpp.read_text())
    base="RAK_4631_repeater"
    ini=args.upstream/"variants/rak4631/platformio.ini"
    ini.write_text(ini.read_text() + (
        "\n; RAK4631 power monitor overlay (2 INA219 + MCP9808)\n"
        "[env:RAK_4631_repeater_power_monitor]\n"
        "extends = env:"+base+"\n"
        "platform = nordicnrf52@11.0.0\n"
        "board_build.ldscript = boards/nrf52840_s140_v6_extrafs.ld\n"
        "board_upload.maximum_size = 712704\n"
        "build_unflags = -Ofast\n"
        "  -D ENV_INCLUDE_INA260=1\n"
        "build_flags = ${env:"+base+".build_flags}\n"
        "  -Os\n"
        "  -DPM_SAMPLE_MS=20\n"
        "  -DPM_CHECKPOINT_MS=900000\n"
        "  -DPM_TEMPERATURE_MS=60000\n"
        "  -DPM_SOLAR_SHUNT_OHMS=0.100f\n"
        "  -DPM_LOAD_SHUNT_OHMS=0.100f\n"
        "  -DPM_SOLAR_SIGN=1\n"
        "  -DPM_LOAD_SIGN=1\n"
        "  -DENV_INCLUDE_INA260=0\n"
    ))
    print("Patched official MeshCore",args.version,"without LoRa OTA",args.upstream)

if __name__=="__main__":
    main()
