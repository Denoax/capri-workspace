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
from .native_operator import unresolved_maintenance
from .util import Rejected,atomic,digest,identity,tree


def source_revision_line(binding, parent):
    purpose='recovery and approved source/state security fixes' if binding.get('schema')==2 else 'recovery'
    return ('Authorize legacy alpha '+purpose+' for task '+parent['task']+' using source '+binding['source_hash']+
            ' and prior checkpoint '+binding['previous_receipt']['sha256']+
            '; preserve source, answers, failures and limits; stop at AWAITING_HUMAN without acceptance or integration.')


def source_revision_binding(config, binding, controller):
    """Validate immutable source bindings and approved diff, not stop eligibility.

    Source authority is captured separately below. The original checkpoint,
    task, inputs, role registry and completed recovery history stay immutable.
    """
    import re
    from .native_startup import checked_file
    keys={'schema','operation','previous_config','previous_receipt','source_hash','controller_hash',
          'config_hash','approval'}
    expanded=isinstance(binding,dict) and binding.get('schema')==2
    if expanded:
        keys=keys|{'additional_modules'}
    if (not isinstance(binding,dict) or set(binding)!=keys or type(binding['schema']) is not int or binding['schema'] not in (1,2) or
            not isinstance(binding['operation'],str) or
            not re.fullmatch('[a-z0-9-]{1,64}',binding['operation'])):
        raise Rejected('Exact bounded runtime source-revision binding required')
    controller=Path(controller).resolve()
    if (config.get('controller')!=str(controller) or identity(config)!=binding['config_hash'] or
            identity(tree(controller))!=binding['controller_hash'] or
            identity(tree(controller.parent))!=binding['source_hash']):
        raise Rejected('New source-revision controller/configuration changed')
    checked_file(binding['approval'])
    previous_config=json.loads(checked_file(binding['previous_config']).read_text())
    previous_controller=Path(previous_config['controller']).resolve()
    expected_config=dict(previous_config,controller=str(controller))
    if config!=expected_config:
        raise Rejected('Source revision cannot change home, model, settings, workflow or roles')
    previous_path=checked_file(binding['previous_receipt'])
    parent=json.loads(previous_path.read_text())
    if parent.get('route')!='CHECKED_NATIVE_RUNTIME_RESUME':
        raise Rejected('Only an original sealed runtime checkpoint can parent this revision')
    if binding['source_hash']==parent['maintenance_binding']['source_hash']:
        raise Rejected('A source revision requires distinct source bytes')
    # The approved maintenance seam excludes adapter, Store, Engine and gates.
    before=tree(previous_controller.parent);after=tree(controller.parent)
    changed={name for name in before.keys()|after.keys() if before.get(name)!=after.get(name)}
    allowed={'controller/loop/native.py','controller/loop/native_operator.py','controller/loop/native_resume.py'}
    if expanded:
        security_modules=['controller/loop/cli.py','controller/loop/contract.py','controller/loop/store.py','tools/ci_bwrap_profile.py']
        if binding['additional_modules']!=security_modules:
            raise Rejected('Only the separately approved source/state security modules can extend admission')
        allowed.update(security_modules)
    if not changed or any(name not in allowed and not
            (name.startswith('controller/tests/test_') and name.endswith('.py') and name in after)
            for name in changed):
        raise Rejected('Source revision exceeds the approved recovery modules and regression tests')
    if any(name in allowed and name not in after for name in changed):
        raise Rejected('Recovery implementation modules cannot be removed')
    # This is a pure precondition check using the OLD controller/configuration
    # identities. The parent receipt is never supplied to run_resume on new code.
    return previous_config, previous_path, parent


def inspect_source_revision(config, binding, controller):
    """Retain the original checkpoint's complete stopped-state/one-use guard."""
    previous_config, previous_path, parent = source_revision_binding(config, binding, controller)
    previous_controller = Path(previous_config['controller']).resolve()
    parent,raw=inspect_resume(previous_config,previous_path,binding['previous_receipt']['sha256'],previous_controller)
    if parent['maintenance_binding']['operation']==binding['operation']:
        raise Rejected('Source revision needs a new operation identity')
    with ReadOnlyState(config['home']) as view:
        records=[]
        for row in view.db.execute("SELECT seq,data FROM events WHERE kind='NATIVE_RUNTIME_SOURCE_REVISION' ORDER BY seq"):
            record=json.loads(row['data'])
            if record.get('operation')==binding['operation']:
                if record.get('binding_hash')!=identity(binding):
                    raise Rejected('Source revision operation reused with a different binding')
                records.append((row['seq'],record))
        if len(records)>1:
            raise Rejected('Duplicate source-revision authority')
    return parent,raw,records


def projected_source_revision(parent,binding,event):
    """Project distinct committed source authority, retaining the whole parent."""
    saved=json.loads(json.dumps(parent))
    saved['route']='CHECKED_NATIVE_SOURCE_REVISION'
    saved['operation']=binding['operation']
    saved['controller_hash']=binding['controller_hash']
    saved['maintenance_binding'].update(operation=binding['operation'],source_hash=binding['source_hash'],
        controller_hash=binding['controller_hash'],config_hash=binding['config_hash'])
    saved['source_revision']=dict(binding=binding,admission_event=event)
    return saved


def prepare_source_revision(store,config,binding,controller,text):
    with store.lock('native-startup'),store.lock('native-writer'),store.transaction():
        parent,_,records=inspect_source_revision(config,binding,controller)
        if records:
            raise Rejected('Source authority already recorded; inspect its receipt without replaying input')
        if text!=source_revision_line(binding,parent):
            raise Rejected('Exact source-bound foreground instruction required')
        event=store.event(parent['task'],'NATIVE_RUNTIME_SOURCE_REVISION',dict(operation=binding['operation'],
            binding_hash=identity(binding),source=binding['source_hash'],controller=binding['controller_hash'],
            parent_receipt=binding['previous_receipt'],origin='FOREGROUND_CONTROLLING_TTY',text=text))
        saved=projected_source_revision(parent,binding,event)
        path=Path(config['home'])/'inputs/native-runtime-source-revision'/identity(binding)/'prepared.json'
        raw=(json.dumps(saved,sort_keys=True,indent=2)+'\n').encode()
        atomic(path,raw,exclusive=True)
    return dict(status='RUNTIME_SOURCE_REVISION_PREPARED',receipt=str(path),receipt_sha256=digest(raw),
                event=event,source=binding['source_hash'],model_dispatch='NOT_STARTED',acceptance='NOT_PERFORMED')


def inspect_resume(config,path,expected_hash,controller):
    path=Path(path)
    if path.is_symlink() or digest(path.read_bytes())!=expected_hash:raise Rejected('Runtime resume receipt changed')
    saved=json.loads(path.read_text())
    if saved.get('route') == 'CHECKED_COMPLETED_READ_RECOVERY':
        from .native_read_recovery import inspect_launch
        return inspect_launch(config, path, expected_hash, controller)
    binding=saved['maintenance_binding']
    revised=saved.get('route')=='CHECKED_NATIVE_SOURCE_REVISION'
    if saved.get('route') not in ('CHECKED_NATIVE_RUNTIME_RESUME','CHECKED_NATIVE_SOURCE_REVISION') or identity(config)!=binding['config_hash'] or identity(tree(controller))!=binding['controller_hash'] or identity(tree(Path(controller).parent))!=binding['source_hash']:
        raise Rejected('Runtime resume source/configuration binding changed')
    if revised:
        revision=saved.get('source_revision',{})
        if (not isinstance(revision,dict) or set(revision)!={'binding','admission_event'} or
                type(revision['admission_event']) is not int):
            raise Rejected('Exact committed source-revision reference required')
        parent,_,records=inspect_source_revision(config,revision['binding'],controller)
        if (len(records)!=1 or records[0][0]!=revision['admission_event'] or
                records[0][1].get('origin')!='FOREGROUND_CONTROLLING_TTY' or
                records[0][1].get('text')!=source_revision_line(revision['binding'],parent) or
                saved!=projected_source_revision(parent,revision['binding'],records[0][0])):
            raise Rejected('Source revision lacks exact committed foreground authority')
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
        if not revised and not any(r['milestone']=='RUNTIME_CHECKPOINTED' and r['details']['receipt_sha256']==expected_hash for r in history):raise Rejected('Runtime projection has no committed checkpoint authority')
        if unresolved_maintenance(history):raise Rejected('Uncertain maintenance prevents restart')
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
    from .native import NativeAdapter,NativeIntake,NativeTerminals,capture_complete
    from .settings import Settings
    from .store import Store
    from .service import capability
    from .native_operator import NativeOperator
    store=Store(Path(config['home']));adapter=intake=terminals=operator=None;stopped=threading.Event();binding=saved['maintenance_binding'];journal=StartupJournal(store,binding['operation'],binding)
    try:
        with store.lock('native-startup'):
            with store.lock('native-writer'):
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
            parent=Checkpoint(Path(saved['owner_checkpoint']),store.home);prior=json.loads(parent.path.read_text())['state']['authority'];authority=adapter.owner_authority();target=Checkpoint(parent.path.parent/('controller-restart-owner-'+identity(authority)+'.json'),store.home)
            fields={'role_generation','thread','server','process','phase'};transition=dict(kind='restart',old={k:prior['lease_generations'].get(k) for k in fields},new={k:authority['lease_generations'].get(k) for k in fields});derive_checkpoint(parent,target,authority,transition)
            payload=[dict(type='text',text='No tools. Final exactly READY.',text_elements=[])]
            state.recovery_probe(target,authority,phase='read',payload_bytes=len(json.dumps(payload).encode()),max_tools=0,max_seconds=30)
            adapter.owner_dispatch(payload,probe=True,recovery=target,validate=lambda value:value=='READY')
            originals=adapter.owner_originals();expected=dict(owner=saved['owner'],checkpoint=target.validate(adapter.owner_authority()),originals=originals)
            payload=[dict(type='text',text=adapter.owner_read_guide(originals)+'\nReturn exactly '+json.dumps(expected),text_elements=[])]
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


def source_revision_cli():
    """Parent-only admission; no model, receipt rebinding or task transition."""
    import argparse
    from .cli import require_human_tty
    from .store import Store
    parser=argparse.ArgumentParser(description=source_revision_cli.__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--binding',required=True,type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();config=json.loads(args.config.read_text());binding=json.loads(args.binding.read_text())
    controller=Path(__file__).resolve().parent.parent
    parent,_,records=inspect_source_revision(config,binding,controller)
    if args.check:
        print(json.dumps(dict(status='RUNTIME_SOURCE_REVISION_CHECKED',prepared=bool(records),
            source=binding['source_hash'],model_dispatch='NOT_STARTED',foreground_line=source_revision_line(binding,parent))))
        return
    if records:
        raise Rejected('Source authority already recorded; inspect rather than replay')
    with require_human_tty() as tty:
        tty.write('New source authority only; the original checkpoint is preserved.\nType exactly:\n'+source_revision_line(binding,parent)+'\n> ')
        tty.flush();text=tty.readline().strip()
    store=Store(Path(config['home']))
    try:
        print(json.dumps(prepare_source_revision(store,config,binding,controller,text)),flush=True)
    finally:
        store.close()


if __name__=='__main__':
    source_revision_cli()
