"""Checked controller restart from a completed sealed qualification boundary."""
import json
import os
from pathlib import Path
import signal
import threading
import time

from .adapter import process_identity
from .context import Checkpoint,derive_checkpoint
from .native_startup import ReadOnlyState,StartupJournal
from .util import Rejected,atomic,digest,identity,tree


def inspect_resume(config,path,expected_hash,controller):
    path=Path(path)
    if path.is_symlink() or digest(path.read_bytes())!=expected_hash:raise Rejected('Runtime resume receipt changed')
    saved=json.loads(path.read_text());binding=saved['maintenance_binding']
    if saved.get('route')!='CHECKED_NATIVE_RUNTIME_RESUME' or identity(config)!=binding['config_hash'] or identity(tree(controller))!=binding['controller_hash'] or identity(tree(Path(controller).parent))!=binding['source_hash']:
        raise Rejected('Runtime resume source/configuration binding changed')
    root=Path(config['settings']['state_dir']);raw=(root/'registry.json').read_bytes()
    if digest(raw)!=saved['registry_sha256'] or identity(json.loads(raw))!=saved['registry_hash']:raise Rejected('Stopped runtime registry changed')
    if (root/'operator.sock').exists() or digest((root/'operator.key').read_bytes())!=saved['operator_key_sha256']:
        raise Rejected('Prior operator endpoint/key ownership unresolved')
    supervisor=json.loads((root/'supervisor.json').read_text())
    if process_identity(supervisor['pid']) is not None:raise Rejected('Prior supervisor remains; no duplicate startup')
    for role,row in saved['registry'].items():
        if process_identity(row['pid']) is not None or (root/(role+'.sock')).exists():raise Rejected('Prior backend/endpoint remains unresolved')
        spec=saved['roles'][role]
        if tree(spec['workspace'])!=spec['source'] or tree(spec['inputs'])!=spec['input_files']:raise Rejected('Role source/inputs changed')
    with ReadOnlyState(config['home']) as view:
        view.require_current(saved['owner']);task=view.task(saved['task'])
        if task['state']!='CANDIDATE_SEALED' or task['version']!=saved['task_version'] or task['content_hash']!=saved['packet_hash'] or tree(task['candidate'])!=saved['source_before_stop']:
            raise Rejected('Exact unchanged qualification hold required for restart')
        journal=StartupJournal(view,binding['operation'],binding);history=journal.records()
        if not any(r['milestone']=='RUNTIME_CHECKPOINTED' and r['details']['receipt_sha256']==expected_hash for r in history):raise Rejected('Runtime projection has no committed checkpoint authority')
        if any(r['milestone']=='MAINTENANCE_UNCERTAIN' for r in history):raise Rejected('Uncertain maintenance prevents restart')
        if any(r['milestone']=='RUNTIME_RESUME_INTENT' and r['details']['receipt_sha256']==expected_hash for r in history):raise Rejected('Runtime restart intent consumed; reconcile, never retry')
        if view.db.execute('SELECT token_hash FROM capabilities WHERE owner=? AND enabled=1',(saved['owner'],)).fetchone():raise Rejected('Owner capability was not held before controller stop')
    for name in ('owner_checkpoint','doer_checkpoint'):
        cp=Checkpoint(Path(saved[name]),Path(config['home']));authority=json.loads(cp.path.read_text())['state']['authority'];cp.validate(authority)
    return saved,raw


def run_resume(config,args,controller):
    saved,raw=inspect_resume(config,args.prepared,args.prepared_sha256,controller)
    if args.check:
        print(json.dumps(dict(status='NATIVE_RUNTIME_RESUME_CHECKED',model_dispatch='NOT_STARTED',state_initialized=False)),flush=True);return
    from .engine import Engine
    from .native import NativeAdapter,NativeIntake,NativeTerminals,capture_complete,original_read_command,grade_original_reads
    from .settings import Settings
    from .store import Store
    from .service import capability
    from .native_operator import NativeOperator
    store=Store(Path(config['home']));adapter=intake=terminals=operator=None;stopped=threading.Event();binding=saved['maintenance_binding'];journal=StartupJournal(store,binding['operation'],binding)
    try:
        with store.lock('native-startup'):
            saved,raw=inspect_resume(config,args.prepared,args.prepared_sha256,controller)
            journal.append('RUNTIME_RESUME_INTENT',dict(receipt_sha256=args.prepared_sha256))
            engine=Engine(store,config['workflow'],defer_review=True);adapter=NativeAdapter(engine,Settings(**config['settings']),evidence_check=capture_complete);engine.adapter=adapter
            intake=NativeIntake(store.home,config['workflow']);intake.start();token=adapter.create_held_capability(saved['owner'],saved['scope'])
            atomic(adapter.slots.root/('registry-before-runtime-resume-'+saved['operation']+'.json'),raw,exclusive=True)
            for role in ('thinker','doer','reviewer'):
                spec=saved['roles'][role];old=saved['registry'][role]
                if old['empty']:
                    adapter.slots.start_role(role,spec['workspace'],spec['inputs'],controller,generation=old['generation']+1,phase='read')
                else:
                    adapter.slots.restore_saved_role(role,spec['workspace'],spec['inputs'],controller,registry_hash=digest(raw),frozen_registry=raw,
                        **(dict(mcp=token,intake_socket=intake.path) if role=='thinker' else {}))
            adapter.register_thinker(saved['owner'],token,held=True);adapter.hold_thinker_tools();adapter.prepared_owner=saved['owner'];adapter.prepared_hash=binding['predecessor_receipt']['sha256'];adapter.owner_recovery_names=binding.get('owner_recovery_names',[])
            atomic(adapter.slots.root/'supervisor.json',json.dumps(dict(pid=os.getpid(),process_identity=process_identity(os.getpid()),cmdline_hex=Path('/proc/self/cmdline').read_bytes().hex(),source=binding['source_hash'],maintenance_operation=binding['operation'])))
            terminals=NativeTerminals(adapter.slots,headless=args.headless);terminals.sync(adapter.slots.save());adapter.slots.mapping_changed=terminals.sync
            for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopped.set())
            deadline=time.monotonic()+15
            while time.monotonic()<deadline and any(not b.clients for b in adapter.slots.backends.values()):stopped.wait(.05)
            if any(not b.clients for b in adapter.slots.backends.values()):raise Rejected('Restored clients did not attach')
            # Each recovered role has one combined, unchanged 240s/12-tool stage.
            adapter.operation_deadline=time.monotonic()+240;adapter.operation_tools=0;adapter.owner_stage_active=True
            state,_=adapter.prepare_owner_context();state.rehydrating=state.restart=True;state.persist()
            parent=Checkpoint(Path(saved['owner_checkpoint']),store.home);prior=json.loads(parent.path.read_text())['state']['authority'];authority=adapter.owner_authority();target=Checkpoint(parent.path.parent/'controller-restart-owner.json',store.home)
            fields={'role_generation','thread','server','process','phase'};transition=dict(kind='restart',old={k:prior['lease_generations'].get(k) for k in fields},new={k:authority['lease_generations'].get(k) for k in fields});derive_checkpoint(parent,target,authority,transition)
            payload=[dict(type='text',text='No tools. Final exactly READY.',text_elements=[])]
            state.recovery_probe(target,authority,phase='read',payload_bytes=len(json.dumps(payload).encode()),max_tools=0,max_seconds=30)
            adapter.owner_dispatch(payload,probe=True,recovery=target,validate=lambda value:value=='READY')
            originals=adapter.owner_originals();expected=dict(owner=saved['owner'],checkpoint=target.validate(adapter.owner_authority()),originals=originals)
            payload=[dict(type='text',text='Read originals using '+original_read_command(originals)+'\nReturn exactly '+json.dumps(expected),text_elements=[])]
            adapter.owner_dispatch(payload,recovery=target,recovery_originals=originals,validate=lambda value:json.loads(value)==expected);state.rehydrate(target,adapter.owner_authority())
            adapter.operation_deadline=time.monotonic()+240;adapter.operation_tools=0
            parent=Checkpoint(Path(saved['doer_checkpoint']),store.home);prior=json.loads(parent.path.read_text())['state']['authority'];state=adapter.prepare_context(saved['task'],'doer');state.rehydrating=state.restart=True;state.persist();derived=adapter.derive_recovery_checkpoint(saved['task'],'doer',parent,prior,'restart')
            adapter.probe(saved['task'],'doer',derived);adapter.rehydrate(saved['task'],'doer',derived)
            journal.append('RUNTIME_RESUMED',dict(task=saved['task'],roles=adapter.slots.save(),old_new_lineage='Checked same Thinker/Doer threads, fresh empty Reviewer, generation+1'))
            prior_key=adapter.slots.root/'operator.key'
            if digest(prior_key.read_bytes())!=saved['operator_key_sha256']:raise Rejected('Operator key identity changed during restart')
            prior_key.rename(prior_key.with_name('operator.key.retired-'+saved['operation']))
            operator=NativeOperator(engine,adapter,binding,controller,journal);operator.start()
            print(json.dumps(dict(status='QUALIFICATION_HOLD_RESTORED',task=saved['task'],operator=str(operator.path),attach=terminals.attach_command())),flush=True)
            while not stopped.is_set():
                operator.poll(.2)
                if operator.stop_requested:break
                if any((b.error or b.proc.poll() is not None) and role not in operator.uncertain_roles for role,b in adapter.slots.backends.items()):raise Rejected('Restored backend failed; explicit recovery required')
    except BaseException as ex:
        journal.append('RUNTIME_RESUME_FAILED',dict(error=str(ex),receipt_sha256=args.prepared_sha256,classification='RECONCILIATION_REQUIRED'));raise
    finally:
        if operator:operator.close()
        if adapter:adapter.slots.mapping_changed=None;adapter.close()
        if terminals:terminals.close()
        if intake:intake.close()
        store.close()
