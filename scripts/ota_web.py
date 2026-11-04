#!/usr/bin/env python3
"""Private HTTPS interface for preparing and uploading MeshCore OTA packages."""
import argparse
import base64
import binascii
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import ssl
import struct
import subprocess
import sys
import threading
import time
import zipfile
import lora_ota

ROOT=Path(__file__).resolve().parents[1]
MAX_REQUEST=1_600_000

def transfer_timing(job,now=None):
    if not job:return None
    job=dict(job);now=time.time() if now is None else now
    end=job.get('finished',now)
    job['elapsed_seconds']=max(0,end-job['started'])
    job['eta_seconds']=None
    job['retry_in_seconds']=max(0,job.get('retry_at',now)-now) if job['status']=='waiting' else None
    measured=end-job.get('progress_started',end)
    moved=job['sent']-job.get('resume_offset',job['sent'])
    if job['status'] in ('starting','running') and measured>=10 and moved>0:
        job['eta_seconds']=max(0,job['total']-job['sent'])*measured/moved
    job['activation_command']='pm ota apply '+job['sha256'][:8]
    return job

class State:
    def __init__(self,directory,auth):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.packages=self.directory/'packages';self.packages.mkdir(exist_ok=True,mode=0o700)
        self.auth=auth;self.lock=threading.Lock();self.job=None;self.process=None
        self.stop_event=threading.Event()
        self.worker_active=False

    def ports(self):
        configured=os.environ.get('PM_OTA_PORTS')
        if configured:return sorted(set(configured.split(',')))
        return sorted(set(str(p) for p in Path('/dev/serial/by-id').glob('*RAK*')) | set(str(p) for p in Path('/dev').glob('ttyACM*')))

    def key_info(self):
        path=self.directory/'signing.pem'
        if not path.exists():return None
        from cryptography.hazmat.primitives import serialization
        key=serialization.load_pem_private_key(path.read_bytes(),password=None)
        return key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()

    def create_key(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        key=Ed25519PrivateKey.generate()
        fd=os.open(self.directory/'signing.pem',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        return self.key_info()

    def store(self,blob):
        metadata=lora_ota.inspect_package(blob);path=self.packages/(metadata['sha256']+'.mota')
        if not path.exists():
            if len(list(self.packages.glob('*.mota')))>=20:raise ValueError('Package storage is full; remove old packages on the Pi')
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(blob)
        return metadata

    def prepare(self,request):
        from cryptography.hazmat.primitives import serialization
        body=base64.b64decode(request['firmware'],validate=True)
        manifest=request['manifest'];name=request['name']
        if not manifest.get('lora_ota') or manifest.get('ota_storage')!='RAK15001 slot C; JEDEC C84015':raise ValueError('Select the RAK15001 LoRa OTA build and its matching JSON manifest')
        if manifest.get('ota_bootloader_sha256')!=lora_ota.BOOT_HASH or manifest.get('ota_target')!=lora_ota.TARGET_NAME:raise ValueError('Use the application matched to OTAFIX 2.4.12; old 0.4.0/0.4.1 builds use a different handoff')
        entries=manifest.get('firmware',{});entry=entries.get(name,{})
        if not entry:
            # Browser downloads may rename files; their complete hash and
            # byte length still have to match a same-format build artifact.
            matches=[(n,e) for n,e in entries.items() if Path(n).suffix==Path(name).suffix and e.get('bytes')==len(body) and e.get('sha256')==hashlib.sha256(body).hexdigest()]
            if len(matches)==1:name,entry=matches[0]
        if entry.get('sha256')!=hashlib.sha256(body).hexdigest() or entry.get('bytes')!=len(body):raise ValueError('Firmware file does not match the build manifest')
        if name.lower().endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                info=z.getinfo('manifest.json')
                if info.file_size>8192:raise ValueError('Invalid DFU manifest')
                m=json.loads(z.read(info))['manifest']
                if set(m)!={'application','dfu_version'} or m['dfu_version']!=0.5:raise ValueError('Application-only legacy DFU ZIP required')
                app=m['application'];info=z.getinfo(app['bin_file'])
                if not 64<=info.file_size<=lora_ota.MAX_IMAGE:raise ValueError('Application size outside profile')
                with z.open(info) as f:body=f.read(lora_ota.MAX_IMAGE+1)
                init_info=z.getinfo(app['dat_file'])
                if init_info.file_size!=14:raise ValueError('Unexpected DFU init packet')
                init=z.read(init_info)
                if struct.unpack_from('<H',init,10)[0]!=0xB6 or struct.unpack_from('<H',init,12)[0]!=binascii.crc_hqx(body,0xffff):raise ValueError('DFU SoftDevice/CRC mismatch')
                if not any(n.endswith('.bin') and e.get('sha256')==hashlib.sha256(body).hexdigest() for n,e in manifest['firmware'].items()):raise ValueError('DFU application BIN does not match build manifest')
        elif not name.lower().endswith('.bin'):raise ValueError('Select a BIN or application DFU ZIP')
        version=[int(x) for x in manifest['version'].split('-')[0].split('.')]
        if len(version)!=3 or any(not 0<=x<=255 for x in version):raise ValueError('Invalid version')
        key=serialization.load_pem_private_key((self.directory/'signing.pem').read_bytes(),password=None)
        return self.store(lora_ota.pack_image(body,(version[0]<<24)|(version[1]<<16)|(version[2]<<8),key))

    def start(self,request):
        digest=request.get('sha256','');target=request.get('target','');port=request.get('port','');password=request.get('password','')
        pace=request.get('pace',2)
        if type(pace) not in (int,float) or not 1<=pace<=30:raise ValueError('Select a packet delay between 1 and 30 seconds')
        activate=request.get('activate',False)
        if type(activate) is not bool:raise ValueError('Invalid activation choice')
        auto_resume=request.get('auto_resume',False);retry_minutes=request.get('retry_minutes',5)
        if type(auto_resume) is not bool or type(retry_minutes) is not int or not 1<=retry_minutes<=15:raise ValueError('Auto-resume delay must be 1–15 whole minutes')
        if auto_resume and activate:raise ValueError('Auto-resume is for upload and verify only; activate separately after success')
        if not re.fullmatch('[0-9a-f]{64}',digest) or not re.fullmatch('[0-9a-fA-F]{64}',target):raise ValueError('Exact package hash and target public key are required')
        if port not in self.ports():raise ValueError('Select a listed companion serial port')
        if not isinstance(password,str) or not 1<=len(password)<=128 or any(c in password for c in '\r\n\0'):raise ValueError('Enter the repeater admin password')
        path=self.packages/(digest+'.mota');metadata=lora_ota.inspect_package(path.read_bytes())
        with self.lock:
            if self.worker_active or self.process is not None or (self.job and self.job['status'] in ('running','starting','stopping','waiting')):raise ValueError('An upload is already running')
            self.stop_event.clear()
            self.worker_active=True
            self.job={'status':'starting','target':target,'port':port,'activate':activate,'pace':pace,'sha256':digest,'auto_resume':auto_resume,'retry_minutes':retry_minutes,'sent':0,'total':metadata['bytes'],'logs':[],'started':time.time()}
            threading.Thread(target=self.worker,args=(path,target,port,password,activate,pace,auto_resume,retry_minutes),daemon=True).start()
        return {'started':True}

    def worker(self,path,target,port,password,activate,pace=2,auto_resume=False,retry_minutes=5):
        try:
            while not self.stop_event.is_set():
                with self.lock:
                    if self.job['status']=='stopping':break
                    self.job['attempt']=self.job.get('attempt',0)+1
                    self.job['started']=time.time();self.job['retryable']=False
                    for name in ('finished','progress_started','resume_offset','retry_at'):self.job.pop(name,None)
                self._attempt(path,target,port,password,activate,pace)
                with self.lock:
                    if self.job['status'] in ('complete','stopped','stopping') or not auto_resume or not self.job.get('retryable'):break
                    self.job['status']='waiting';self.job['retry_at']=time.time()+retry_minutes*60
                    self.job['logs']=(self.job['logs']+[f'Connection failed. Auto-resume of the same package in {retry_minutes} minute(s). Stop sending cancels pending retries.'])[-300:]
                if self.stop_event.wait(retry_minutes*60):break
            with self.lock:
                if self.stop_event.is_set() or self.job['status']=='stopping':self.job['status']='stopped'
        finally:
            password=None
            with self.lock:self.worker_active=False

    def _attempt(self,path,target,port,password,activate,pace=2):
        command=[sys.executable,'-u',str(ROOT/'scripts/lora_ota.py'),'upload',str(path),'--port',port,'--target',target,'--password-stdin','--progress','--pace',str(pace)]
        if activate:command.append('--apply')
        process=None
        try:
            with self.lock:
                if self.job['status']=='stopping':self.job['status']='stopped';return
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                self.process=process;self.job['status']='running'
            process.stdin.write(password+'\n');process.stdin.close()
            for line in process.stdout:
                line=line.rstrip().replace(password,'[redacted]')
                with self.lock:
                    if line.startswith('PM_FAILURE retryable='):
                        self.job['retryable']=line=='PM_FAILURE retryable=1';continue
                    if line.startswith('PM_ROUTE '):
                        self.job['route']=json.loads(line[9:]);continue
                    match=re.fullmatch(r'PM_PROGRESS (\d+) (\d+)',line)
                    if match:
                        if 'progress_started' not in self.job:
                            self.job['progress_started']=time.time();self.job['resume_offset']=int(match[1])
                        self.job['sent']=int(match[1]);self.job['total']=int(match[2])
                    else:self.job['logs']=(self.job['logs']+[line])[-300:]
            result=process.wait()
            with self.lock:self.job['status']='stopped' if self.job['status']=='stopping' else ('complete' if result==0 else 'failed')
        except Exception as error:
            with self.lock:
                self.job['status']='failed';self.job['retryable']=isinstance(error,(ConnectionError,TimeoutError))
                self.job['logs'].append('Upload could not run. Check the companion connection and service logs.')
        finally:
            password=None
            with self.lock:
                self.job['finished']=time.time()
                if self.process is process:self.process=None

    def stop(self):
        with self.lock:
            if self.job and self.job['status'] in ('starting','running','waiting'):
                self.stop_event.set()
                self.job['status']='stopping'
                if self.process:self.process.terminate()
        return {'stopping':True}

class Handler(BaseHTTPRequestHandler):
    server_version='PowerMonitor'
    def log_message(self,*args):pass # Never log request bodies or credentials.

    def auth(self):
        try:
            header=self.headers.get('Authorization','')
            if not header.startswith('Basic '):return False
            user,password=base64.b64decode(header[6:],validate=True).decode().split(':',1)
            config=self.server.state.auth
            actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(config['salt']),200000).hex()
            return hmac.compare_digest(user,'admin') and hmac.compare_digest(actual,config['hash'])
        except Exception:return False

    def respond(self,status,data,kind='application/json',download=None):
        body=data if isinstance(data,bytes) else json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        if download:self.send_header('Content-Disposition','attachment; filename="'+download+'"')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)

    def authorized(self):
        if self.auth():return True
        self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="PowerMonitor OTA", charset="UTF-8"');self.send_header('Content-Length','0');self.end_headers();return False

    def do_GET(self):
        if not self.authorized():return
        state=self.server.state
        try:
            if self.path in ('/','/app.js','/style.css'):
                name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[self.path]
                kind={'/':'text/html; charset=utf-8','/app.js':'application/javascript','/style.css':'text/css'}[self.path]
                return self.respond(200,(ROOT/'web'/name).read_bytes(),kind)
            if self.path=='/api/status':
                with state.lock:job=transfer_timing(json.loads(json.dumps(state.job)))
                companion=None
                try:
                    from companion_rpc import SOCKET,call_sync
                    if SOCKET.exists():companion=call_sync({'op':'status'},timeout=2)
                except Exception:pass
                return self.respond(200,{'ports':state.ports(),'signer':state.key_info(),'job':job,'companion':companion})
            if self.path=='/downloads/receiver.zip':
                return self.respond(200,(ROOT/'releases/v0.4.2-bootstrap.4/RAK4631_official_rak15001_lora_ota_PM_v0.4.2-bootstrap.4.zip').read_bytes(),'application/zip')
            if self.path=='/downloads/receiver.json':
                return self.respond(200,(ROOT/'releases/v0.4.2-bootstrap.4/RAK4631_official_rak15001_lora_ota_PM_v0.4.2-bootstrap.4.json').read_bytes())
            if self.path in ('/downloads/test.zip','/downloads/test.json'):
                suffix=self.path.rsplit('.',1)[1]
                path=ROOT/'releases/v0.4.2-ota-test.4'/('RAK4631_official_rak15001_lora_ota_PM_v0.4.2-ota-test.4.'+suffix)
                return self.respond(200,path.read_bytes(),'application/zip' if suffix=='zip' else 'application/json')
            if re.fullmatch(r'/packages/[0-9a-f]{64}\.mota',self.path):
                name=self.path.rsplit('/',1)[1]
                return self.respond(200,(state.packages/name).read_bytes(),'application/octet-stream',download='power-monitor-'+name[:8]+'.mota')
            self.respond(404,{'error':'Not found'})
        except Exception:self.respond(400,{'error':'Unable to read requested resource'})

    def do_POST(self):
        if not self.authorized():return
        # A custom header and matching origin prevent cross-site form requests
        # using the browser's cached Basic credentials. No CORS is enabled.
        origin=self.headers.get('Origin')
        if self.headers.get('X-PM-Request')!='1' or (origin and origin!='https://'+self.headers.get('Host','')):
            return self.respond(403,{'error':'Same-origin request required'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=MAX_REQUEST:return self.respond(413,{'error':'Upload too large'})
            body=self.rfile.read(size);state=self.server.state
            if self.path=='/api/import':return self.respond(200,state.store(body))
            request=json.loads(body or b'{}')
            if self.path=='/api/key':return self.respond(200,{'signer':state.create_key()})
            if self.path=='/api/prepare':return self.respond(200,state.prepare(request))
            if self.path=='/api/start':return self.respond(200,state.start(request))
            if self.path=='/api/stop':return self.respond(200,state.stop())
            self.respond(404,{'error':'Not found'})
        except FileExistsError:self.respond(409,{'error':'A signing key already exists; it will not be replaced'})
        except FileNotFoundError:self.respond(400,{'error':'Create the signing key or upload the package first'})
        except (ValueError,KeyError,TypeError,zipfile.BadZipFile,binascii.Error) as e:self.respond(400,{'error':str(e)[:220]})
        except Exception:self.respond(400,{'error':'Package validation or request failed'})

class TLSHTTPServer(ThreadingHTTPServer):
    # A client that opens TCP without completing TLS must not block accept().
    # Perform the handshake in its worker, with a bounded idle timeout.
    request_queue_size=32
    def process_request_thread(self,request,client_address):
        connection=request
        try:
            request.settimeout(15)
            connection=self.tls.wrap_socket(request,server_side=True,do_handshake_on_connect=False)
            connection.do_handshake()
            super().process_request_thread(connection,client_address)
        except (OSError,ssl.SSLError):
            pass
        finally:
            self.shutdown_request(connection)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind',default='0.0.0.0');parser.add_argument('--port',type=int,default=8443)
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--auth',type=Path,required=True)
    parser.add_argument('--cert',required=True);parser.add_argument('--key',required=True)
    args=parser.parse_args();server=TLSHTTPServer((args.bind,args.port),Handler)
    server.state=State(args.directory,json.loads(args.auth.read_text()))
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(args.cert,args.key)
    server.tls=tls
    print(f'PowerMonitor HTTPS uploader listening on port {args.port}',flush=True);server.serve_forever()

if __name__=='__main__':main()
