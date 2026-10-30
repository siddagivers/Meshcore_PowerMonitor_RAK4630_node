import base64
import hashlib
import http.client
import io
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ota_web
import lora_ota

class WebTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();salt=b'local-test-salt'
        self.auth={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',b'test-only-password',salt,200000).hex()}
        self.state=ota_web.State(self.folder.name,self.auth)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),ota_web.Handler);self.server.state=self.state
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.folder.cleanup()
    def request(self,path,body=None,auth=True,csrf=True):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        headers={}
        if auth:headers['Authorization']='Basic '+base64.b64encode(b'admin:test-only-password').decode()
        if csrf:headers['X-PM-Request']='1'
        if body is not None and not isinstance(body,bytes):body=json.dumps(body).encode()
        connection.request('GET' if body is None else 'POST',path,body,headers)
        response=connection.getresponse();status=response.status;data=response.read();connection.close()
        return status,json.loads(data) if data else {}
    def test_auth_csrf_and_key(self):
        self.assertEqual(self.request('/api/status',auth=False)[0],401)
        self.assertEqual(self.request('/api/key',{},csrf=False)[0],403)
        status,body=self.request('/api/key',{});self.assertEqual(status,200);self.assertEqual(len(body['signer']),64)
        self.assertEqual(self.request('/api/key',{})[0],409)
        self.assertNotIn('PRIVATE',json.dumps(self.request('/api/status')[1]))
        self.assertEqual(self.request('/api/import',b'not a signed image')[0],400)
    def test_prepare_and_no_automatic_radio(self):
        self.state.create_key();binary=bytearray(b'\x55'*5000);struct.pack_into('<II',binary,0,0x2003f000,0x26021)
        manifest={'lora_ota':True,'ota_storage':'RAK15001 slot C; JEDEC C84015','version':'0.4.0-test','firmware':{'firmware.bin':{'bytes':len(binary),'sha256':hashlib.sha256(binary).hexdigest()}}}
        status,result=self.request('/api/prepare',{'firmware':base64.b64encode(binary).decode(),'name':'firmware.bin','manifest':manifest})
        self.assertEqual(status,200);self.assertIsNone(self.state.job);self.assertIsNone(self.state.process)
        self.assertTrue((self.state.packages/(result['sha256']+'.mota')).exists())
        status,_=self.request('/api/start',{'sha256':result['sha256'],'target':'a'*64,'port':'/dev/unrelated','password':'secret','activate':False})
        self.assertEqual(status,400);self.assertIsNone(self.state.process)
        manifest['firmware']['firmware.bin']['sha256']='0'*64
        self.assertEqual(self.request('/api/prepare',{'firmware':base64.b64encode(binary).decode(),'name':'firmware.bin','manifest':manifest})[0],400)
    def test_password_not_in_job_or_arguments(self):
        self.state.create_key();binary=bytearray(b'\x55'*5000);struct.pack_into('<II',binary,0,0x2003f000,0x26021)
        from cryptography.hazmat.primitives import serialization
        key=serialization.load_pem_private_key((self.state.directory/'signing.pem').read_bytes(),None)
        info=self.state.store(lora_ota.pack_image(bytes(binary),0x40000,key))
        with patch.object(self.state,'ports',return_value=['/dev/test-companion']),patch('threading.Thread.start'):
            self.state.start({'sha256':info['sha256'],'target':'b'*64,'port':'/dev/test-companion','password':'private-test-value','activate':False})
        self.assertNotIn('private-test-value',json.dumps(self.state.job));self.assertFalse(self.state.job['activate'])
        class Pipe(io.StringIO):
            def close(self):pass
        class Process:
            stdin=Pipe();stdout=iter(['private-test-value\n','PM_PROGRESS 40 5000\n'])
            def wait(self):return 0
        with patch('subprocess.Popen',return_value=Process()) as spawned:
            self.state.worker(self.state.packages/(info['sha256']+'.mota'),'b'*64,'/dev/test-companion','private-test-value',False)
        self.assertNotIn('private-test-value',json.dumps(self.state.job))
        self.assertNotIn('private-test-value',' '.join(spawned.call_args.args[0]))
        self.assertNotIn('--apply',spawned.call_args.args[0]);self.assertEqual(self.state.job['sent'],40)
    def test_actual_dfu_zip_can_be_renamed(self):
        self.state.create_key();root=Path(__file__).resolve().parents[1]
        prefix='RAK4631_official_rak15001_lora_ota_PM_v0.4.0-pi.ota.1'
        folder=root/'releases/v0.4.0-pi.ota.1'
        manifest=json.loads((folder/(prefix+'.json')).read_text());data=(folder/(prefix+'.zip')).read_bytes()
        result=self.state.prepare({'name':'renamed-download.zip','firmware':base64.b64encode(data).decode(),'manifest':manifest})
        self.assertEqual(result['image_bytes'],379660+56);self.assertIsNone(self.state.job)

if __name__=='__main__':unittest.main()
