import base64
import hashlib
import http.client
import io
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import struct
import zipfile
import sys
import tempfile
import threading
import socket
import ssl
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ota_web
import lora_ota

class WebTest(unittest.TestCase):
    def test_auto_resume_same_package_after_network_failure(self):
        self.state.job={'status':'starting','started':100,'logs':[],'sha256':'a'*64}
        calls=[]
        def attempt(*args):
            calls.append(args)
            self.state.job.update(status='failed' if len(calls)==1 else 'complete',retryable=True,finished=120)
        with patch.object(self.state,'_attempt',side_effect=attempt),patch.object(self.state.stop_event,'wait',return_value=False) as wait:
            self.state.worker(Path('/same-package'),'b'*64,'/port','test-only-password',False,3,True,7)
        self.assertEqual(len(calls),2);self.assertEqual(calls[0],calls[1])
        wait.assert_called_once_with(420)
        self.assertEqual(self.state.job['status'],'complete');self.assertEqual(self.state.job['attempt'],2)
        self.assertNotIn('test-only-password',json.dumps(self.state.job))
    def test_auto_resume_stop_and_fatal_failure(self):
        self.state.job={'status':'starting','started':100,'logs':[],'sha256':'a'*64}
        def fatal(*args):self.state.job.update(status='failed',retryable=False)
        with patch.object(self.state,'_attempt',side_effect=fatal) as attempt,patch.object(self.state.stop_event,'wait') as wait:
            self.state.worker(Path('/same'),'b'*64,'/port','secret',False,2,True,1)
        attempt.assert_called_once();wait.assert_not_called()
        self.state.job.update(status='starting')
        def network(*args):self.state.job.update(status='failed',retryable=True)
        def stop(seconds):self.state.stop();return True
        with patch.object(self.state,'_attempt',side_effect=network) as attempt,patch.object(self.state.stop_event,'wait',side_effect=stop):
            self.state.worker(Path('/same'),'b'*64,'/port','secret',False,2,True,1)
        attempt.assert_called_once();self.assertEqual(self.state.job['status'],'stopped')
    def test_auto_resume_rejects_invalid_delay_and_activation(self):
        for value in (0,16,True,1.5,'5'):
            status,body=self.request('/api/start',{'retry_minutes':value})
            self.assertEqual(status,400);self.assertIn('1–15',body['error'])
        status,body=self.request('/api/start',{'auto_resume':True,'activate':True})
        self.assertEqual(status,400);self.assertIn('activate separately',body['error'])

    def test_invalid_packet_delays_do_not_start_transfer(self):
        for pace in (0,-1,31,True,'5',None,float('inf'),float('nan')):
            self.assertEqual(self.request('/api/start',{'pace':pace})[0],400)
            self.assertIsNone(self.state.job)

    def test_elapsed_eta_resumed_upload_and_activation_command(self):
        job={'started':100,'progress_started':110,'resume_offset':20000,'sent':21000,'total':30000,'status':'running','sha256':'844497f0'+'a'*56}
        status=ota_web.transfer_timing(job,now=130)
        self.assertEqual(status['elapsed_seconds'],30)
        self.assertEqual(status['eta_seconds'],180)
        self.assertEqual(status['activation_command'],'pm ota apply 844497f0')
        self.assertNotIn('elapsed_seconds',job)
        self.assertIsNone(ota_web.transfer_timing(job,now=115)['eta_seconds'])
        stopped=dict(job,status='failed',finished=140)
        status=ota_web.transfer_timing(stopped,now=999)
        self.assertEqual(status['elapsed_seconds'],40)
        self.assertIsNone(status['eta_seconds'])

    def test_incomplete_tls_does_not_block_other_visitors(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
        import datetime
        key=ec.generate_private_key(ec.SECP256R1())
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
        now=datetime.datetime.now(datetime.timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now-datetime.timedelta(minutes=1))
              .not_valid_after(now+datetime.timedelta(days=1)).sign(key,hashes.SHA256()))
        certfile=Path(self.folder.name)/'cert.pem';keyfile=Path(self.folder.name)/'tls.pem'
        certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        server=ota_web.TLSHTTPServer(('127.0.0.1',0),ota_web.Handler)
        server.state=self.state;server.tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server.tls.load_cert_chain(certfile,keyfile)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        stalled=socket.create_connection(server.server_address,timeout=2)
        try:
            context=ssl.create_default_context(cafile=str(certfile))
            connection=http.client.HTTPSConnection('localhost',server.server_port,context=context,timeout=2)
            connection.request('GET','/api/status')
            response=connection.getresponse()
            self.assertEqual(response.status,401);response.read();connection.close()
        finally:
            stalled.close();server.shutdown();server.server_close()

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
        manifest={'lora_ota':True,'ota_storage':'RAK15001 slot C; JEDEC C84015','version':'0.4.2-test','ota_bootloader_sha256':lora_ota.BOOT_HASH,'ota_target':lora_ota.TARGET_NAME,'firmware':{'firmware.bin':{'bytes':len(binary),'sha256':hashlib.sha256(binary).hexdigest()}}}
        status,result=self.request('/api/prepare',{'firmware':base64.b64encode(binary).decode(),'name':'firmware.bin','manifest':manifest})
        self.assertEqual(status,200);self.assertIsNone(self.state.job);self.assertIsNone(self.state.process)
        self.assertTrue((self.state.packages/(result['sha256']+'.mota')).exists())
        path='/packages/'+result['sha256']+'.mota'
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request('GET',path,headers={'Authorization':'Basic '+base64.b64encode(b'admin:test-only-password').decode()})
        response=connection.getresponse()
        self.assertEqual(response.status,200)
        self.assertEqual(response.getheader('Content-Type'),'application/octet-stream')
        self.assertIn('attachment;',response.getheader('Content-Disposition'))
        self.assertEqual(response.read(),(self.state.packages/(result['sha256']+'.mota')).read_bytes())
        connection.close()
        self.assertEqual(self.request(path,auth=False)[0],401)
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
            self.state.start({'sha256':info['sha256'],'target':'b'*64,'port':'/dev/test-companion','password':'private-test-value','activate':False,'pace':5})
        self.assertNotIn('private-test-value',json.dumps(self.state.job));self.assertFalse(self.state.job['activate']);self.assertEqual(self.state.job['pace'],5)
        class Pipe(io.StringIO):
            def close(self):pass
        class Process:
            stdin=Pipe();stdout=iter(['private-test-value\n','PM_ROUTE '+json.dumps({'known':True,'target':'Target','hops':[],'hop_count':0})+'\n','PM_PROGRESS 40 5000\n'])
            def wait(self):return 0
        with patch('subprocess.Popen',return_value=Process()) as spawned:
            self.state.worker(self.state.packages/(info['sha256']+'.mota'),'b'*64,'/dev/test-companion','private-test-value',False,5)
        self.assertNotIn('private-test-value',json.dumps(self.state.job))
        self.assertNotIn('private-test-value',' '.join(spawned.call_args.args[0]))
        self.assertEqual(self.state.job['route']['hop_count'],0);self.assertEqual(spawned.call_args.args[0][-2:],['--pace','5']);self.assertNotIn('--apply',spawned.call_args.args[0]);self.assertEqual(self.state.job['sent'],40)
    def test_dfu_zip_can_be_renamed_and_old_profile_rejected(self):
        self.state.create_key();binary=bytearray(b'\x55'*5000);struct.pack_into('<II',binary,0,0x2003f000,0x26021)
        import binascii
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('manifest.json',json.dumps({'manifest':{'dfu_version':0.5,'application':{'bin_file':'firmware.bin','dat_file':'firmware.dat'}}}))
            z.writestr('firmware.bin',binary)
            z.writestr('firmware.dat',struct.pack('<HHIHHH',82,52840,0xffffffff,1,0xb6,binascii.crc_hqx(binary,0xffff)))
        data=archive.getvalue()
        manifest={'lora_ota':True,'ota_storage':'RAK15001 slot C; JEDEC C84015','version':'0.4.2-test','ota_bootloader_sha256':lora_ota.BOOT_HASH,'ota_target':lora_ota.TARGET_NAME,'firmware':{'real.zip':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},'real.bin':{'bytes':len(binary),'sha256':hashlib.sha256(binary).hexdigest()}}}
        request={'name':'renamed-download.zip','firmware':base64.b64encode(data).decode(),'manifest':manifest}
        result=self.state.prepare(request)
        self.assertEqual(result['image_bytes'],5056);self.assertIsNone(self.state.job)
        del manifest['ota_bootloader_sha256']
        with self.assertRaises(ValueError):self.state.prepare(request)

if __name__=='__main__':unittest.main()
