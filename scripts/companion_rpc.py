"""Local, owner-only companion broker protocol. Never logs request bodies."""
import asyncio
import json
import os
from pathlib import Path
import socket

SOCKET=Path(os.environ.get('PM_COMPANION_SOCKET',str(Path.home()/'.local/share/meshcore-inbox/companion.sock')))

async def call(request,timeout=180):
    reader,writer=await asyncio.open_unix_connection(str(SOCKET),limit=1_000_000)
    try:
        writer.write(json.dumps(request).encode()+b'\n');await writer.drain()
        raw=await asyncio.wait_for(reader.readline(),timeout)
        result=json.loads(raw)
        if not result.get('ok'):raise RuntimeError(result.get('error','Companion request failed'))
        return result['result']
    finally:
        writer.close();await writer.wait_closed()

def call_sync(request,timeout=180):
    return asyncio.run(call(request,timeout))
