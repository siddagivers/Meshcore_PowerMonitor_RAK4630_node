from pathlib import Path
import json
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from meshcore_telegram import Forwarder

class ForwardTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=self.root/'inbox.sqlite3';self.source=sqlite3.connect(self.path)
        self.source.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,kind TEXT,direction TEXT,peer TEXT,text TEXT,payload TEXT)')
        self.source.execute('CREATE TABLE cache(name TEXT PRIMARY KEY,value TEXT)')
        self.source.execute('INSERT INTO cache VALUES(?,?)',('contacts',json.dumps([{'public_key':'a'*64,'adv_name':'Friend'}])))
        self.source.commit()
    def tearDown(self):self.source.close();self.folder.cleanup()
    def add(self,kind='contact_message',direction='in',text='Hello',txt_type=0):
        self.source.execute('INSERT INTO events(kind,direction,peer,text,payload) VALUES(?,?,?,?,?)',(kind,direction,'a'*12,text,json.dumps({'txt_type':txt_type})));self.source.commit()
    def forwarder(self):return Forwarder(self.path,self.root/'telegram.sqlite3','/existing/telegram')
    def test_new_private_only_no_history_replay_or_duplicates(self):
        self.add(text='Old message')
        f=self.forwarder();f.collect()
        self.assertEqual(f.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],0)
        self.add(text='Private -M <tag> žluťoučký')
        self.add(kind='channel_message');self.add(kind='telemetry_response');self.add(kind='acknowledgement')
        self.add(direction='out');self.add(txt_type=1)
        f.collect();f.collect()
        self.assertEqual(f.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],1)
        calls=[]
        def send(args,**kwargs):calls.append((args,kwargs));return SimpleNamespace(returncode=0,stdout='{"ok":true}')
        self.assertTrue(f.deliver_one(now=100,runner=send));self.assertFalse(f.deliver_one(now=101,runner=send))
        self.assertEqual(calls[0][0],['/existing/telegram','-D','-'])
        self.assertIn('Friend',calls[0][1]['input']);self.assertIn('Private -M <tag> žluťoučký',calls[0][1]['input'])
        self.assertNotIn('shell',calls[0][1])
        f.source.close();f.db.close();again=self.forwarder();again.collect()
        self.assertFalse(again.deliver_one(now=999,runner=send));again.source.close();again.db.close()
    def test_failure_retries_are_bounded_and_survive_restart(self):
        f=self.forwarder();self.add();f.collect()
        def fail(*args,**kwargs):return SimpleNamespace(returncode=1,stdout='')
        self.assertTrue(f.deliver_one(now=100,runner=fail));self.assertFalse(f.deliver_one(now=159,runner=fail))
        f.source.close();f.db.close();f=self.forwarder()
        for moment in (160,1000,2000,3000):f.deliver_one(now=moment,runner=fail)
        row=f.db.execute('SELECT status,attempts FROM outbox').fetchone()
        self.assertEqual(tuple(row),('failed',5));f.source.close();f.db.close()

if __name__=='__main__':unittest.main()
