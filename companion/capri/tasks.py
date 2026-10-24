"""Owner-issued task leases and durable effects, independent of model prose."""
import asyncio
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import secrets
import time

from .broker import Denied, exact_keys
from .provider import atomic_private
from .engine import WorkEngine
from .task_sandbox import RootHandle, TaskSandbox, validate_roots

POLICY = 'capri-task-v2.1'
TOOLS = [
    {'type':'function','name':'exec','description':'Run exact argv under /usr/bin inside the selected read/write project roots. No network, home, credentials, desktop sockets or live Capri files. 30 seconds and 1 MiB output per command. Use Python or installed tools to inspect/edit/build/test and verify effects.',
     'inputSchema':{'type':'object','properties':{'argv':{'type':'array','items':{'type':'string'}},'cwd':{'type':'string'}},'required':['argv','cwd'],'additionalProperties':False}},
    {'type':'function','name':'desktop','description':'Typed installed desktop actions when enabled for this task. Kinds: desktop.list (args {}), desktop.open (app allowlist: calculator,code,firefox,thunar,audio-settings), desktop.focus (address), media.players ({}), media.select (player), media.status ({}), media.control (command: play,pause,play-pause,next,previous,stop), audio.adjust (percent 0..100). No general GUI input or administrator privilege.',
     'inputSchema':{'type':'object','properties':{'kind':{'type':'string'},'args':{'type':'object'}},'required':['kind','args'],'additionalProperties':False}},
    {'type':'function','name':'appearance','description':'Automatically adjust only bounded Capri size, reduced-motion and check-in cadence data when useful. Cannot change DND, mute, observation, authority, code, paths or hooks.',
     'inputSchema':{'type':'object','properties':{'changes':{'type':'object'}},'required':['changes'],'additionalProperties':False}},
    {'type':'function','name':'request_scope','description':'Pause for concrete native owner approval of extra exact project directories or typed desktop tools. Cannot request credentials, live Capri authority, root, arbitrary network or GUI input. Explain why the current task needs the expansion.',
     'inputSchema':{'type':'object','properties':{'roots':{'type':'array','items':{'type':'string'}},'desktop':{'type':'boolean'},'reason':{'type':'string'}},'required':['roots','desktop','reason'],'additionalProperties':False}},
]

@dataclass
class Lease:
    task: str
    partition: str
    model: str
    session: str
    epoch: str
    owner_event: str
    deadline: float
    roots: list
    desktop: bool
    handles: list = field(default_factory=list)
    actions: int = 0
    active: bool = True

    def public(self):
        return {'policy':POLICY,'owner_event':self.owner_event,'partition':self.partition,
                'model':self.model,'session':self.session,'roots':self.roots,'desktop':self.desktop,
                'seconds':1800,'action_budget':64,'network':'none',
                'root_identity':[(h.identity.st_dev,h.identity.st_ino) for h in self.handles]}

class TaskCoordinator:
    def __init__(self, store, provider, broker, adapters, directory, context, publish, engine_factory=WorkEngine,data_adjust=None):
        self.store=store; self.provider=provider; self.broker=broker; self.adapters=adapters
        self.directory=Path(directory); self.context=context; self.publish=publish; self.engine_factory=engine_factory;self.data_adjust=data_adjust
        self.runner=TaskSandbox(self.directory/'control'); self.lease=None; self.engine=None
        self.pending=None; self.expansion=None; self.phase=''; self.lock=asyncio.Lock()

    def scope(self):
        return self.store.value(self.provider.partition,'work_scope',{'roots':[],'desktop':False})

    def set_scope(self, roots, desktop):
        if type(desktop) is not bool or not isinstance(roots,list):raise Denied('Invalid project/desktop scope')
        roots=validate_roots(roots) if roots else []
        self.store.set_value(self.provider.partition,'work_scope',{'roots':roots,'desktop':desktop})

    def valid(self):
        lease=self.lease
        return bool(lease and lease.active and time.monotonic()<lease.deadline and
                    lease.partition==self.provider.partition and lease.model==self.provider.model and
                    lease.epoch==self.broker.epoch and self.broker.trusted_ui and not self.broker.locked and
                    self.context()==lease.session and lease.session)

    def issue(self, owner_event, *, origin):
        if origin!='owner-ui' or not self.broker.trusted_ui or self.broker.locked or not self.context():
            raise Denied('A current unlocked native owner task is required')
        if not self.provider.record or not self.provider.model:raise Denied('Connect your ChatGPT account and select an available model first')
        scope=self.scope()
        if not scope['roots'] and not scope['desktop']:raise Denied('Choose project folders or typed desktop tools in Settings before starting a Task')
        roots=validate_roots(scope['roots']) if scope['roots'] else []
        handles=[]
        try:
            for path in roots:handles.append(RootHandle(path))
            lease=Lease(secrets.token_hex(16),self.provider.partition,self.provider.model,self.context(),self.broker.epoch,str(owner_event),time.monotonic()+1800,roots,scope['desktop'],handles)
            self.lease=lease;return lease
        except BaseException:
            for h in handles:h.close()
            raise

    async def event(self,kind,detail):
        if not self.lease:return
        if kind=='thread':self.store.update_task(self.lease.task,thread=detail['id'])
        elif kind=='delta':
            await self.publish('delta',{'text':detail['text']});return
        elif kind=='usage':
            self.store.update_task(self.lease.task,checkpoint=json.dumps({'provider_usage':detail['usage'],'actions':self.lease.actions}))
        else:self.phase='Working · '+str(detail.get('type') or kind)
        self.store.task_event(self.lease.task,kind,json.dumps(detail))
        await self.publish(kind,detail)

    async def run(self, objective, owner_event, *, origin, resume=None):
        lease=self.issue(owner_event,origin=origin)
        thread=None;engine_directory=self.directory/'tasks'/lease.task
        if resume:
            row=self.store.db.execute('SELECT partition,status,lease,thread FROM tasks WHERE id=?',(resume,)).fetchone()
            if not row or row[0]!=lease.partition or row[1] not in ('interrupted','cancelled','failed','completed'):
                self.revoke()
                for h in lease.handles:h.close()
                self.lease=None;raise Denied('That task cannot be resumed in this account')
            prior=json.loads(row[2])
            if prior['roots']!=lease.roots or prior['desktop']!=lease.desktop:
                self.revoke()
                for h in lease.handles:h.close()
                self.lease=None;raise Denied('Select the original task scope before resuming it')
            thread=row[3];engine_directory=self.directory/'tasks'/resume
            objective='Continue this owner task after interruption. First inspect actual files and prior results; never replay an uncertain mutation blindly. '+objective
        self.store.create_task(lease.task,lease.partition,objective,lease.public())
        self.store.update_task(lease.task,status='running')
        self.phase='Starting qualified work engine'
        self.engine=self.engine_factory(self.provider,engine_directory,lease.model,lease.roots,self.valid,self.dispatch,self.event,TOOLS,held_handles=lease.handles)
        try:
            await self.engine.start(thread)
            result=await self.engine.run(objective)
            if not self.valid():raise Denied('Task authority changed before completion')
            self.store.update_task(lease.task,status='completed',checkpoint=json.dumps(result))
            self.store.task_event(lease.task,'verified-terminal','completed')
            return result['text']
        except asyncio.CancelledError:
            self.store.update_task(lease.task,status='cancelled');raise
        except Exception:
            self.store.update_task(lease.task,status='failed');raise
        finally:
            self.revoke()
            try:
                if self.engine:await self.engine.close()
                await self.runner.stop()
            finally:
                for handle in lease.handles:handle.close()
                self.engine=None;self.lease=None;self.phase=''

    def revoke(self):
        if self.lease:self.lease.active=False
        if self.expansion and not self.expansion.done():self.expansion.set_result(False)

    async def stop(self):
        self.revoke()
        await self.runner.stop()
        if self.engine:await self.engine.interrupt()

    async def dispatch(self, call_id, tool, args):
        async with self.lock:
            if not self.valid():raise Denied('Expired or revoked task')
            if not isinstance(call_id,str) or not 1<=len(call_id)<=256:raise Denied('Invalid action identity')
            lease=self.lease
            thread=getattr(self.engine,'thread_id',None) or lease.task
            action_id=hashlib.sha256(json.dumps([lease.partition,thread,call_id]).encode()).hexdigest()
            if self.store.action(action_id):raise Denied('Action already journaled; reconcile its actual effect')
            if lease.actions>=64:raise Denied('Task action budget exhausted; checkpoint and request a new task')
            lease.actions+=1
            self.store.journal(action_id,lease.epoch,tool,'RUNNING')
            self.store.task_event(lease.task,'action-start',json.dumps({'id':action_id,'tool':tool,'arguments':args}))
            try:
                if tool=='exec':
                    exact_keys(args,('argv','cwd'))
                    if not lease.roots:raise Denied('No project root in this task; request a concrete scope expansion')
                    result=await self.runner.run(args['argv'],lease.roots,args['cwd'],held_handles=lease.handles,timeout=min(30,lease.deadline-time.monotonic()))
                    argv=args['argv']
                    known_check=('-m' in argv and any(x in argv for x in ('unittest','pytest'))) or (Path(argv[0]).name in ('npm','pnpm','make','ctest','ninja') and any(x in argv for x in ('test','check','build')))
                    if known_check:
                        evidence=self.directory/'tasks'/lease.task/('check-'+action_id+'.json')
                        atomic_private(evidence,{'task':lease.task,'action':action_id,'argv':argv,'result':result})
                        await self.event('verification',{'exit_code':result['exit_code'],'project':args['cwd'],'evidence':str(evidence),'action':action_id})
                elif tool=='appearance':
                    exact_keys(args,('changes',));changes=args['changes']
                    if not isinstance(changes,dict) or not changes or not set(changes)<={'character_size','reduced_motion','min_gap_minutes','max_gap_minutes'} or self.data_adjust is None:raise Denied('Only supported appearance/cadence data can be adjusted automatically')
                    result=await self.data_adjust(changes)
                elif tool=='desktop':result=await self.desktop(args)
                elif tool=='request_scope':result=await self.request_scope(args)
                else:raise Denied('Unregistered native tool')
                if not self.valid():raise Denied('Authority revoked during operation; inspect its effect')
                self.store.journal(action_id,lease.epoch,tool,'SUCCEEDED',json.dumps(result))
                self.store.task_event(lease.task,'action-result',json.dumps({'id':action_id,'result':result}))
                return result
            except BaseException as error:
                self.store.journal(action_id,lease.epoch,tool,'EFFECT_UNKNOWN',type(error).__name__)
                raise

    async def desktop(self,args):
        exact_keys(args,('kind','args'));kind=args['kind'];values=args['args']
        if not self.lease.desktop:raise Denied('Typed desktop tools are outside this task; request native expansion')
        if kind=='desktop.list':exact_keys(values,());return {'windows':await self.adapters.clients()}
        if kind=='media.players':exact_keys(values,());return {'players':await self.adapters.players()}
        if kind=='media.select':
            exact_keys(values,('player',))
            if values['player'] not in await self.adapters.players():raise Denied('Player is unavailable')
            self.adapters.player=values['player'];return {'selected':values['player']}
        if kind not in ('desktop.open','desktop.focus','media.status','media.control','audio.adjust'):raise Denied('That desktop capability has not been qualified')
        return await self.adapters.run(kind,values)

    async def request_scope(self,args):
        exact_keys(args,('roots','desktop','reason'))
        if type(args['desktop']) is not bool or not isinstance(args['reason'],str) or not 1<=len(args['reason'])<=1000:raise Denied('Invalid scope request')
        roots=validate_roots(args['roots']) if args['roots'] else []
        if len(set(self.lease.roots+roots))>8:raise Denied('At most eight roots per task')
        self.pending={'id':secrets.token_hex(16),'roots':roots,'desktop':args['desktop'],'reason':args['reason'],'task':self.lease.task}
        self.expansion=asyncio.get_running_loop().create_future()
        self.phase='Waiting for your scope decision';await self.publish('task',{})
        try:
            approved=await asyncio.wait_for(self.expansion,min(300,max(.1,self.lease.deadline-time.monotonic())))
            if not approved or not self.valid():raise Denied('Scope expansion declined or expired')
            added=[]
            try:
                for path in roots:
                    if path not in self.lease.roots:added.append(RootHandle(path))
            except BaseException:
                for h in added:h.close()
                raise
            self.lease.handles.extend(added);self.lease.roots.extend(h.path for h in added)
            self.lease.desktop=self.lease.desktop or args['desktop']
            self.store.task_event(self.lease.task,'native-scope-approved',json.dumps(self.pending))
            return {'roots':self.lease.roots,'desktop':self.lease.desktop,'network':'none'}
        finally:self.pending=None;self.expansion=None;await self.publish('task',{})

    def resolve_scope(self,request_id,approved, *, origin):
        if origin!='owner-ui' or type(approved) is not bool or not self.valid() or not self.pending or self.pending['id']!=request_id or not self.expansion or self.expansion.done():raise Denied('No current native scope request')
        self.expansion.set_result(approved)
