"""No-radio tests for inbox persistence, queueing and collector compatibility."""
import asyncio
import base64
import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import meshcore_inbox as inbox
import ota_gateway
import companion_meshcli
from meshcore import EventType

class StoreTest(unittest.TestCase):
    def test_collector_bridge_json_and_legacy_fallback(self):
        import io
        argv=['bridge','-s','/dev/test-companion','req_telemetry','SK-RK-SIPRUN']
        status={'online':True,'port':'/dev/test-companion'}
        result={'name':'SK-RK-SIPRUN','lpp':[{'channel':1,'type':'voltage','value':4.1}]}
        with patch('sys.argv',argv),patch.object(companion_meshcli,'SOCKET',SimpleNamespace(exists=lambda:True)),patch.object(companion_meshcli,'call_sync',side_effect=[status,result]) as rpc,patch('sys.stdout',new_callable=io.StringIO) as output:
            companion_meshcli.main()
            self.assertEqual(json.loads(output.getvalue()),result)
            self.assertEqual(rpc.call_args.args[0],{'op':'telemetry','target':'SK-RK-SIPRUN'})
        with patch('sys.argv',argv),patch.object(companion_meshcli,'SOCKET',SimpleNamespace(exists=lambda:False)),patch('os.execv',side_effect=RuntimeError('fallback')) as execute:
            with self.assertRaisesRegex(RuntimeError,'fallback'):companion_meshcli.main()
            self.assertEqual(execute.call_args.args[0],'/home/pi/.local/bin/meshcli')

    def test_restart_and_receive_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'messages.db';store=inbox.Store(path)
            message={'pubkey_prefix':'aa','sender_timestamp':123,'text':'Hello <script>','txt_type':0}
            store.save('contact_message',message,text=message['text'],dedup=True)
            store.save('contact_message',dict(message,SNR=3),text=message['text'],dedup=True)
            store.cache('contacts',[{'public_key':'a'*64,'adv_name':'Node'}])
            again=inbox.Store(path)
            self.assertEqual(len(again.events()),1)
            self.assertEqual(again.events()[0]['text'],'Hello <script>')
            self.assertEqual(again.cache('contacts')[0]['adv_name'],'Node')
    def test_http_auth_and_csrf_no_radio(self):
        with tempfile.TemporaryDirectory() as d:
            store=inbox.Store(Path(d)/'messages.db');hub=inbox.Hub(store,'/not-a-device','/unused')
            server=ThreadingHTTPServer(('127.0.0.1',0),inbox.ChatHandler)
            salt=b'test-only';server.state=SimpleNamespace(auth={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',b'test',salt,200000).hex()})
            server.hub=hub;server.store=store
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                c=http.client.HTTPConnection(*server.server_address);c.request('GET','/api/state');r=c.getresponse();self.assertEqual(r.status,401);r.read();c.close()
                headers={'Authorization':'Basic '+base64.b64encode(b'admin:test').decode()}
                c=http.client.HTTPConnection(*server.server_address);c.request('GET','/api/state',headers=headers);r=c.getresponse();self.assertFalse(json.loads(r.read())['connection']['online']);c.close()
                c=http.client.HTTPConnection(*server.server_address);c.request('POST','/api/send',b'{}',headers);r=c.getresponse();self.assertEqual(r.status,403);r.read();c.close()
            finally:server.shutdown();server.server_close()

class HubTest(unittest.IsolatedAsyncioTestCase):
    async def test_login_captures_immediate_reply_and_checks_sender(self):
        with tempfile.TemporaryDirectory() as d:
            hub=inbox.Hub(inbox.Store(Path(d)/'db'),'/none','/none');callbacks={}
            contact={'public_key':'a'*64}
            def subscribe(kind,callback):callbacks[kind]=callback;return SimpleNamespace(unsubscribe=lambda:None)
            async def send(contact,password):
                self.assertIn(EventType.LOGIN_SUCCESS,callbacks)
                callbacks[EventType.LOGIN_FAILED](SimpleNamespace(type=EventType.LOGIN_FAILED,payload={'pubkey_prefix':'b'*12}))
                callbacks[EventType.LOGIN_SUCCESS](SimpleNamespace(type=EventType.LOGIN_SUCCESS,payload={'pubkey_prefix':'a'*12,'is_admin':True}))
                return SimpleNamespace(type=EventType.OK)
            hub.mc=SimpleNamespace(subscribe=subscribe,commands=SimpleNamespace(send_login=send))
            self.assertEqual(await hub.login(contact,'test-only'),{'logged_in':True})
            async def reject(contact,password):
                callbacks[EventType.LOGIN_FAILED](SimpleNamespace(type=EventType.LOGIN_FAILED,payload={'pubkey_prefix':'a'*12}))
                return SimpleNamespace(type=EventType.OK)
            hub.mc.commands.send_login=reject
            with self.assertRaisesRegex(RuntimeError,'explicitly rejected'):await hub.login(contact,'test-only')

    async def test_ota_waits_for_telemetry_before_send(self):
        with tempfile.TemporaryDirectory() as d:
            hub=inbox.Hub(inbox.Store(Path(d)/'db'),'/none','/none');hub.online=True
            contact={'public_key':'a'*64,'adv_name':'Repeater'};calls=[];callbacks=[]
            def subscribe(kind,callback,filters=None):callbacks.append(callback);return SimpleNamespace(unsubscribe=lambda:None)
            async def send(contact,text):
                calls.append(text)
                for callback in callbacks:callback(SimpleNamespace(payload={'text':text[:3]+'OK data next=40'}))
                return SimpleNamespace(type=EventType.OK)
            hub.mc=SimpleNamespace(contacts={'a'*64:contact},subscribe=subscribe,commands=SimpleNamespace(send_cmd=send))
            await hub.lock.acquire()
            task=asyncio.create_task(hub.command({'op':'admin','target':'a'*64,'command':'pm ota status','pace':1}))
            await asyncio.sleep(.02);self.assertEqual(calls,[])
            hub.lock.release();result=await asyncio.wait_for(task,1)
            self.assertEqual(result['reply'],'OK data next=40');self.assertEqual(len(calls),1)
    async def test_collector_json_contract(self):
        with tempfile.TemporaryDirectory() as d:
            hub=inbox.Hub(inbox.Store(Path(d)/'db'),'/none','/none');hub.online=True
            contact={'public_key':'a'*64,'adv_name':'SK-RK-SIPRUN'};callbacks=[]
            def subscribe(kind,callback,filters=None):callbacks.append(callback);return SimpleNamespace(unsubscribe=lambda:None)
            lpp=[{'channel':1,'type':'voltage','value':4.1}]
            async def send(contact,timeout):
                for callback in callbacks:callback(SimpleNamespace(payload={'pubkey_pre':'a'*12,'lpp':lpp}))
                return lpp
            hub.mc=SimpleNamespace(contacts={'a'*64:contact},subscribe=subscribe,commands=SimpleNamespace(req_telemetry_sync=send))
            result=await hub.command({'op':'telemetry','target':'SK-RK-SIPRUN'})
            self.assertEqual(result,{'name':'SK-RK-SIPRUN','pubkey_pre':'a'*16,'lpp':lpp})
    async def test_gateway_resume_without_retransmission_or_apply(self):
        requests=[]
        async def call(request,timeout=180):
            requests.append(request);op=request['op']
            if op=='status':return {'online':True}
            if op=='route':return {'contact':{'public_key':'a'*64,'out_path_len':0},'route':{'known':True,'hops':[],'hop_count':0}}
            if op=='login':return {'logged_in':True}
            command=request['command']
            if command=='pm ota status':reply='OTA cli1 pair=1 boot=1 flash=2097152'
            elif command.startswith('pm ota begin'):reply='OK begin next=40'
            elif command.startswith('pm ota data'):reply='OK data next='+str(int(command.split()[4])+40)
            else:reply='OK verified 12345678'
            return {'reply':reply}
        args=SimpleNamespace(target='a'*64,password_stdin=True,pace=3,apply=False)
        import io
        with patch.object(ota_gateway,'call',call),patch('sys.stdin',io.StringIO('test-only-password\n')):
            await ota_gateway.upload(args,b'x'*120,{'sha256':'12345678'+'b'*56})
        commands=[r['command'] for r in requests if r['op']=='admin']
        offsets=[int(c.split()[4]) for c in commands if c.startswith('pm ota data')]
        self.assertEqual(offsets,[40,80]);self.assertFalse(any(c.startswith('pm ota apply') for c in commands))

if __name__=='__main__':unittest.main()
