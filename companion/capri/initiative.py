"""Local deterministic eligibility; observations never acquire an execution lease."""
from datetime import datetime
import hashlib
import json
import random
import time
from zoneinfo import ZoneInfo
from .broker import Denied

class Scheduler:
    def __init__(self,store,profile,wall=time.time,monotonic=time.monotonic,partition=None):
        self.store=store;self.profile=profile;self.wall=wall;self.monotonic=monotonic;self.partition=partition or (lambda:"local-owner")
        saved=store.value('local-owner','initiative-clock',{})
        now=wall();elapsed=now-saved.get('wall',now)
        self.logical=saved.get('logical',0)+(elapsed if 0<=elapsed<=172800 else 0)
        self.last_mono=monotonic();self.notice=None
        self.state=store.value('local-owner','initiative-budget',{'bubbles':[],'models':[],'topics':{},'snooze':0,'next_social':0})
        if not self.state.get('next_social'):self.next_social()
        self.save()
    def next_social(self):
        p=self.profile();self.state['next_social']=self.now()+random.uniform(p['min_gap_minutes']*60,p['max_gap_minutes']*60)
    def activity(self,source_id,status):
        self.state['activity']={'id':str(source_id),'status':status,'when':self.now(),'partition':self.partition()}
        self.save()
    def social_tick(self):
        now=self.now()
        if now<self.state['next_social']:return
        self.next_social();activity=self.state.get('activity')
        if activity and activity.get('partition')==self.partition() and now-activity['when']<86400 and activity['id']!=self.state.get('last_social'):
            self.offer('owner-task','recent-work','check-in',{'status':activity['status'],'cloud':False},'check-in:'+activity['id'])
            self.state['last_social']=activity['id']
        self.save()
    def now(self):
        current=self.monotonic();self.logical+=max(0,current-self.last_mono);self.last_mono=current;return self.logical
    def save(self):
        now=self.now()
        self.state['bubbles']=[t for t in self.state['bubbles'] if 0<=now-t<86400]
        self.state['models']=[t for t in self.state['models'] if 0<=now-t<86400]
        self.state['topics']={k:v for k,v in self.state['topics'].items() if v>now-86400}
        self.store.set_value('local-owner','initiative-clock',{'logical':now,'wall':self.wall()})
        self.store.set_value('local-owner','initiative-budget',self.state)
    def quiet_hours(self):
        p=self.profile();start=p['quiet_start'];end=p['quiet_end']
        if not start or not end or start==end:return False
        current=datetime.fromtimestamp(self.wall(),ZoneInfo(p.get('timezone','America/Edmonton'))).strftime('%H:%M')
        return start<=current<end if start<end else current>=start or current<end
    def offer(self,source,topic,kind,payload,source_id):
        if source not in ('owner-task','selected-project','selected-mail'):raise Denied('Unregistered observation source')
        if not isinstance(payload,dict) or len(json.dumps(payload))>6000:raise Denied('Observation exceeds local bounds')
        identity=hashlib.sha256((source+':'+str(source_id)).encode()).hexdigest()
        with self.store.db:
            self.store.db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?)',(identity,source,topic,kind,json.dumps({'partition':self.partition(),'data':payload}),self.now(),'pending'))
            # Bound retained observations; no growing screen/mail transcript.
            self.store.db.execute('DELETE FROM observations WHERE id IN (SELECT id FROM observations ORDER BY created DESC LIMIT -1 OFFSET 500)')
        return identity
    def blocked(self,attention):
        p=self.profile();now=self.now()
        return (p['quiet'] or p['paused'] or p['dnd'] or not p['initiative'] or self.quiet_hours() or
                now<self.state['snooze'] or not attention.get('unlocked') or not attention.get('input_idle') or
                attention.get('fullscreen') or attention.get('busy') or attention.get('hidden') or
                attention.get('desktop_dnd') is not False)
    def current_notice(self):
        return self.notice if self.notice and self.notice.get('partition')==self.partition() else None
    def eligible(self,attention):
        self.social_tick();self.save();now=self.now();p=self.profile()
        if self.notice and self.notice.get('partition')!=self.partition():self.notice=None
        if self.notice:
            if now-self.notice['shown']>=90:self.dismiss()
            else:return None
        if self.blocked(attention):return None
        if len(self.state['bubbles'])>=p['daily_bubbles'] or sum(now-t<3600 for t in self.state['bubbles'])>=p['hourly_bubbles']:return None
        rows=self.store.db.execute("SELECT id,source,topic,kind,payload,created FROM observations WHERE status='pending' AND created<=? ORDER BY created DESC LIMIT 40",(now-30,)).fetchall()
        rows=[r for r in rows if now-r[5]<86400 and self.state['topics'].get(r[2],0)<=now and json.loads(r[4]).get('partition')==self.partition()]
        if not rows:return None
        latest=rows[0]
        return {'ids':[r[0] for r in rows],'source':latest[1],'topic':latest[2],'kind':latest[3],'payload':json.loads(latest[4])['data'],'coalesced':len(rows)}
    def reserve_model(self):
        self.save();limit=self.profile()['daily_model_requests']
        if len(self.state['models'])>=limit:return False
        self.state['models'].append(self.now());self.save();return True
    def present(self,candidate,text,why):
        now=self.now();identity=hashlib.sha256(('|'.join(candidate['ids'])).encode()).hexdigest()
        self.notice={'partition':self.partition(),'id':identity,'topic':candidate['topic'],'text':text[:1200],'why':why[:1600],'shown':now,'source':candidate['source'],'payload':candidate['payload']}
        self.state['bubbles'].append(now);self.state['topics'][candidate['topic']]=now+10800
        with self.store.db:
            self.store.db.executemany("UPDATE observations SET status='coalesced' WHERE id=?",[(i,) for i in candidate['ids']])
            self.store.db.execute('INSERT OR REPLACE INTO notices VALUES(?,?,?,?,?,?,?)',(identity,candidate['topic'],candidate['kind'],text[:1200],why[:1600],'shown',self.wall()))
        self.save();return self.notice
    def dismiss(self):
        if self.notice:
            with self.store.db:self.store.db.execute("UPDATE notices SET status='dismissed' WHERE id=?",(self.notice['id'],))
            self.state['topics'][self.notice['topic']]=self.now()+10800
        self.notice=None;self.save()
    def snooze(self,minutes):
        if type(minutes) is not int or not 1<=minutes<=1440:raise Denied('Snooze must be 1..1440 minutes')
        self.state['snooze']=self.now()+minutes*60;self.dismiss()
