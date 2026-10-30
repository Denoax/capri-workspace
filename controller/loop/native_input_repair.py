"""Bound new source after the observed inventory rejection before backend.dispatch.

The failed classification and consumed intent remain unchanged. This accepts no
generic uncertain turn: the exact stopped event sequence contains no owner/model
dispatch and every recorded backend is still empty, revoked and dead.
"""
import contextlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

from .adapter import process_identity
from .native_stopped import FileBinding, StoppedCompaction, StoppedReadOnlyState, event, require
from .native_qualification import checked_terminal_endpoint, create_source, load_materials
from .native_packet import load, verify_source_materials
from .native_startup import run_session
from .settings import Settings
from .util import digest, identity, tree

KIND = 'PRE_DISPATCH_MATERIAL_REPAIR'


def require_no_model_frames(received):
    forbidden={digest(n.encode()) for n in ('turn/started','turn/completed','thread/tokenUsage/updated','item/started','item/completed','model/rerouted')}
    for frame in received:
        envelope=frame['envelope'];method=envelope.get('method')
        method_hash=method.get('sha256') if isinstance(method,dict) else digest(method.encode()) if isinstance(method,str) else None
        require(envelope.get('turnId') is None and method_hash not in forbidden,'Native model/lifecycle effects prevent pre-dispatch repair')


def ancestry(binding):
    old = FileBinding(**binding['base']).json()
    require(old['kind'] == 'COMPLETED_OWNER_SOURCE_REVISION', 'Exact source-delivery ancestry required')
    previous = FileBinding(**old['base']).json()
    original = FileBinding(**previous['base']).json()
    return old, previous, StoppedCompaction.parse(FileBinding(**original['case']).json())


def stopped_effects(binding, view):
    from .native_owner_material import owner_effects, foreground_line
    old, previous, case = ancestry(binding)
    owner_effects(old, previous, view)
    intent, held = event(view,binding['intent_event']), event(view,binding['held_event'])
    require(intent['kind']=='NATIVE_OWNER_MATERIAL_INTENT' and intent['data']['binding_hash']==identity(old) and
            intent['data']['source']==old['target_source'] and held['kind']=='NATIVE_OWNER_MATERIAL_HELD' and
            held['data']['admission_event']==intent['seq'] and held['data']['binding_hash']==identity(old) and
            held['data']['error_type']=='Rejected' and held['data']['retry']=='FORBIDDEN', 'Exact consumed source-delivery intent/hold required')
    scope=event(view,intent['data']['prepared_event'])
    require(scope['kind']=='NATIVE_OWNER_MATERIAL_PREPARED' and scope['data']['binding_hash']==identity(old) and
            scope['data']['origin']=='FOREGROUND_CONTROLLING_TTY' and scope['data']['text']==foreground_line(old), 'Prior foreground source scope differs')
    cfg=FileBinding(**old['config']).json(); home=Path(cfg['home']); root=Path(cfg['settings']['state_dir'])
    require(intent['data']['home']==str(home) and binding['old_database']['path']==str(home/'state/workflow.sqlite3') and
            binding['registry']['path']==str(root/'registry.json') and binding['supervisor']['path']==str(root/'supervisor.json'), 'Failed destination binding differs')
    reg=FileBinding(**binding['registry']).json();sup=FileBinding(**binding['supervisor']).json()
    with StoppedReadOnlyState(home) as state:
        require([r['kind'] for r in state.db.execute('SELECT kind FROM events ORDER BY seq')]==[
            'NATIVE_STARTUP','NATIVE_CAPABILITY_STAGED_HELD','NATIVE_THINKER_REGISTERED','NATIVE_STARTUP','NATIVE_STARTUP',
            'NATIVE_STARTUP','NATIVE_THINKER_CAPABILITY_HELD','NATIVE_STARTUP','NATIVE_CAPABILITY_REVOKED'], 'Unknown dispatch or failed-home effects')
        require(all(state.db.execute('SELECT COUNT(*) FROM '+n).fetchone()[0]==0 for n in ('tasks','attempts','questions','human_inputs')), 'Task or human effects prevent input repair')
        starts=[json.loads(r['data']) for r in state.db.execute("SELECT data FROM events WHERE kind='NATIVE_STARTUP' ORDER BY seq")]
        require([r['milestone'] for r in starts]==['LAUNCH_INTENT','SLOTS_CREATED','CLIENTS_ATTACHED','PROBE_DISPATCH_INTENT','FAILED_OR_UNCERTAIN'] and
                starts[-1]['details']==dict(classification='EXECUTION_REQUIRES_RECONCILIATION',error='Source file exceeds bounded snapshot limit',last_proved='PROBE_DISPATCH_INTENT',task=None), 'Only the observed pre-RPC input failure is supported')
        session=starts[0]['parameters'];owner=session['owner']
        from .native_startup_repair import condition
        require(owner==str(uuid.uuid5(uuid.NAMESPACE_URL,'capri-owner-material:'+condition(old))) and all(r['parameters_hash']==identity(session) and r['operation']==session['operation'] for r in starts), 'Failed owner/session identity differs')
        require(session['source_hash']==old['target_source'] and session['controller_hash']==old['controller_hash'] and session['config_hash']==identity(cfg) and starts[1]['details']['registry']==reg, 'Failed source/config/registry differs')
        caps=state.db.execute('SELECT owner,scope,enabled FROM capabilities').fetchall()
        require(len(caps)==1 and caps[0]['owner']==owner and caps[0]['enabled']==0 and json.loads(caps[0]['scope'])==dict(repo=str(home/'fixtures/source'),request=old['request'],key=owner+':native-revision'), 'Failed capability differs or remains enabled')
        sessions=state.db.execute('SELECT id,owner,role,runtime,active FROM sessions').fetchall()
        require(len(sessions)==1 and dict(sessions[0])==dict(id=reg['thinker']['thread'],owner=owner,role='thinker',runtime=str(root/'thinker/runtime'),active=0), 'Failed session identity differs')
    FileBinding(**binding['old_database']).read()
    settings=Settings(**cfg['settings']);pids=[sup['pid']]
    require(set(reg)==set(binding['received'])=={'thinker','doer','reviewer'} and sup['source']==old['target_source'] and sup['maintenance_operation']==session['operation'], 'Failed process/receive ownership differs')
    for role,row in reg.items():
        require(row['empty'] is True and row['phase']=='read' and row['model']==settings.model and row['effort']==settings.efforts[role], 'Occupied or changed role cannot use input repair')
        spec=binding['received'][role];require(spec['path']==str(root/role/str(row['generation'])/'received-frames.jsonl'),'Wrong receive path')
        frames=[json.loads(line) for line in FileBinding(**spec).read().splitlines()]
        received=[f for f in frames if f['phase']=='RECEIVED']
        require(received and all(f['role']==role and f['generation']==row['generation'] and f.get('expected_thread') in (None,row['thread']) for f in received) and not any(f['phase']=='REJECTED' for f in frames),'Rejected or wrong-generation frames')
        require_no_model_frames(received)
        pids.append(row['pid'])
    terminals=tuple(FileBinding(**v) for v in binding['terminals']);require(terminals,'Closed terminal evidence required')
    for spec in terminals:
        require(Path(spec.path).parent==root and Path(spec.path).name.startswith('terminal-registry-closed-'),'Wrong closed terminal record')
        pids.extend(r['pid'] for r in spec.json().values())
    require(all(process_identity(p) is None for p in pids),'Live or reused process blocks input repair')
    require(all(not os.path.lexists(root/n) for n in ('thinker.sock','doer.sock','reviewer.sock','operator.sock')) and not any((root/'input-receipts').glob('*.json')),'Remaining endpoint or human input')
    checked_terminal_endpoint(SimpleNamespace(runtime=str(root),terminals=terminals))
    require(identity(tree(home/'fixtures/source'))==old['target_source'] and identity(tree(session['workspace']))==old['target_source'],'Failed source/snapshot changed')
    # Audit the previously bound oversized evidence without relaxing util.tree.
    mounted=Path(session['inputs']);material={r['name']:FileBinding(str(mounted/r['name']),r['sha256']).read() for r in old['materials']}
    require(sum(map(len,material.values()))<=32_000_000 and {str(p.relative_to(mounted)) for p in mounted.rglob('*') if p.is_file()}==set(material) and not any(p.is_symlink() for p in mounted.rglob('*')) and all((mounted/n).stat().st_mode&0o777==0o600 for n in material),'Failed material inventory changed')
    index=load(mounted/'current-context');verify_source_materials(material,index)
    large={n for n,raw in material.items() if len(raw)>8_000_000}
    require(large=={index['binding']['source_delivery']['archive']},'Unexpected oversized original')
    return old,case,cfg,dict(classification='EXACT_PRE_DISPATCH_INPUT_REJECTION',prior_intent=intent['seq'],prior_hold=held['seq'],observed_model_dispatches=0,old_case=case.key())


def check(config,binding,controller,*,view=None,require_prepared=True):
    from .native_startup_repair import condition, records, foreground_line, PREPARED, INTENT
    _,_,case=ancestry(binding);require(config==case.config.json(),'Original configuration changed')
    with (StoppedReadOnlyState(case.home) if view is None else contextlib.nullcontext(view)) as state:
        old,case,prior,proof=stopped_effects(binding,state)
        require(not records(state,binding,INTENT),'Input-repair intent consumed; never replay')
        prepared=records(state,binding,PREPARED);require(prepared or not require_prepared,'Distinct input-layout source scope required')
        if prepared:require(prepared[0]['origin']=='FOREGROUND_CONTROLLING_TTY' and prepared[0]['text']==foreground_line(binding),'Input repair scope differs')
    controller=Path(controller).resolve();target=FileBinding(**binding['config']).json();home=Path(target['home']);runtime=target['settings']['state_dir']
    require(str(controller.parent)==binding['target_root'] and identity(tree(controller.parent))==binding['target_source'] and binding['target_source']!=old['target_source'] and identity(tree(controller))==binding['controller_hash'],'Exact distinct repaired source required')
    require(home.resolve()==home and home.is_relative_to(case.home) and home!=Path(prior['home']) and not os.path.lexists(home) and Path(runtime).parent==home and Path(runtime).name=='r','Unused input-repair destination required')
    expected=json.loads(json.dumps(prior));expected.update(home=str(home),controller=str(controller));expected['settings']['state_dir']=runtime
    expected['workflow'].update(notes=str(home/'notes'),authorized_repositories=[str(home/'fixtures/source')])
    expected['roles']={r:dict(workspace=str(home/'slots'/r/'workspace'),inputs=str(home/'slots'/r/'inputs')) for r in ('thinker','doer','reviewer')}
    require(target==expected,'Input repair cannot change authority or limits')
    settings=Settings(**target['settings']);require(Path(settings.auth_file).is_file() and digest(Path(settings.executable()).read_bytes())==settings.binary_sha256 and len(os.fsencode(Path(runtime)/'reviewer.sock'))<108,'Pinned runtime prerequisites differ')
    material,index=load_materials(binding)
    immutable={r['name']:FileBinding(r['path'],r['sha256']).read() for r in old['materials'] if not r['name'].startswith(('current-context/','current-source/')) and r['name']!='successor-request.json'}
    require(all(material.get(n)==raw for n,raw in immutable.items()) and binding['request']['human_answers']==old['request']['human_answers'] and 'lineage' not in binding['request'],'Original requirements/answers/history changed')
    require(json.loads(material['INPUT_REPAIR_LINEAGE.json'])==dict(prior_binding=binding['base'],prior_archive=next(r for r in old['materials'] if r['name']=='current-source/source.zip'),prior_intent=binding['intent_event'],prior_hold=binding['held_event']),'Exact old source archive/failed scope lineage required')
    owner=str(uuid.uuid5(uuid.NAMESPACE_URL,'capri-startup-repair:'+condition(binding)))
    require(index['binding']['owner']==owner and index['binding']['repo_source_hash']==binding['target_source'] and index['binding']['controller_source_hash']==binding['target_source'] and index['binding']['scope_hash']==digest(binding['request']['text'].encode()) and isinstance(index['binding']['source_delivery']['archive'],list),'Repaired current source/owner/parts differ')
    verify_source_materials(material,index)
    return dict(status='PREMODEL_REPAIR_LAUNCH_CHECKED' if prepared else 'PREMODEL_REPAIR_NEEDS_FOREGROUND',binding_hash=identity(binding),owner=owner,home=str(home),runtime=runtime,original_repo=str(home/'fixtures/source'),source=binding['target_source'],controller=binding['controller_hash'],proof=proof,prepared_event=prepared[0]['event'] if prepared else None,model_dispatch='NOT_STARTED')


def launch(config,binding,controller,args):
    from .store import Store
    from .native_startup_repair import commit,INTENT,records
    check(config,binding,controller);_,_,case=ancestry(binding);store=Store(case.home)
    try:
        with store.lock('native-qualification'):
            plan=commit(store,config,binding,controller)
            try:
                create_source(SimpleNamespace(target_root=binding['target_root'],target_source=binding['target_source']),plan)
                target=FileBinding(**binding['config']).json()
                for spec in target['roles'].values():
                    for path in spec.values():Path(path).mkdir(parents=True,exist_ok=True)
                material,_=load_materials(binding)
                session=dict(operation='startup-repair-'+identity(binding),owner=plan['owner'],source_hash=binding['target_source'],controller_hash=binding['controller_hash'],config_hash=identity(target),predecessor_receipt=case.prepared.json()['binding']['predecessor_receipt'],fresh_qualification=True,workspace=str(Path(plan['home'])/'snapshots/thinker'),inputs=str(Path(plan['home'])/'inputs/thinker'),registry=binding['registry'],context_packet=binding['context_packet'],required_requirements=json.loads(material['preserved-requirements.json']),verify_visible_clients=True)
                def admit():
                    stopped_effects(binding,store)
                    require(identity(tree(Path(controller).parent))==binding['target_source'] and FileBinding(**binding['config']).json()==target and len(records(store,binding,INTENT))==1,'Input repair changed after committed intent')
                return run_session(target,args,controller,dict(binding=session,scope_text=binding['request']['text'],admission_event=plan['admission_event']),plan,session,material,binding['request'],admit)
            except BaseException as ex:
                with store.transaction():store.event(None,'NATIVE_PREMODEL_STARTUP_REPAIR_HELD',dict(prior_intent=binding['intent_event'],binding_hash=identity(binding),admission_event=plan['admission_event'],error_type=type(ex).__name__,retry='FORBIDDEN'))
                raise
    finally:store.close()
