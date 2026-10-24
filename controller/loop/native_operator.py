"""Parent-only operation on the existing supervisor; model interfaces cannot call it."""
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import struct
import threading

from .adapter import process_identity
from .native_startup import checked_file
from .util import Rejected,atomic,digest,identity,safe_path,tree


class NativeOperator:
    def __init__(self,engine,adapter,binding,controller,journal):
        self.engine,self.adapter,self.binding,self.controller,self.journal=engine,adapter,binding,Path(controller),journal
        self.root=adapter.slots.root;self.path=self.root/'operator.sock';self.key_path=self.root/'operator.key'
        self.stop_requested=False;self.uncertain_roles=set();self.requests=queue.Queue(maxsize=1);self.stopped=threading.Event();self.listener=None

    def start(self):
        if os.path.lexists(self.path) or self.key_path.exists():raise Rejected('Existing operator identity requires checked recovery')
        self.key=secrets.token_hex(32);atomic(self.key_path,self.key,exclusive=True)
        self.listener=socket.socket(socket.AF_UNIX);self.listener.bind(str(self.path));os.chmod(self.path,0o600);self.listener.listen(1);self.listener.settimeout(.2);self.socket_identity=(self.path.stat().st_dev,self.path.stat().st_ino)
        self.thread=threading.Thread(target=self.serve,daemon=True);self.thread.start()

    def serve(self):
        while not self.stopped.is_set():
            try:connection,_=self.listener.accept()
            except socket.timeout:continue
            except OSError:return
            with connection:
                connection.settimeout(5)
                try:
                    _,uid,_=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if uid!=os.getuid():raise Rejected('Operator UID mismatch')
                    reader=connection.makefile('rb');raw=reader.readline(60001)
                    if len(raw)>60000 or not raw.endswith(b'\n'):raise Rejected('Oversized/incomplete operator request')
                    value=json.loads(raw)
                    if not secrets.compare_digest(value.pop('key',''),self.key):raise Rejected('Parent-only operator capability required')
                    item=dict(request=value,done=threading.Event());self.requests.put_nowait(item)
                    while not self.stopped.is_set() and not item['done'].wait(.2):pass
                    reply=item.get('reply',dict(status='HELD',error='Supervisor stopped before result'))
                except (Rejected,ValueError,OSError,queue.Full) as ex:reply=dict(status='REJECTED',error=str(ex))
                try:connection.sendall((json.dumps(reply)+'\n').encode())
                except OSError:pass # Result stays journaled; never repeat a lost response.

    def poll(self,timeout=.2):
        try:item=self.requests.get(timeout=timeout)
        except queue.Empty:return
        try:item['reply']=self.finish(item['request'])
        except Exception as ex:item['reply']=dict(status='BLOCKED',error=str(ex))
        finally:item['done'].set()

    def checked_task(self,b):
        task=self.engine.store.task(b['task']);self.engine.require_current(task);self.engine.verify_inputs(task)
        if task['state']!='CANDIDATE_SEALED' or task['version']!=b['version'] or task['owner']!=b['owner'] or task['owner']!=self.binding['owner']:
            raise Rejected('Exact current qualification hold required')
        if b['packet_hash']!=task['content_hash'] or b['source_hash']!=identity(tree(task['candidate'])) or json.loads(task['seal'])['source_hash']!=b['source_hash']:
            raise Rejected('Sealed task/source binding changed')
        if b['controller_hash']!=self.binding['controller_hash'] or identity(tree(self.controller))!=self.binding['controller_hash'] or identity(tree(self.controller.parent))!=self.binding['source_hash'] or b['supervisor_pid']!=os.getpid() or b['supervisor_identity']!=process_identity(os.getpid()):
            raise Rejected('Current controller/supervisor binding changed')
        return task

    def finish(self,request):
        if set(request)!= {'action','binding'}:raise Rejected('Exact parent operation required')
        if request['action'] in ('compact-role','replace-role','checkpoint-runtime','reconcile-maintenance'):return self.maintenance(request['action'],request['binding'])
        if request['action']!='finish-review':raise Rejected('Unsupported parent operation')
        b=request['binding'];task=self.checked_task(b)
        if self.unresolved():raise Rejected('Unreconciled maintenance prevents formal review')
        ids={row['id'] for row in task['packet']['requirements']}
        required={'N01','N02','N03','N04','N05','N06','N07','N08'}
        if not required<=ids or ids-required-{'SCOPE'}:raise Rejected('Final review must target all eight workflow requirements, with only optional SCOPE')
        material={}
        for item in b['evidence']:
            name=item['name'];safe_path('/review-material',name)
            if name in material:raise Rejected('Duplicate evidence name')
            data=checked_file(item).read_bytes()
            if len(data)>24000:raise Rejected('Index bundle too large; retain bounded excerpts with hashed originals')
            material[name]=data
        if 'INDEX.json' not in material or len(material)>10 or sum(map(len,material.values()))>120000:raise Rejected('Bounded indexed evidence required')
        key=identity(b);history=self.journal.records()
        if any(r['milestone']=='FINAL_REVIEW_INTENT' for r in history):raise Rejected('Final review intent consumed; no automatic retry')
        for name,data in material.items():self.engine.native_materials['review/'+name]=data
        self.adapter.review_guide='Read /inputs/review/INDEX.json first, then the bounded source/evidence bundles it names. Budget at most8 grouped read commands and preserve room for the schema final output within12 exposed tools/240seconds. Inspect relevant source and original collector receipts; do not dump the entire archive. Missing evidence stays UNVERIFIED. No fixes.'
        self.journal.append('FINAL_REVIEW_INTENT',dict(key=key,binding=b))
        try:
            self.engine.review(task['id'])
            result=self.engine.result(task['id'],task['owner'])
            if result['state']!='REPORTING':raise Rejected('Completed review did not reach exact report gate')
            self.journal.append('FINAL_REVIEW_COMPLETED',dict(result=result))
            self.adapter.thinker_turn('Report this exact controller-bound final review result, limitations and human stop: '+json.dumps(result),report_task=task['id'])
            result=self.engine.result(task['id'],task['owner']);self.journal.append('FINAL_REPORT_COMPLETED',dict(result=result))
            return dict(status='AWAITING_HUMAN',result=result,operation=key)
        except Exception:
            current=self.engine.store.task(task['id'])
            if current['state']=='REVIEWER_RUNNING':self.engine.store.transition(task['id'],'REVIEWER_RUNNING','BLOCKED',outcome='UNVERIFIED')
            self.journal.append('FINAL_REVIEW_OR_REPORT_INCOMPLETE',dict(task=task['id'],current_state=self.engine.store.task(task['id'])['state']))
            raise

    def unresolved(self):
        rows=self.journal.records();done={r['details']['prior_key'] for r in rows if r['milestone']=='MAINTENANCE_RECOVERED'}
        return [r for r in rows if r['milestone']=='MAINTENANCE_UNCERTAIN' and r['details']['key'] not in done]

    def reconcile(self,b,task,backend):
        rows=self.journal.records();key=b['uncertain_key']
        unknown=[r for r in self.unresolved() if r['details']['key']==key]
        bound=next((r['details'] for r in rows if r['milestone']=='MAINTENANCE_READ_ONLY_BOUND' and r['details']['key']==key),None)
        if len(unknown)!=1 or not bound or bound['action']!='compact-role':raise Rejected('Only an accounted read-only compaction can be fenced here')
        if backend.active or backend.phase!='read' or backend.thread!=bound['old_thread'] or backend.generation!=bound['generation'] or backend.proc.pid!=bound['pid'] or backend.start_identity!=bound['process'] or process_identity(bound['pid']) is not None or backend.proc.poll() is None:
            raise Rejected('Exact prior read-only process must have exited; PID reuse remains held')
        if tree(backend.workspace)!=bound['source'] or tree(backend.inputs)!=bound['inputs']:raise Rejected('Read-only source/input effects are unresolved')
        from .context import Checkpoint
        cp=Checkpoint(Path(bound['checkpoint']),self.engine.store.home);cp.validate(self.adapter.checkpoint_authority(task['id'],'doer'))
        if digest(cp.path.read_bytes())!=bound['checkpoint_sha256']:raise Rejected('Pre-operation checkpoint changed')
        if any(r['milestone']=='MAINTENANCE_FENCED' and r['details']['key']==key for r in rows):raise Rejected('Fence already recorded; inspect it without repeating')
        self.journal.append('MAINTENANCE_FENCED',dict(**bound,classification='DEAD_READ_ONLY_COMPACTION_FENCE',old_thread_reused=False))
        return dict(status='FENCED_READ_ONLY',key=key,next='Explicit checked fresh Doer replacement only; ordinary work remains held')

    def maintenance(self,action,b):
        import time
        from .context import Checkpoint
        task=self.checked_task(b);role=b.get('role','doer')
        if role!='doer':raise Rejected('Task maintenance operates on the visible Doer only')
        backend=self.adapter.slots.backends[role]
        if action=='reconcile-maintenance':return self.reconcile(b,task,backend)
        reconciled=None
        if action=='replace-role' and b.get('reconciled_key'):
            reconciled=next((r['details'] for r in self.journal.records() if r['milestone']=='MAINTENANCE_FENCED' and r['details']['key']==b['reconciled_key']),None)
            if not reconciled:raise Rejected('Committed read-only fence required')
        if backend.active or (backend.error and not reconciled) or backend.thread!=b['thread'] or backend.generation!=b['role_generation']:raise Rejected('Exact idle role identity required')
        key=identity(dict(action=action,binding=b))
        history=self.journal.records()
        if any(r['milestone']=='MAINTENANCE_INTENT' and r['details']['key']==key for r in history):raise Rejected('Maintenance intent consumed; no automatic retry')
        unknown=self.unresolved()
        if unknown and (not reconciled or len(unknown)!=1 or unknown[0]['details']['key']!=reconciled['key']):raise Rejected('Uncertain maintenance requires explicit effect reconciliation')
        self.journal.append('MAINTENANCE_INTENT',dict(key=key,action=action,role=role,thread=backend.thread,generation=backend.generation))
        self.adapter.operation_deadline=time.monotonic()+240;self.adapter.operation_tools=0
        try:
            if backend.phase!='read':
                backend.write_ready=False;backend=self.adapter.slots.remount(role,backend.inputs,phase='read',fresh=False)
            checkpoint=Checkpoint(Path(reconciled['checkpoint']),self.engine.store.home) if reconciled else self.adapter.checkpoint(task['id'],role)
            state=self.adapter.prepare_context(task['id'],role)
            if action=='checkpoint-runtime':
                owner_checkpoint=self.adapter.owner_checkpoint()
                rows=self.adapter.slots.save()
                scope=json.loads(self.engine.store.db.execute('SELECT scope FROM capabilities WHERE token_hash=?',(self.adapter.thinker_capability_hash,)).fetchone()['scope'])
                roles={name:dict(workspace=str(value.workspace),inputs=str(value.inputs),source=tree(value.workspace),input_files=tree(value.inputs)) for name,value in self.adapter.slots.backends.items()}
                receipt=dict(schema_version=1,route='CHECKED_NATIVE_RUNTIME_RESUME',operation=key,maintenance_binding=self.binding,task=task['id'],task_version=task['version'],packet_hash=task['content_hash'],candidate_source=b['source_hash'],controller_hash=b['controller_hash'],roles=roles,registry=rows,registry_hash=identity(rows),registry_sha256=digest((self.root/'registry.json').read_bytes()),operator_key_sha256=digest(self.key_path.read_bytes()),scope=scope,owner=self.binding['owner'],owner_checkpoint=str(owner_checkpoint.path),doer_checkpoint=str(checkpoint.path),source_before_stop=tree(task['candidate']))
                path=self.engine.store.home/'inputs/native-runtime-resume'/key/'prepared.json'
                atomic(path,json.dumps(receipt,sort_keys=True)+'\n',exclusive=True)
                result=dict(status='RUNTIME_CHECKPOINTED',receipt=str(path),receipt_sha256=digest(path.read_bytes()),model_dispatch='NOT_STARTED',next='Wait for exact owned processes to exit, then checked resume-runtime')
                self.journal.append('RUNTIME_CHECKPOINTED',result);self.stop_requested=True
            else:
                if not reconciled and (state.restart or state.rehydrating or state.decision()['reason'] in ('UNKNOWN','STALE_OR_WRONG_IDENTITY')):
                    self.adapter.probe(task['id'],role,checkpoint);self.adapter.rehydrate(task['id'],role,checkpoint)
                if action=='replace-role':
                    replaced=self.adapter.replace_fenced_readonly(task['id'],role,checkpoint,reconciled) if reconciled else self.adapter.replace_role(task['id'],role,checkpoint)
                    checkpoint=Checkpoint(Path(replaced['checkpoint']),self.engine.store.home)
                elif action=='compact-role':
                    self.journal.append('MAINTENANCE_READ_ONLY_BOUND',dict(key=key,action=action,role=role,old_thread=backend.thread,generation=backend.generation,pid=backend.proc.pid,process=backend.start_identity,source=tree(backend.workspace),inputs=tree(backend.inputs),checkpoint=str(checkpoint.path),checkpoint_sha256=digest(checkpoint.path.read_bytes())))
                    self.adapter.compact(task['id'],role,checkpoint)
                self.adapter.probe(task['id'],role,checkpoint);result=self.adapter.rehydrate(task['id'],role,checkpoint)
                result=dict(status='READ_ONLY_MAINTENANCE_COMPLETED',role=role,result=result,source_unchanged=tree(task['candidate'])==json.loads(task['seal'])['files'])
            if reconciled:
                self.journal.append('MAINTENANCE_RECOVERED',dict(prior_key=reconciled['key'],replacement=result));self.uncertain_roles.discard(role)
            self.journal.append('MAINTENANCE_COMPLETED',dict(key=key,result=result));return result
        except Exception as ex:
            self.uncertain_roles.add(role)
            self.journal.append('MAINTENANCE_UNCERTAIN',dict(key=key,role=role,error=str(ex)));raise

    def close(self):
        self.stopped.set()
        if self.listener:self.listener.close()
        if self.path.exists() and (self.path.stat().st_dev,self.path.stat().st_ino)==getattr(self,'socket_identity',None):self.path.unlink()
        if hasattr(self,'thread'):self.thread.join(timeout=1)
        # Preserve the old capability file and journal for stopped-operation audit.


def request_review(root,binding,action="finish-review"):
    root=Path(root);key=(root/'operator.key').read_text()
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(900);connection.connect(str(root/'operator.sock'))
        connection.sendall((json.dumps(dict(key=key,action=action,binding=binding))+'\n').encode())
        response=connection.makefile('rb').readline(200001)
        if len(response)>200000 or not response.endswith(b'\n'):raise Rejected('Incomplete operator result; reconcile journal, never auto-repeat')
        return json.loads(response)
