"""OTA adapter for the single-owner companion broker; no direct serial opens."""
import re
import sys
from companion_rpc import call

async def upload(args,blob,metadata):
    tag=metadata['sha256'][:8]
    status=await call({'op':'status'})
    if not status['online']:raise RuntimeError(status['error'])
    info=await call({'op':'route','target':args.target})
    contact=info['contact']
    if contact['public_key'].lower()!=args.target.lower():raise ValueError('Exact target public key required')
    if contact.get('out_path_len',-1)<0:raise ValueError('Learn a route before uploading; no automatic flooding')
    import json,getpass
    print('PM_ROUTE '+json.dumps(info['route']),flush=True)
    password=sys.stdin.readline().rstrip('\r\n') if getattr(args,'password_stdin',False) else getpass.getpass('Repeater admin password: ')
    print('Waiting for companion: telemetry and other requests finish before OTA continues.',flush=True)
    result=await call({'op':'login','target':args.target,'password':password},timeout=600)
    password=None
    if not result['logged_in']:raise RuntimeError('Admin login failed')
    async def command(text):
        result=await call({'op':'admin','target':args.target,'command':text,'pace':args.pace},timeout=600)
        return result['reply']
    status=await command('pm ota status');print(status,flush=True)
    if 'pair=1 boot=1 flash=2097152' not in status:raise RuntimeError('Target is not paired with compatible flash/bootloader')
    reply=await command(f"pm ota begin {len(blob)} {metadata['sha256']}")
    match=re.fullmatch(r'OK begin next=(\d+)',reply)
    if not match:raise RuntimeError(reply)
    offset=int(match[1])
    if not 0<=offset<=len(blob):raise RuntimeError('Invalid resume offset')
    print(f'PM_PROGRESS {offset} {len(blob)}',flush=True)
    while offset<len(blob):
        data=blob[offset:offset+40]
        reply=await command(f'pm ota data {tag} {offset} {data.hex()}')
        if reply!=f'OK data next={offset+len(data)}':raise RuntimeError(reply)
        offset+=len(data);print(f'PM_PROGRESS {offset} {len(blob)}',flush=True)
        if offset%4000<40 or offset==len(blob):print(f'{offset}/{len(blob)} bytes',flush=True)
    reply=await command(f'pm ota verify {tag}');print(reply,flush=True)
    if not reply.startswith('OK verified '):raise RuntimeError(reply)
    if args.apply:
        reply=await command(f'pm ota apply {tag}');print(reply,flush=True)
        if not reply.startswith('OK apply armed '):raise RuntimeError(reply)
        print('Activation requested. Reconnect and check pm version.',flush=True)
    else:print(f'Staged and verified; not activated. Explicit admin command: pm ota apply {tag}',flush=True)
