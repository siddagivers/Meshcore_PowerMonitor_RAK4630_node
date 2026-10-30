#!/usr/bin/env python3
"""Signed full-image OTA packages and paced stock-MeshCore admin-CLI upload."""
import argparse
import asyncio
import getpass
import hashlib
import json
from pathlib import Path
import re
import struct
import time

HW=b"RAK4631_RAK15001_C".ljust(32,b"\0")
TARGET=int.from_bytes(hashlib.sha256(b"RAK4631_PM_RAK15001_C").digest()[:4],"little")
MAX_IMAGE=712704
BLOCK=2048

def h(data):return hashlib.sha256(data).digest()

def root_hash(leaves):
    while len(leaves)>1:
        leaves=[h(leaves[i]+leaves[i+1])[:4] if i+1<len(leaves) else leaves[i] for i in range(0,len(leaves),2)]
    return leaves[0]

def pack_image(body,version,key):
    """Append exact hardware identity; sign manifest; never sign a bootloader."""
    if len(body)<64 or len(body)+56>MAX_IMAGE:raise ValueError("application size outside profile")
    sp,pc=struct.unpack_from("<II",body)
    if not 0x20000000<=sp<=0x20040000 or sp%8 or not pc&1 or not 0x26000<pc<0x26000+len(body):
        raise ValueError("invalid S140v6 application vectors")
    image=body+b"EndF"+struct.pack("<I",len(body))+h(body)[:8]+struct.pack("<II",version,TARGET)+HW
    leaves=[h(image[i:i+BLOCK])[:4] for i in range(0,len(image),BLOCK)]
    from cryptography.hazmat.primitives import serialization
    public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    manifest=struct.pack("<BBBIIIIB",2,3,0x12,TARGET,version,len(image),len(image),11)
    manifest+=root_hash(leaves)+h(image)+b"\0"+HW+b"\0"*8+public
    assert len(manifest)==129
    manifest+=key.sign(manifest)+b"\xff"*4
    payload=manifest+b"".join(leaves)+image+b"vk496"
    return b"mOTA"+struct.pack("<I",len(payload)+8)+payload

def inspect_package(data):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if len(data)<210 or data[:4]!=b"mOTA" or struct.unpack_from("<I",data,4)[0]!=len(data) or data[-5:]!=b"vk496":
        raise ValueError("invalid framing")
    m=data[8:205]
    fmt,flags,algo,target,version,size,payload,log2=struct.unpack_from("<BBBIIIIB",m)
    if (fmt,flags,algo,target,log2)!=(2,3,0x12,TARGET,11) or m[56]!=0 or m[57:89]!=HW or m[193:]!=b"\xff"*4:
        raise ValueError("wrong profile, codec, unsigned or already approved")
    if not 64<=size<=MAX_IMAGE or payload!=size:raise ValueError("invalid image size")
    count=(payload+BLOCK-1)//BLOCK
    start=205+count*4
    if start+size+5!=len(data):raise ValueError("invalid layout")
    image=data[start:-5]
    leaves=[h(image[i:i+BLOCK])[:4] for i in range(0,len(image),BLOCK)]
    if b"".join(leaves)!=data[205:start] or root_hash(leaves)!=m[20:24] or h(image)!=m[24:56]:
        raise ValueError("Merkle/image hash mismatch")
    Ed25519PublicKey.from_public_bytes(m[97:129]).verify(m[129:193],m[:129])
    endf=image[-56:]
    if endf!=b"EndF"+struct.pack("<I",len(image)-56)+h(image[:-56])[:8]+struct.pack("<II",version,TARGET)+HW:
        raise ValueError("invalid EndF")
    return {"bytes":len(data),"image_bytes":size,"sha256":h(data).hex(),"signer":m[97:129].hex(),"target":hex(target),"version":version}

class Radio:
    def __init__(self,mc,contact,timeout=60,retries=5,pace=2):
        self.mc,self.contact=mc,contact
        self.timeout,self.retries,self.pace=timeout,retries,pace
        self.sequence=0;self.last_send=0

    async def request(self,command):
        from meshcore import EventType
        for attempt in range(self.retries):
            # Respect upstream monotonic-second replay checks without sending
            # timestamps ahead of wall time. One request at a time; no floods.
            await asyncio.sleep(max(0,self.last_send+self.pace-time.time()))
            self.sequence=(self.sequence+1)%65536
            alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
            prefix=alphabet[(self.sequence//62)%62]+alphabet[self.sequence%62]+"|"
            loop=asyncio.get_running_loop();received=loop.create_future()
            def callback(event):
                text=event.payload.get("text","")
                if text.startswith(prefix) and not received.done():received.set_result(text[3:])
            sub=self.mc.subscribe(EventType.CONTACT_MSG_RECV,callback,
                {"pubkey_prefix":self.contact["public_key"][:12]})
            try:
                result=await self.mc.commands.send_cmd(self.contact,prefix+command)
                self.last_send=time.time()
                if result is None or result.type==EventType.ERROR:raise TimeoutError("companion send rejected")
                response=await asyncio.wait_for(received,self.timeout)
                return response
            except (TimeoutError,asyncio.TimeoutError):
                if attempt+1==self.retries:raise TimeoutError(f"No reply after {self.retries} attempts; rerun to resume")
                await asyncio.sleep(min(5*(attempt+1),30))
            finally:sub.unsubscribe()

async def upload(args):
    from meshcore import MeshCore,EventType
    blob=args.image.read_bytes();metadata=inspect_package(blob)
    tag=metadata["sha256"][:8]
    mc=await MeshCore.create_serial(args.port,115200)
    try:
        await mc.commands.get_contacts()
        contact=mc.get_contact_by_key_prefix(args.target.lower())
        if not contact or contact["public_key"].lower()!=args.target.lower():raise ValueError("exact target public key must exist in companion contacts")
        if contact.get("out_path_len",-1) in (-1,255):raise ValueError("Learn a direct/repeater route first; uploader does not flood or reset routes")
        password=getpass.getpass("Repeater admin password: ")
        if not await mc.commands.send_login_sync(contact,password,min_timeout=30):raise RuntimeError("admin login failed")
        password=None
        await mc.start_auto_message_fetching()
        radio=Radio(mc,contact,args.timeout,args.retries,args.pace)
        status=await radio.request("pm ota status");print(status)
        if "pair=1 boot=1 flash=2097152" not in status:raise RuntimeError("Target is not paired with compatible RAK15001/OTAFIX")
        reply=await radio.request(f"pm ota begin {len(blob)} {metadata['sha256']}")
        match=re.fullmatch(r"OK begin next=(\d+)",reply)
        if not match:raise RuntimeError(reply)
        offset=int(match[1])
        if not 0<=offset<=len(blob):raise RuntimeError("invalid remote resume offset")
        while offset<len(blob):
            data=blob[offset:offset+40]
            response=await radio.request(f"pm ota data {tag} {offset} {data.hex()}")
            if response!=f"OK data next={offset+len(data)}":raise RuntimeError(response)
            offset+=len(data)
            if offset%4000<40 or offset==len(blob):print(f"{offset}/{len(blob)} bytes")
        response=await radio.request(f"pm ota verify {tag}");print(response)
        if not response.startswith("OK verified "):raise RuntimeError(response)
        if args.apply:
            response=await radio.request(f"pm ota apply {tag}");print(response)
            if not response.startswith("OK apply armed "):raise RuntimeError(response)
            print("Activation requested. Reconnect and check pm version; this reply does not prove installation succeeded.")
        else:print(f"Staged and verified; not activated. Explicit admin command: pm ota apply {tag}")
    finally:await mc.disconnect()

def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest="action",required=True)
    keygen=commands.add_parser("keygen");keygen.add_argument("key",type=Path)
    pack=commands.add_parser("pack");pack.add_argument("binary",type=Path);pack.add_argument("manifest",type=Path);pack.add_argument("key",type=Path);pack.add_argument("output",type=Path)
    inspect=commands.add_parser("inspect");inspect.add_argument("image",type=Path)
    send=commands.add_parser("upload");send.add_argument("image",type=Path);send.add_argument("--port",required=True);send.add_argument("--target",required=True)
    send.add_argument("--timeout",type=float,default=60);send.add_argument("--retries",type=int,default=5);send.add_argument("--pace",type=float,default=2)
    send.add_argument("--apply",action="store_true",help="Explicitly activate after verification; default only stages")
    args=parser.parse_args()
    if args.action=="keygen":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        key=Ed25519PrivateKey.generate()
        # Exclusive create; do not replace existing identity or print secrets.
        import os
        fd=os.open(args.key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f:f.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        print("Public signer:",key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex())
    elif args.action=="pack":
        from cryptography.hazmat.primitives import serialization
        manifest=json.loads(args.manifest.read_text());body=args.binary.read_bytes()
        expected=manifest["firmware"][args.binary.name]
        if not manifest.get("lora_ota") or manifest.get("ota_storage")!="RAK15001 slot C; JEDEC C84015" or expected["sha256"]!=h(body).hex():raise ValueError("Not a hash-matching OTA-profile application")
        numbers=[int(n) for n in manifest["version"].split("-")[0].split(".")]
        if len(numbers)!=3 or any(not 0<=n<=255 for n in numbers):raise ValueError("invalid version")
        version=(numbers[0]<<24)|(numbers[1]<<16)|(numbers[2]<<8)
        key=serialization.load_pem_private_key(args.key.read_bytes(),password=None)
        blob=pack_image(body,version,key);metadata=inspect_package(blob)
        with args.output.open("xb") as f:f.write(blob)
        print(json.dumps(metadata,indent=2))
    elif args.action=="inspect":print(json.dumps(inspect_package(args.image.read_bytes()),indent=2))
    else:
        if not re.fullmatch(r"[0-9a-fA-F]{64}",args.target):parser.error("--target must be the exact 32-byte public key")
        if args.pace<1 or args.timeout<5 or not 1<=args.retries<=20:parser.error("pace >=1 second, timeout >=5 seconds, retries 1..20")
        asyncio.run(upload(args))

if __name__=="__main__":main()
