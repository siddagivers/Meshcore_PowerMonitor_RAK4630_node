"""Exercise the actual uploader request method without transmitting on a radio."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
spec=importlib.util.spec_from_file_location('ota',Path(__file__).resolve().parents[1]/'scripts/lora_ota.py')
ota=importlib.util.module_from_spec(spec);spec.loader.exec_module(ota)
sys.modules['meshcore']=types.SimpleNamespace(EventType=types.SimpleNamespace(CONTACT_MSG_RECV=1,ERROR=2))
class Subscription:
    def __init__(self,radio):self.radio=radio
    def unsubscribe(self):self.radio.active=False
class Fake:
    def __init__(self):self.commands=self;self.calls=[];self.drop=1;self.active=False
    def subscribe(self,event,callback,filters):
        assert filters=={'pubkey_prefix':'a'*12}
        self.callback=callback;self.active=True;return Subscription(self)
    async def send_cmd(self,contact,text):
        assert self.active
        self.calls.append(text)
        self.callback(types.SimpleNamespace(payload={'text':'ZZ|stale response'}))
        if self.drop:self.drop-=1
        else:self.callback(types.SimpleNamespace(payload={'text':text[:3]+'OK data next=40'}))
        return types.SimpleNamespace(type=0)
async def main():
    fake=Fake();radio=ota.Radio(fake,{'public_key':'a'*64},timeout=0.001,retries=2,pace=0)
    original=ota.asyncio.sleep
    async def immediate(_):pass
    ota.asyncio.sleep=immediate
    try:
        response=await radio.request('pm ota data 01234567 0 aa')
        assert response=='OK data next=40' and len(fake.calls)==2 and not fake.active
        assert fake.calls[0][:3]!=fake.calls[1][:3]
        fake.drop=10
        try:await radio.request('pm ota status')
        except TimeoutError:pass
        else:raise AssertionError('unbounded retry/no timeout')
        assert not fake.active
    finally:ota.asyncio.sleep=original
asyncio.run(main())
print('PASS: uploader subscribes before transmit, correlates replies, retries lost ACKs and stops after bounded failure')
