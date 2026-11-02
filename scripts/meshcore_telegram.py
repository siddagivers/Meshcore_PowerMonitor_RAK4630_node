#!/usr/bin/env python3
"""Forward new incoming MeshCore private messages through the existing Telegram helper.

This service only reads the inbox database. It never opens the companion port.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import time

class Forwarder:
    def __init__(self,inbox,state,helper):
        if not Path(inbox).is_file():raise RuntimeError('Inbox database is not available yet')
        self.source=sqlite3.connect(Path(inbox).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
        self.source.row_factory=sqlite3.Row
        self.db=sqlite3.connect(state,timeout=5);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS cursor(id INTEGER PRIMARY KEY CHECK(id=1),event_id INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox(event_id INTEGER PRIMARY KEY,message TEXT,status TEXT,attempts INTEGER,next_try REAL)')
        latest=self.source.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
        self.db.execute('INSERT OR IGNORE INTO cursor VALUES(1,?)',(latest,))
        self.db.execute("UPDATE outbox SET status='pending' WHERE status='sending'")
        self.db.commit();self.helper=str(helper)
    @staticmethod
    def eligible(row):
        if row['kind']!='contact_message' or row['direction']!='in':return False
        try:payload=json.loads(row['payload'])
        except (TypeError,ValueError):return False
        return isinstance(payload,dict) and payload.get('txt_type',0)==0 and bool(row['text'])
    def sender(self,peer):
        row=self.source.execute("SELECT value FROM cache WHERE name='contacts'").fetchone()
        try:contacts=json.loads(row[0]) if row else []
        except ValueError:contacts=[]
        matches=[c for c in contacts if peer and c.get('public_key','').startswith(peer)]
        return matches[0].get('adv_name') or peer if len(matches)==1 else peer or 'Unknown contact'
    def collect(self):
        cursor=self.db.execute('SELECT event_id FROM cursor WHERE id=1').fetchone()[0]
        rows=self.source.execute('SELECT * FROM events WHERE id>? ORDER BY id LIMIT 500',(cursor,)).fetchall()
        with self.db:
            for row in rows:
                if self.eligible(row):
                    peer=row['peer'] or ''
                    message='MeshCore private message\nFrom: '+self.sender(peer)+' ['+peer+']\n\n'+row['text']
                    self.db.execute("INSERT OR IGNORE INTO outbox VALUES(?,?,'pending',0,0)",(row['id'],message))
            if rows:self.db.execute('UPDATE cursor SET event_id=? WHERE id=1',(rows[-1]['id'],))
    def deliver_one(self,now=None,runner=subprocess.run):
        now=time.time() if now is None else now
        row=self.db.execute("SELECT * FROM outbox WHERE status='pending' AND next_try<=? ORDER BY event_id LIMIT 1",(now,)).fetchone()
        if not row:return False
        attempts=row['attempts']+1
        with self.db:self.db.execute("UPDATE outbox SET status='sending',attempts=? WHERE event_id=?",(attempts,row['event_id']))
        try:
            # Plain text over stdin: no shell expansion, message in process
            # arguments, credential logging, Markdown or HTML interpolation.
            result=runner([self.helper,'-D','-'],input=row['message'],text=True,cwd=str(Path.home()),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=30)
            sent=result.returncode==0
            if sent:
                try:reply=json.loads(result.stdout or '{}');sent=not isinstance(reply,dict) or reply.get('ok',True) is not False
                except (ValueError,TypeError):pass
        except (OSError,subprocess.TimeoutExpired):sent=False
        status='sent' if sent else 'failed' if attempts>=5 else 'pending'
        with self.db:self.db.execute('UPDATE outbox SET status=?,next_try=? WHERE event_id=?',(status,now+min(900,60*2**(attempts-1)),row['event_id']))
        return True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox',type=Path,required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--helper',type=Path,default=Path('/home/pi/tools/telegram.sh/telegram'))
    args=parser.parse_args()
    import os
    os.umask(0o077);args.state.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not os.access(args.helper,os.X_OK):raise RuntimeError('Configured Telegram helper is not executable')
    forwarder=Forwarder(args.inbox,args.state,args.helper)
    print('Telegram forwarding enabled for new incoming private messages only',flush=True)
    while True:
        try:forwarder.collect();forwarder.deliver_one()
        except sqlite3.Error:print('Inbox temporarily busy; retrying without opening the radio',flush=True)
        time.sleep(3)

if __name__=='__main__':main()
