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

class State:
    def __init__(self,directory,auth):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.packages=self.directory/'packages';self.packages.mkdir(exist_ok=True,mode=0o700)
        self.auth=auth;self.lock=threading.Lock();self.job=None;self.process=None

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
        if not re.fullmatch('[0-9a-f]{64}',digest) or not re.fullmatch('[0-9a-fA-F]{64}',target):raise ValueError('Exact package hash and target public key are required')
        if port not in self.ports():raise ValueError('Select a listed companion serial port')
        if not isinstance(password,str) or not 1<=len(password)<=128 or any(c in password for c in '\r\n\0'):raise ValueError('Enter the repeater admin password')
        path=self.packages/(digest+'.mota');metadata=lora_ota.inspect_package(path.read_bytes())
        activate=request.get('activate',False)
        if type(activate) is not bool:raise ValueError('Invalid activation choice')
        with self.lock:
            if self.process is not None or (self.job and self.job['status'] in ('running','starting','stopping')):raise ValueError('An upload is already running')
            self.job={'status':'starting','target':target,'port':port,'activate':activate,'sent':0,'total':metadata['bytes'],'logs':[],'started':time.time()}
            threading.Thread(target=self.worker,args=(path,target,port,password,activate),daemon=True).start()
        return {'started':True}

    def worker(self,path,target,port,password,activate):
        command=[sys.executable,'-u',str(ROOT/'scripts/lora_ota.py'),'upload',str(path),'--port',port,'--target',target,'--password-stdin','--progress']
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
                    match=re.fullmatch(r'PM_PROGRESS (\d+) (\d+)',line)
                    if match:self.job['sent']=int(match[1]);self.job['total']=int(match[2])
                    else:self.job['logs']=(self.job['logs']+[line])[-300:]
            result=process.wait()
            with self.lock:self.job['status']='stopped' if self.job['status']=='stopping' else ('complete' if result==0 else 'failed')
        except Exception:
            with self.lock:self.job['status']='failed';self.job['logs'].append('Upload could not run. Check the companion connection and service logs.')
        finally:
            password=None
            with self.lock:
                if self.process is process:self.process=None

    def stop(self):
        with self.lock:
            if self.job and self.job['status'] in ('starting','running'):
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

    def respond(self,status,data,kind='application/json'):
        body=data if isinstance(data,bytes) else json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
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
                with state.lock:job=json.loads(json.dumps(state.job))
                return self.respond(200,{'ports':state.ports(),'signer':state.key_info(),'job':job})
            if self.path=='/downloads/receiver.zip':
                return self.respond(200,(ROOT/'releases/v0.4.2-bootstrap.1/RAK4631_official_rak15001_lora_ota_PM_v0.4.2-bootstrap.1.zip').read_bytes(),'application/zip')
            if self.path=='/downloads/receiver.json':
                return self.respond(200,(ROOT/'releases/v0.4.2-bootstrap.1/RAK4631_official_rak15001_lora_ota_PM_v0.4.2-bootstrap.1.json').read_bytes())
            if self.path in ('/downloads/test.zip','/downloads/test.json'):
                suffix=self.path.rsplit('.',1)[1]
                path=ROOT/'releases/v0.4.2-ota-test.1'/('RAK4631_official_rak15001_lora_ota_PM_v0.4.2-ota-test.1.'+suffix)
                return self.respond(200,path.read_bytes(),'application/zip' if suffix=='zip' else 'application/json')
            if re.fullmatch(r'/packages/[0-9a-f]{64}\.mota',self.path):
                return self.respond(200,(state.packages/self.path.rsplit('/',1)[1]).read_bytes(),'application/octet-stream')
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

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind',default='0.0.0.0');parser.add_argument('--port',type=int,default=8443)
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--auth',type=Path,required=True)
    parser.add_argument('--cert',required=True);parser.add_argument('--key',required=True)
    args=parser.parse_args();server=ThreadingHTTPServer((args.bind,args.port),Handler)
    server.state=State(args.directory,json.loads(args.auth.read_text()))
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(args.cert,args.key)
    server.socket=tls.wrap_socket(server.socket,server_side=True)
    print(f'PowerMonitor HTTPS uploader listening on port {args.port}',flush=True);server.serve_forever()

if __name__=='__main__':main()
