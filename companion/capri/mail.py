"""Own-account Gmail desktop OAuth and bounded read-only polling; no mail tools."""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import time
from urllib.parse import parse_qs,urlparse,urlencode

from .broker import Denied
from .provider import atomic_private,private_json

AUTH='https://accounts.google.com/o/oauth2/v2/auth'
TOKEN='https://oauth2.googleapis.com/token'
API='https://gmail.googleapis.com/gmail/v1/users/me'
SCOPES={'metadata':'https://www.googleapis.com/auth/gmail.metadata','body':'https://www.googleapis.com/auth/gmail.readonly'}


def selection(labels,summary,cloud):
    if not isinstance(labels,list) or not 1<=len(labels)<=8 or not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',v) for v in labels):raise Denied('Choose one to eight exact Gmail label IDs')
    if summary not in SCOPES or type(cloud) is not bool:raise Denied('Choose metadata or plain-text summary and an explicit cloud-sharing preference')
    return {'labels':list(dict.fromkeys(labels)),'summary':summary,'cloud':cloud}


def plain_body(payload):
    """No HTML rendering, external resources, attachment reads or execution."""
    result=[]
    def walk(part,depth=0):
        if depth>12 or not isinstance(part,dict) or part.get('filename'):return
        if part.get('mimeType')=='text/plain':
            body=part.get('body',{});data=body.get('data','')
            if isinstance(data,str) and len(data)<=350000 and not body.get('attachmentId'):
                try:result.append(base64.b64decode(data+'='*((-len(data))%4),altchars=b'-_',validate=True).decode(errors='replace')[:16000])
                except (ValueError,TypeError):pass
        for child in part.get('parts',[])[:30]:walk(child,depth+1)
    walk(payload)
    return '\n'.join(result)[:16000]

class Gmail:
    def __init__(self,directory,store,partition,offer):
        self.directory=Path(directory);self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.store=store;self.partition=partition;self.offer=offer;self.http=None
        self.record=None;self.bound=None;self.listener=None;self.pending=None;self.lock=asyncio.Lock()
        self.next_poll=0;self.failures=0;self.bodies={};self.polling=None
        self.status='Not connected. Choose a Gmail Desktop app OAuth client JSON in Settings.'
        self.load()
    def path(self):return self.directory/(hashlib.sha256(self.partition().encode()).hexdigest()+'.json')
    def load(self):
        self.bodies.clear();self.record=None;self.bound=self.partition();self.next_poll=0
        if self.path().exists():self.record=private_json(self.path());self.status='Connected read-only: '+self.record['email']+' · '+self.record['selection']['summary']
    async def client(self):
        if self.http is None:
            import httpx
            self.http=httpx.AsyncClient(timeout=30,follow_redirects=False,trust_env=False)
        return self.http
    def valid(self):return self.bound==self.partition() and self.record is not None
    async def connect(self,registration,labels,summary,cloud,notify):
        choice=selection(labels,summary,cloud)
        path=Path(registration)
        if not path.is_absolute():raise Denied('Select the local Desktop app client JSON path')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            if os.fstat(stream.fileno()).st_uid!=os.getuid() or os.fstat(stream.fileno()).st_size>32000:raise Denied('OAuth registration must be a small owner-owned JSON file')
            client=json.load(stream).get('installed')
        if not isinstance(client,dict) or not re.fullmatch(r'[A-Za-z0-9_.-]{10,250}\.apps\.googleusercontent\.com',str(client.get('client_id',''))):raise Denied('Use an official Google Desktop app OAuth registration, not a web client')
        if self.pending:raise Denied('Gmail sign-in is already pending')
        binding=self.partition();state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
        future=asyncio.get_running_loop().create_future();self.pending=future
        async def callback(reader,writer):
            accepted=False
            try:
                raw=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),3)
                if len(raw)>8192:raise Denied('OAuth callback too large')
                method,target,_=raw.split(b'\r\n',1)[0].decode('ascii').split(' ',2)
                parsed=urlparse(target);values=parse_qs(parsed.query,max_num_fields=16)
                if method!='GET' or parsed.path!='/oauth/callback' or any(len(v)!=1 for v in values.values()) or not secrets.compare_digest(values.get('state',[''])[0],state) or future.done() or binding!=self.partition():raise Denied('OAuth callback identity mismatch')
                if 'error' in values:future.set_exception(Denied('Gmail consent was declined'))
                else:
                    code=values.get('code',[''])[0]
                    if not code or len(code)>4096:raise Denied('Invalid authorization code')
                    future.set_result(code);accepted=True
            except (ValueError,OSError,asyncio.TimeoutError):pass
            finally:
                writer.write(b'HTTP/1.1 '+(b'200 OK' if accepted else b'400 Bad Request')+b'\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nReturn to Capri. Account validation is still in progress.')
                await writer.drain();writer.close();await writer.wait_closed()
        self.listener=await asyncio.start_server(callback,'127.0.0.1',0,limit=8192)
        port=self.listener.sockets[0].getsockname()[1];redirect=f'http://127.0.0.1:{port}/oauth/callback'
        # Authlib implements standard OAuth authorization-code PKCE/state handling.
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        oauth=AsyncOAuth2Client(client_id=client['client_id'],client_secret=client.get('client_secret'),scope=SCOPES[summary],redirect_uri=redirect,code_challenge_method='S256',token_endpoint_auth_method='client_secret_post',timeout=30,follow_redirects=False,trust_env=False)
        try:
            url,_=oauth.create_authorization_url(AUTH,state=state,code_verifier=verifier,access_type='offline',prompt='consent')
            proc=await asyncio.create_subprocess_exec('/usr/bin/python3',str(Path(__file__).with_name('portal_open.py')),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            try:await asyncio.wait_for(proc.communicate(url.encode()),45)
            finally:
                if proc.returncode is None:proc.terminate();await proc.wait()
            if proc.returncode:raise Denied('System browser did not accept Gmail sign-in')
            self.status='Complete read-only Gmail consent in your system browser.';await notify()
            code=await asyncio.wait_for(future,600)
            token=await oauth.fetch_token(TOKEN,code=code,code_verifier=verifier)
            if binding!=self.partition():raise Denied('Capri account changed during Gmail setup')
            scopes=token.get('scope',SCOPES[summary]).split()
            if set(scopes)!={SCOPES[summary]}:raise Denied('Google returned different scopes; no mail account was connected')
            record={'client_id':client['client_id'],'client_secret':client.get('client_secret',''),'token':dict(token),'selection':choice,'email':'pending'}
            self.record=record;self.bound=binding
            profile=await self.read('profile');email=profile.get('emailAddress')
            if not isinstance(email,str) or not 3<=len(email)<=254:raise Denied('Gmail account identity was not returned')
            record['email']=email;atomic_private(self.path(),record)
            self.status='Connected read-only: '+email+' · '+summary;self.next_poll=0;await notify()
        except BaseException:
            self.load();raise
        finally:
            await oauth.aclose();self.listener.close()
            if not future.done():future.cancel()
            self.listener=None;self.pending=None
    async def access_token(self):
        async with self.lock:
            if not self.valid():raise Denied('Gmail account unavailable for this Capri account')
            account=self.record
            token=account['token']
            if token.get('expires_at',0)<=time.time()+60:
                if not token.get('refresh_token'):raise Denied('Reconnect Gmail to renew its read-only permission')
                response=await (await self.client()).post(TOKEN,data={'client_id':self.record['client_id'],'client_secret':self.record['client_secret'],'grant_type':'refresh_token','refresh_token':token['refresh_token']})
                if response.status_code!=200:raise Denied('Gmail token renewal failed; reconnect the account')
                if not self.valid() or self.record is not account:raise Denied('Account changed during Gmail renewal')
                refreshed=response.json()
                if 'scope' in refreshed and set(refreshed['scope'].split())!={SCOPES[self.record['selection']['summary']]}:raise Denied('Gmail scope changed; reconnect the read-only account')
                self.record['token']={**token,**refreshed,'expires_at':time.time()+refreshed.get('expires_in',3600)};atomic_private(self.path(),self.record)
            return self.record['token']['access_token']
    async def read(self,path,params=None):
        if not (path in ('profile','messages') or re.fullmatch(r'messages/[0-9a-f]{1,64}',path)):raise Denied('Only qualified Gmail profile/message reads are available')
        account=self.record;binding=self.bound
        token=await self.access_token()
        response=await (await self.client()).get(API+'/'+path,params=params,headers={'Authorization':'Bearer '+token})
        if response.status_code!=200:raise Denied('Gmail HTTP '+str(response.status_code)+'; polling will back off')
        if len(response.content)>2*1024*1024:raise Denied('Mail response exceeds 2 MiB')
        if not self.valid() or self.bound!=binding or self.record is not account:raise Denied('Account changed during mail read')
        return response.json()
    async def poll(self):
        if self.bound!=self.partition():self.load()
        if not self.valid() or time.monotonic()<self.next_poll:return 0
        # Reserve the interval before awaiting; Check now cannot bypass backoff.
        self.next_poll=time.monotonic()+900+random.uniform(0,60)
        try:
            choice=self.record['selection'];key='mail-seen-'+hashlib.sha256(self.record['email'].encode()).hexdigest()
            seen=self.store.value(self.bound,key,[]);known=set(seen)
            params=[('maxResults','20'),('includeSpamTrash','false'),('labelIds','UNREAD')]+[('labelIds',v) for v in choice['labels']]
            listing=await self.read('messages',params);new=[]
            for item in listing.get('messages',[])[:20]:
                identity=item.get('id','')
                if not re.fullmatch(r'[0-9a-f]{1,64}',identity) or identity in known:continue
                values=[('format','full' if choice['summary']=='body' else 'metadata')]
                if choice['summary']=='metadata':values +=[('metadataHeaders',h) for h in ('From','Subject','Date')]
                message=await self.read('messages/'+identity,values);payload=message.get('payload',{})
                headers={str(h.get('name','')).lower():str(h.get('value',''))[:250] for h in payload.get('headers',[])[:100]}
                entry={'id':identity,'subject':headers.get('subject','(no subject)'),'from':headers.get('from','(unknown sender)')}
                if choice['summary']=='body':self.bodies[identity]=(time.monotonic()+900,plain_body(payload))
                new.append(entry);seen.append(identity);known.add(identity)
            self.store.set_value(self.bound,key,seen[-500:]);now=time.monotonic();self.bodies={k:v for k,v in self.bodies.items() if v[0]>now}
            if new:
                digest='Unread in your selected Gmail labels: '+'; '.join(v['subject'] for v in new[:3])
                self.offer('selected-mail','mail:'+self.record['email'],'mail',{'local_digest':digest[:1000],'messages':new[:3],'cloud':choice['cloud'],'account':self.record['email']},self.record['email']+':'+','.join(v['id'] for v in new))
            self.failures=0;self.status='Read-only Gmail checked; '+str(len(new))+' new message(s).';return len(new)
        except (Denied,OSError,ValueError):
            self.failures+=1;self.next_poll=time.monotonic()+min(21600,900*2**min(self.failures,5))+random.uniform(0,60)
            self.status='Gmail unavailable; bounded retry scheduled. Other features remain available.';raise
    def excerpts(self,ids):
        if not self.valid() or not self.record['selection']['cloud']:return []
        now=time.monotonic()
        return [{'id':i,'plain_excerpt':self.bodies[i][1][:1200]} for i in ids[:3] if i in self.bodies and self.bodies[i][0]>now]
    def disconnect(self):
        if self.pending and not self.pending.done():self.pending.cancel()
        self.path().unlink(missing_ok=True);self.record=None;self.bodies.clear();self.status='Gmail disconnected locally. You can revoke the app in your Google account permissions.'
    async def close(self):
        if self.http:await self.http.aclose()
