#!/usr/bin/env python3
"""Compatibility entry point for the existing SIPRUN cron collector."""
import json
import os
import sys
from companion_rpc import call_sync,SOCKET

def main():
    args=sys.argv[1:]
    if len(args)!=4 or args[0] not in ('-s','--serial') or args[2] not in ('req_telemetry','reset_path','path'):
        raise SystemExit('Unsupported collector command; no serial access attempted')
    status=None
    if SOCKET.exists():
        try:status=call_sync({'op':'status'},timeout=3)
        except Exception:raise SystemExit('Shared companion is not responding; refusing a second serial connection')
        if not status['online'] and status.get('error')!='Waiting for the scheduled telemetry collection':
            raise SystemExit(status.get('error') or 'Companion handover in progress; retry shortly')
    if not status or not status['online']:
        # Before broker handover, preserve the existing collector exactly.
        # If the socket answers as online, never fall back to a second reader.
        os.execv('/home/pi/.local/bin/meshcli',['meshcli',*args])
    if os.path.realpath(args[1])!=os.path.realpath(status['port']):raise SystemExit('Collector port differs from the shared companion')
    op={'req_telemetry':'telemetry','reset_path':'reset_path','path':'route'}[args[2]]
    try:result=call_sync({'op':op,'target':args[3]},timeout=120)
    except Exception as error:raise SystemExit(str(error))
    print(json.dumps(result))

if __name__=='__main__':main()
