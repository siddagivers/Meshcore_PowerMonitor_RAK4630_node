#!/usr/bin/env python3
"""Persistent MeshCore inbox and single-owner companion command broker."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import threading
import time
from urllib.parse import urlsplit
from types import SimpleNamespace
from ota_web import Handler,TLSHTTPServer
from companion_rpc import call_sync

ROOT=Path(__file__).resolve().parents[1]

def plain(value):
    if isinstance(value,bytes):return value.hex()
    if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain(v) for v in value]
    return value if isinstance(value,(str,int,float,bool,type(None))) else str(value)

class Store:
    def __init__(self,path):
        self.lock=threading.RLock();self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,received REAL,kind TEXT,direction TEXT,peer TEXT,text TEXT,payload TEXT,fingerprint TEXT UNIQUE)')
        self.db.execute('CREATE TABLE IF NOT EXISTS cache(name TEXT PRIMARY KEY,value TEXT)');self.db.commit()
    def save(self,kind,payload,direction='in',peer='',text='',dedup=False):
        payload=plain(payload)
        identity={k:payload.get(k) for k in ('pubkey_prefix','sender_timestamp','channel_idx','text','txt_type')}
        fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest() if dedup else None
        with self.lock:
            self.db.execute('INSERT OR IGNORE INTO events(received,kind,direction,peer,text,payload,fingerprint) VALUES(?,?,?,?,?,?,?)',(time.time(),kind,direction,peer,text,json.dumps(payload),fingerprint));self.db.commit()
    def cache(self,name,value=None):
        with self.lock:
            if value is not None:
                self.db.execute('INSERT OR REPLACE INTO cache VALUES(?,?)',(name,json.dumps(plain(value))));self.db.commit()
            row=self.db.execute('SELECT value FROM cache WHERE name=?',(name,)).fetchone()
            return json.loads(row[0]) if row else []
    def events(self):
        with self.lock:
            rows=self.db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 200').fetchall()
            return [dict(r,payload=json.loads(r['payload'])) for r in reversed(rows)]

def port_owners(port):
    """Detect older non-broker serial owners; never terminate them."""
    target=os.path.realpath(port);owners=[]
    for process in Path('/proc').glob('[0-9]*'):
        if process.name==str(os.getpid()):continue
        try:
            if any(os.path.realpath(fd)==target for fd in (process/'fd').iterdir()):owners.append(int(process.name))
        except (OSError,PermissionError):pass
    return owners

class Hub:
    def __init__(self,store,port,cron_lock):
        self.store,self.port,self.cron_lock=store,port,cron_lock
        self.mc=None;self.online=False;self.busy=None;self.error='Starting';self.lock=asyncio.Lock();self.radios={}
    def status(self):return {'online':self.online,'busy':self.busy,'error':self.error,'port':self.port}
    def contact(self,key):
        values=list(self.mc.contacts.values())
        exact=[c for c in values if c['public_key'].lower()==str(key).lower() or c.get('adv_name')==key]
        if len(exact)!=1:raise ValueError('Contact not found or name is ambiguous; use its full public key')
        return exact[0]
    def snapshot_contacts(self):
        contacts=[{k:c.get(k) for k in ('public_key','adv_name','type','out_path','out_path_len','out_path_hash_mode','flags','last_advert')} for c in self.mc.contacts.values()]
        self.store.cache('contacts',contacts)
    def event(self,event):
        from meshcore import EventType
        payload=plain(event.payload);kind=event.type.value
        if event.type==EventType.CONTACT_MSG_RECV and payload.get('txt_type',0)!=0:return
        if event.type==EventType.NEW_CONTACT:
            pending=self.store.cache('discovered');pending=[c for c in pending if c.get('public_key')!=payload.get('public_key')]
            self.store.cache('discovered',(pending+[payload])[-100:]);return
        if event.type==EventType.ADVERTISEMENT:return
        peer=payload.get('pubkey_prefix',payload.get('pubkey_pre',str(payload.get('channel_idx',''))))
        self.store.save(kind,payload,peer=peer,text=payload.get('text',''),dedup=event.type in (EventType.CONTACT_MSG_RECV,EventType.CHANNEL_MSG_RECV))
    async def connect_loop(self):
        from meshcore import MeshCore,EventType
        while True:
            try:
                if port_owners(self.port):
                    self.error='Waiting for the existing OTA/telemetry serial connection to finish';await asyncio.sleep(3);continue
                # The existing cron wrapper holds this for its entire collection.
                gate=open(self.cron_lock,'a')
                try:fcntl.flock(gate,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    gate.close();self.error='Waiting for the scheduled telemetry collection';await asyncio.sleep(2);continue
                try:
                    if port_owners(self.port):continue
                    self.mc=await MeshCore.create_serial(self.port,115200)
                    self.radios.clear()
                    for kind in ('CONTACT_MSG_RECV','CHANNEL_MSG_RECV','TELEMETRY_RESPONSE','ACK','NEW_CONTACT','ADVERTISEMENT'):
                        self.mc.subscribe(getattr(EventType,kind),self.event)
                    result=await self.mc.commands.get_contacts()
                    if result is None or result.type==EventType.ERROR:raise RuntimeError('Unable to read companion contacts')
                    self.snapshot_contacts()
                    channels=[]
                    for index in range(8):
                        result=await self.mc.commands.get_channel(index)
                        if result and result.type!=EventType.ERROR:
                            name=result.payload.get('channel_name','')
                            if name:channels.append({'index':index,'name':name})
                    self.store.cache('channels',channels)
                    await self.mc.start_auto_message_fetching();self.online=True;self.error=''
                finally:gate.close()
                ticks=0
                while self.online:
                    await asyncio.sleep(5)
                    ticks+=1
                    if ticks%6==0:
                        async with self.lock:
                            result=await self.mc.commands.get_bat()
                            if result is None or result.type==EventType.ERROR:raise RuntimeError('Companion disconnected')
                    # Contacts may change when advertisements arrive.
                    self.snapshot_contacts()
            except Exception:
                self.online=False;self.error='Companion disconnected; reconnecting'
            finally:
                if self.mc:
                    try:await self.mc.disconnect()
                    except Exception:pass
                    self.mc=None
            await asyncio.sleep(5)
    async def command(self,request):
        from meshcore import EventType
        op=request.get('op')
        if op=='status':return self.status()
        if not self.online:raise ValueError(self.error or 'Companion not connected')
        if op=='admin':
            # Only the local serial send takes the shared lock. Waiting for an
            # OTA reply must not starve the five-minute telemetry collector.
            # Conversely, an ongoing telemetry transaction retains the lock,
            # so OTA's send and its reply timeout start only after it finishes.
            contact=self.contact(request.get('target',''));text=request.get('command','')
            if not text.startswith('pm ota ') or len(text)>180:raise ValueError('Only OTA commands are supported by this bridge')
            pace=request.get('pace',2)
            if type(pace) not in (int,float) or not 1<=pace<=30:raise ValueError('Invalid packet interval')
            from lora_ota import Radio
            hub=self
            class Commands:
                async def send_cmd(self,contact,text):
                    async with hub.lock:return await hub.mc.commands.send_cmd(contact,text)
            proxy=SimpleNamespace(commands=Commands(),subscribe=self.mc.subscribe)
            radio=self.radios.setdefault(contact['public_key'],Radio(proxy,contact))
            radio.pace=pace
            return {'reply':await radio.request(text)}
        async with self.lock:
            if not self.online:raise ValueError('Companion disconnected')
            self.busy=op
            try:
                if op=='contacts':
                    await self.mc.commands.get_contacts();self.snapshot_contacts();return self.store.cache('contacts')
                if op=='import':
                    raw=request.get('card','');raw=raw.removeprefix('meshcore://')
                    if not re.fullmatch('[0-9a-fA-F]{2,1024}',raw) or len(raw)%2:raise ValueError('Enter an exported meshcore:// contact card')
                    result=await self.mc.commands.import_contact(bytes.fromhex(raw))
                elif op=='add':
                    key=request.get('key','');name=request.get('name','').strip()
                    if not re.fullmatch('[0-9a-fA-F]{64}',key) or not 1<=len(name.encode())<=32:raise ValueError('Enter a full public key and a name of 1–32 UTF-8 bytes')
                    kind=request.get('type',1)
                    if type(kind) is not int or kind not in (1,2,3):raise ValueError('Invalid contact type')
                    contact={'public_key':key.lower(),'adv_name':name,'type':kind,'flags':0,'out_path':'','out_path_len':-1,'out_path_hash_mode':0,'last_advert':int(time.time()),'adv_lat':0,'adv_lon':0}
                    result=await self.mc.commands.add_contact(contact)
                elif op=='channel':
                    index=request.get('channel');text=request.get('text','')
                    if type(index) is not int or index not in [c['index'] for c in self.store.cache('channels')]:raise ValueError('Select a configured channel')
                    self.validate_text(text);result=await self.mc.commands.send_chan_msg(index,text)
                    self.record_send(result,str(index),text,'channel')
                    return {'status':'Accepted by companion; channel delivery is not acknowledged'}
                else:
                    contact=self.contact(request.get('target',''))
                    if op=='telemetry':
                        # Match the existing meshcli collector: modern binary
                        # telemetry requests correlate the response by tag.
                        lpp=await self.mc.commands.req_telemetry_sync(contact,timeout=25)
                        if lpp is None:raise RuntimeError('No telemetry reply before timeout')
                        return {'name':contact['adv_name'],'pubkey_pre':contact['public_key'][:16],'lpp':lpp}
                    if op=='route':
                        from lora_ota import describe_route
                        return {'contact':contact,'route':describe_route(contact,self.mc.contacts)}
                    if op=='reset_path':result=await self.mc.commands.reset_path(contact)
                    elif op=='login':
                        password=request.get('password','')
                        if not isinstance(password,str) or not 1<=len(password)<=128:raise ValueError('Invalid admin password')
                        ok=await self.mc.commands.send_login_sync(contact,password,min_timeout=30)
                        return {'logged_in':bool(ok)}
                    elif op=='remove':result=await self.mc.commands.remove_contact(contact)
                    elif op=='message':
                        text=request.get('text','');self.validate_text(text)
                        result=await self.mc.commands.send_msg(contact,text)
                        self.record_send(result,contact['public_key'],text,'private')
                        return {'status':'Accepted by companion; awaiting acknowledgment (see inbox events)'}
                    else:raise ValueError('Unknown companion action')
                if result is None or result.type==EventType.ERROR:raise RuntimeError('Companion rejected the action')
                await self.mc.commands.get_contacts();self.snapshot_contacts();return {'status':'Contact updated'}
            finally:self.busy=None
    @staticmethod
    def validate_text(text):
        if not isinstance(text,str) or not text.strip() or len(text.encode())>150:raise ValueError('Enter a message of 1–150 UTF-8 bytes')
    def record_send(self,result,peer,text,kind):
        from meshcore import EventType
        if result is None or result.type==EventType.ERROR:raise RuntimeError('Companion rejected the message')
        self.store.save(kind,{'status':'accepted by companion','response':plain(result.payload)},direction='out',peer=peer,text=text)
    async def client(self,reader,writer):
        task=watch=None
        try:
            request=json.loads(await asyncio.wait_for(reader.readline(),10))
            task=asyncio.create_task(self.command(request))
            watch=asyncio.create_task(reader.read(1))
            done,_=await asyncio.wait((task,watch),return_when=asyncio.FIRST_COMPLETED)
            if watch in done and not task.done():
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass
                return
            result=await task;response={'ok':True,'result':result}
        except (ValueError,RuntimeError) as error:response={'ok':False,'error':str(error)[:180]}
        except Exception:response={'ok':False,'error':'Companion request timed out or disconnected; check connection and retry'}
        finally:
            if watch:watch.cancel()
            if task and not task.done():task.cancel()
            if 'response' not in locals():writer.close()
        try:writer.write(json.dumps(plain(response)).encode()+b'\n');await writer.drain()
        finally:writer.close();await writer.wait_closed()
    async def run(self,socket_path):
        socket_path.unlink(missing_ok=True)
        server=await asyncio.start_unix_server(self.client,str(socket_path),limit=65536)
        os.chmod(socket_path,0o600)
        async with server:await asyncio.gather(server.serve_forever(),self.connect_loop())

class ChatHandler(Handler):
    def do_GET(self):
        if not self.authorized():return
        path=urlsplit(self.path).path
        if path=='/api/state':return self.respond(200,{'connection':self.server.hub.status(),'contacts':self.server.store.cache('contacts'),'channels':self.server.store.cache('channels'),'discovered':self.server.store.cache('discovered'),'events':self.server.store.events()})
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','application/javascript'),'/style.css':('style.css','text/css')}
        if path not in files:return self.respond(404,{'error':'Not found'})
        name,kind=files[path];self.respond(200,(ROOT/'inbox'/name).read_bytes(),kind)
    def do_POST(self):
        if not self.authorized():return
        origin=self.headers.get('Origin')
        if self.headers.get('X-PM-Request')!='1' or (origin and origin!='https://'+self.headers.get('Host','')):return self.respond(403,{'error':'Same-origin request required'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=10000:raise ValueError('Invalid request size')
            request=json.loads(self.rfile.read(size))
            allowed={'/api/send':('message','channel'),'/api/contact':('add','remove','import'),'/api/refresh':('contacts',),'/api/telemetry':('telemetry',)}
            if request.get('op') not in allowed.get(self.path,()):raise ValueError('Unsupported action')
            result=call_sync(request);self.respond(200,result)
        except (ValueError,RuntimeError) as error:self.respond(400,{'error':str(error)[:180]})
        except Exception:self.respond(503,{'error':'Companion unavailable; no message was queued. Check connection and retry.'})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','auth','cert','key','serial'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--port',type=int,default=8444)
    parser.add_argument('--cron-lock',default='/tmp/meshcore-siprun.lock')
    args=parser.parse_args();os.umask(0o077)
    directory=Path(args.directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Only one service may own this broker, including across restarts.
    lease=open(directory/'service.lock','a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=Store(directory/'inbox.sqlite3');hub=Hub(store,args.serial,args.cron_lock)
    thread=threading.Thread(target=lambda:asyncio.run(hub.run(directory/'companion.sock')),daemon=True);thread.start()
    server=TLSHTTPServer(('0.0.0.0',args.port),ChatHandler)
    server.state=SimpleNamespace(auth=json.loads(Path(args.auth).read_text()))
    server.store=store;server.hub=hub
    server.tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server.tls.minimum_version=ssl.TLSVersion.TLSv1_2;server.tls.load_cert_chain(args.cert,args.key)
    print('MeshCore inbox HTTPS ready; companion waits for existing serial users',flush=True);server.serve_forever()

if __name__=='__main__':main()
