"""Explicit source-bound recovery of an audited failure before the first probe.

No replay of the consumed original intent, no reuse/deletion of its home, no
model completion inference. Existing Store events and foreground TTY boundary
own a distinct condition. Only the observed frontend mapping failure is admitted.
"""
import contextlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
import uuid

from .adapter import process_identity
from .native_qualification import load_materials,checked_terminal_endpoint,create_source
from .native_startup import run_session
from .native_stopped import FileBinding,StoppedCompaction,StoppedReadOnlyState,event,inspect,require
from .settings import Settings
from .util import identity,tree,digest,Rejected

PREPARED='NATIVE_PREMODEL_STARTUP_REPAIR_PREPARED'
INTENT='NATIVE_PREMODEL_STARTUP_REPAIR_INTENT'


def parse(value):
    keys={'schema','kind','base','intent_event','held_event','old_database','registry','supervisor',
          'terminals','received','target_root','target_source','controller_hash','config','materials',
          'context_packet','request'}
    require(isinstance(value,dict) and set(value)==keys and type(value['schema']) is int and value['schema']==1 and
            value['kind'] in ('PREMODEL_NATIVE_QUALIFICATION_REPAIR','PRE_DISPATCH_MATERIAL_REPAIR'),'Exact pre-model repair binding required')
    for name in ('base','old_database','registry','supervisor','config'):
        require(set(value[name])=={'path','sha256'},'Exact repair file binding required');FileBinding(**value[name]).read()
    require(type(value['intent_event']) is int and type(value['held_event']) is int and
            0<value['intent_event']<value['held_event'],'Exact prior intent/hold events required')
    return value


def condition(binding):
    return identity(dict(base=binding['base'],intent=binding['intent_event'],source=binding['target_source'],config=binding['config']))


def foreground_line(binding):
    return ('Authorize pre-model startup repair '+str(binding['intent_event'])+' using source '+binding['target_source']+
            ' and binding '+identity(binding)+'; preserve all prior scopes, failures and limits; stop at AWAITING_HUMAN without acceptance or integration.')


def records(view,binding,kind):
    rows=[]
    for row in view.db.execute('SELECT seq,data FROM events WHERE kind=?',(kind,)):
        data=json.loads(row['data'])
        if data.get('prior_intent')==binding['intent_event']:
            require(data.get('binding_hash')==identity(binding),'Consumed/prepared recovery cannot be rebound')
            rows.append(dict(event=row['seq'],**data))
    require(len(rows)<=1,'Conflicting pre-model recovery records')
    return rows


def stopped_effects(binding,base,case,view):
    intent,held=event(view,binding['intent_event']),event(view,binding['held_event'])
    prior=intent['data']
    require(intent['kind']=='NATIVE_DISPOSABLE_QUALIFICATION_INTENT' and held['kind']=='NATIVE_DISPOSABLE_QUALIFICATION_HELD' and
            prior['case_hash']==case.key() and prior['binding_hash']==identity(base) and
            held['data']['admission_event']==intent['seq'] and held['data']['case_hash']==case.key() and held['data']['error_type']=='Rejected',
            'Exact consumed launch/hold authority required')
    old=FileBinding(**base['target_config']).json();home=Path(old['home']);root=Path(old['settings']['state_dir'])
    require(binding['old_database']['path']==str(home/'state/workflow.sqlite3') and
            binding['registry']['path']==str(root/'registry.json') and binding['supervisor']['path']==str(root/'supervisor.json'),
            'Failed home/config/registry binding differs')
    require(prior['target_home']==str(home) and prior['runtime']==str(root) and prior['target_source']==case.target_source and
            prior['target_config']==base['target_config'],'Original intent destination differs')
    with StoppedReadOnlyState(home) as stopped:
        for table in ('tasks','attempts','questions','human_inputs'):
            require(stopped.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0,'Failed scope contains task, turn or human effects')
        caps=stopped.db.execute('SELECT owner,scope,enabled FROM capabilities').fetchall()
        require(len(caps)==1 and caps[0]['enabled']==0 and caps[0]['owner']==prior['qualification_owner'] and
                json.loads(caps[0]['scope'])['request']==base['request'] and
                json.loads(caps[0]['scope'])['repo']==str(home/'fixtures/source'),'Failed capability scope/revocation differs')
        rows=stopped.db.execute('SELECT kind,data FROM events ORDER BY seq').fetchall()
        require([r['kind'] for r in rows]==['NATIVE_STARTUP','NATIVE_CAPABILITY_STAGED_HELD','NATIVE_THINKER_REGISTERED',
                    'NATIVE_STARTUP','NATIVE_STARTUP','NATIVE_CAPABILITY_REVOKED'],'Unexplained failed-home events')
        startup=[json.loads(r['data']) for r in rows if r['kind']=='NATIVE_STARTUP']
        require([r['milestone'] for r in startup]==['LAUNCH_INTENT','SLOTS_CREATED','FAILED_OR_UNCERTAIN'] and
                startup[-1]['details']==dict(classification='STARTUP_REQUIRES_EFFECT_AUDIT',error='Native visible frontend mapping differs',last_proved='SLOTS_CREATED',task=None),
                'Only the accounted before-probe frontend mapping failure is supported')
        session=startup[0]['parameters']
        require(all(r['parameters_hash']==identity(session) and r['operation']==session['operation'] for r in startup) and
                session['config_hash']==identity(old) and session['source_hash']==case.target_source and
                session['controller_hash']==base['target_controller_hash'] and session['owner']==prior['qualification_owner'] and
                session['fresh_qualification'] is True and session['verify_visible_clients'] is True,'Failed session source/owner/config differs')
        sessions=stopped.db.execute('SELECT id,owner,role,runtime,active FROM sessions').fetchall()
        registry=FileBinding(**binding['registry']).json()
        require(len(sessions)==1 and dict(sessions[0])==dict(id=registry['thinker']['thread'],owner=session['owner'],
                role='thinker',runtime=str(root/'thinker/runtime'),active=0),'Failed native session identity differs')
        require(startup[0]['details']['source']==case.target_source,'Failed launch source differs')
    FileBinding(**binding['old_database']).read()
    reg=FileBinding(**binding['registry']).json();sup=FileBinding(**binding['supervisor']).json()
    require(set(reg)=={'thinker','doer','reviewer'} and startup[1]['details']['registry']==reg,'Failed role registry differs')
    require(sup.get('source')==case.target_source and sup.get('maintenance_operation')==session['operation'],'Failed supervisor differs')
    settings=Settings(**old['settings']);pids=[sup['pid']]
    require(set(binding['received'])==set(reg) and binding['terminals'],'Complete public receive/terminal evidence required')
    for role,row in reg.items():
        require(row['empty'] is True and row['phase']=='read' and row['model']==settings.model and row['effort']==settings.efforts[role],
                'Occupied or changed role cannot use pre-model recovery')
        spec=binding['received'][role]
        require(spec['path']==str(root/role/str(row['generation'])/'received-frames.jsonl'),'Receive-generation path differs')
        frames=[json.loads(line) for line in FileBinding(**spec).read().splitlines()]
        received=[r for r in frames if r['phase']=='RECEIVED']
        require(received and all(r['role']==role and r['generation']==row['generation'] and
                r.get('expected_thread') in (None,row['thread']) for r in received),'Receive producer differs')
        require(not any(r['phase']=='REJECTED' for r in frames),'Rejected backend effects require separate audit')
        require(not any(r['envelope'].get('method') in ('turn/started','turn/completed','thread/tokenUsage/updated','item/started','item/completed') for r in received),
                'Model/lifecycle effects prevent pre-model recovery')
        pids.append(row['pid'])
    terminals=tuple(FileBinding(**s) for s in binding['terminals'])
    for spec in terminals:
        require(Path(spec.path).parent==root and Path(spec.path).name.startswith('terminal-registry-closed-'),'Exact owned terminal cleanup record required')
        pids += [r['pid'] for r in spec.json().values()]
    require(all(process_identity(pid) is None for pid in pids),'Live or PID-reused old process holds recovery')
    require(all(not os.path.lexists(root/n) for n in ('thinker.sock','doer.sock','reviewer.sock','operator.sock')),'Old endpoint remains')
    require(not any((root/'input-receipts').glob('*.json')),'Captured native input requires explicit reconciliation')
    checked_terminal_endpoint(SimpleNamespace(runtime=str(root),terminals=terminals))
    require(identity(tree(home/'fixtures/source'))==case.target_source and
            identity(tree(session['workspace']))==case.target_source,'Failed source/snapshot changed')
    expected={r['name']:dict(sha256=FileBinding(r['path'],r['sha256']).sha256,mode=0o600) for r in base['materials']}
    require(tree(session['inputs'])==expected,'Failed mounted original inputs changed')
    return old,reg,dict(classification='ACCOUNTED_PREMODEL_MAPPING_REJECTION',observed_model_turns=0,
                       original_intent=intent['seq'],original_hold=held['seq'],failed_home=str(home),failed_session_hash=identity(session))


def check(old_config,value,controller,*,view=None,require_prepared=True):
    binding=parse(value)
    if binding['kind']=='PRE_DISPATCH_MATERIAL_REPAIR':
        from .native_input_repair import check as input_check
        return input_check(old_config,binding,controller,view=view,require_prepared=require_prepared)
    base=FileBinding(**binding['base']).json()
    case=StoppedCompaction.parse(FileBinding(**base['case']).json())
    # Preserve and inspect the original immutable case/fence. Never replace its
    # target/source/case hash to escape a single-use guard.
    with (StoppedReadOnlyState(case.home) if view is None else contextlib.nullcontext(view)) as state:
        prior=inspect(old_config,case,base['recovery_controller'],view=state)
        require(prior['fence_event'] is not None and prior['prepared_event'] is not None,'Original scope/fence must remain committed')
        old_intent=event(state,binding['intent_event'])['data']
        require(old_intent['fence_event']==prior['fence_event'] and old_intent['prepared_event']==prior['prepared_event'],'Original launch scope/fence differs')
        old,reg,proof=stopped_effects(binding,base,case,state)
        require(not records(state,binding,INTENT),'Repair launch intent consumed; inspect without replay')
        prepared=records(state,binding,PREPARED)
        require(bool(prepared) or not require_prepared,'Distinct repaired-source foreground scope required')
        if prepared:require(prepared[0]['origin']=='FOREGROUND_CONTROLLING_TTY' and prepared[0]['text']==foreground_line(binding),'Repair foreground scope differs')
    controller=Path(controller).resolve();target=FileBinding(**binding['config']).json();home=Path(target['home']);runtime=target['settings']['state_dir']
    require(str(controller.parent)==binding['target_root'] and identity(tree(controller.parent))==binding['target_source'] and
            binding['target_source']!=case.target_source and identity(tree(controller))==binding['controller_hash'],'Exact distinct repaired source required')
    require(home.is_absolute() and home.resolve()==home and home.is_relative_to(case.home) and home!=Path(old['home']) and
            not os.path.lexists(home) and Path(runtime).parent==home and Path(runtime).name=='r','Unused private repaired condition required')
    expected=json.loads(json.dumps(old));expected.update(home=str(home),controller=str(controller));expected['settings']['state_dir']=runtime
    expected['workflow'].update(notes=str(home/'notes'),authorized_repositories=[str(home/'fixtures/source')])
    expected['roles']={r:dict(workspace=str(home/'slots'/r/'workspace'),inputs=str(home/'slots'/r/'inputs')) for r in ('thinker','doer','reviewer')}
    require(target==expected,'Repaired configuration cannot broaden authority or change limits')
    settings=Settings(**target['settings']);require(Path(settings.auth_file).is_file(),'Configured auth mount unavailable')
    require(all(shutil.which(n) for n in ('git','bwrap','tmux')),'Supported-host prerequisites unavailable')
    require(digest(Path(settings.executable()).read_bytes())==settings.binary_sha256,'Pinned executable differs')
    require(len(os.fsencode(Path(runtime)/'reviewer.sock'))<108,'Repaired native socket path too long')
    material,index=load_materials(binding)
    # Original authority/answers stay exact; only current request/context and the
    # new repair brief may differ. No original is silently demoted or discarded.
    immutable={n for n in (r['name'] for r in base['materials']) if not n.startswith('current-context/') and n not in ('successor-request.json','QUALIFICATION_TASK.md')}
    old_material={r['name']:FileBinding(r['path'],r['sha256']).read() for r in base['materials']}
    require(all(material.get(n)==old_material[n] for n in immutable),'Preserved original/answer/source material differs')
    owner=str(uuid.uuid5(uuid.NAMESPACE_URL,'capri-startup-repair:'+condition(binding)))
    require(binding['request'].get('human_answers')==base['request']['human_answers'] and 'lineage' not in binding['request'] and
            binding['request']['text'].startswith('Recover only the accounted pre-model native launch '+str(binding['intent_event'])+' '),
            'Scoped current request/answers differ')
    require(index['binding'].get('owner')==owner and index['binding'].get('repo_source_hash')==binding['target_source'] and
            index['binding'].get('controller_source_hash')==binding['target_source'] and
            index['binding'].get('scope_hash')==digest(binding['request']['text'].encode()),'Repaired context identity differs')
    return dict(status='PREMODEL_REPAIR_LAUNCH_CHECKED' if prepared else 'PREMODEL_REPAIR_NEEDS_FOREGROUND',
        binding_hash=identity(binding),condition=condition(binding),owner=owner,home=str(home),runtime=runtime,
        original_repo=str(home/'fixtures/source'),source=binding['target_source'],controller=binding['controller_hash'],
        proof=proof,prepared_event=prepared[0]['event'] if prepared else None,model_dispatch='NOT_STARTED')


def prepare(store,old_config,binding,controller,text):
    with store.lock('native-startup'),store.lock('native-writer'),store.transaction():
        plan=check(old_config,binding,controller,view=store,require_prepared=False)
        require(plan['prepared_event'] is None,'Repair scope already prepared; do not repeat input')
        require(text==foreground_line(binding),'Exact repaired-source foreground scope required')
        seq=store.event(None,PREPARED,dict(prior_intent=binding['intent_event'],binding_hash=identity(binding),
            text=text,origin='FOREGROUND_CONTROLLING_TTY',source=binding['target_source'],proof=plan['proof'],new_dispatch='NOT_AUTHORIZED'))
        return dict(status='PREMODEL_REPAIR_PREPARED',event=seq,source=binding['target_source'],model_dispatch='NOT_STARTED')


def commit(store,old_config,binding,controller):
    with store.lock('native-startup'),store.lock('native-writer'),store.transaction():
        plan=check(old_config,binding,controller,view=store)
        seq=store.event(None,INTENT,dict(prior_intent=binding['intent_event'],binding_hash=identity(binding),
            source=binding['target_source'],prepared_event=plan['prepared_event'],home=plan['home'],old_intent='PRESERVED_CONSUMED',replay='FORBIDDEN'))
        return dict(plan,admission_event=seq)


def launch(old_config,binding,controller,args):
    if binding['kind']=='PRE_DISPATCH_MATERIAL_REPAIR':
        from .native_input_repair import launch as input_launch
        return input_launch(old_config,binding,controller,args)
    from .store import Store
    check(old_config,binding,controller)
    base=FileBinding(**binding['base']).json();case=StoppedCompaction.parse(FileBinding(**base['case']).json());store=Store(case.home)
    try:
        with store.lock('native-qualification'):
            plan=commit(store,old_config,binding,controller)
            try:
                create_source(SimpleNamespace(target_root=binding['target_root'],target_source=binding['target_source']),plan)
                target=FileBinding(**binding['config']).json()
                for spec in target['roles'].values():
                    for path in spec.values():Path(path).mkdir(parents=True,exist_ok=True)
                material,_=load_materials(binding);requirements=json.loads(material['preserved-requirements.json'])
                session=dict(operation='startup-repair-'+condition(binding),owner=plan['owner'],source_hash=binding['target_source'],
                    controller_hash=binding['controller_hash'],config_hash=identity(target),predecessor_receipt=case.prepared.json()['binding']['predecessor_receipt'],
                    fresh_qualification=True,workspace=str(Path(plan['home'])/'snapshots/thinker'),inputs=str(Path(plan['home'])/'inputs/thinker'),
                    registry=binding['registry'],context_packet=binding['context_packet'],required_requirements=requirements,verify_visible_clients=True)
                receipt=dict(binding=session,scope_text=binding['request']['text'],admission_event=plan['admission_event'])
                def revalidate():
                    inspect(old_config,case,base['recovery_controller'],view=store)
                    stopped_effects(binding,base,case,store)
                    require(identity(tree(Path(controller).parent))==binding['target_source'] and
                            FileBinding(**binding['config']).json()==target,'Repaired source/config drift after intent')
                    require(len(records(store,binding,INTENT))==1,'Committed repair intent missing')
                return run_session(target,args,controller,receipt,plan,session,material,binding['request'],revalidate)
            except BaseException as ex:
                with store.transaction():store.event(None,'NATIVE_PREMODEL_STARTUP_REPAIR_HELD',dict(prior_intent=binding['intent_event'],
                    binding_hash=identity(binding),admission_event=plan['admission_event'],error_type=type(ex).__name__,retry='FORBIDDEN'))
                raise
    finally:store.close()


def run_cli(config,args,controller):
    require(args.binding is not None,'Exact pre-model repair binding required');binding=parse(json.loads(args.binding.read_text()))
    plan=check(config,binding,controller,require_prepared=False)
    if args.check or args.command=='inspect-startup-repair':print(json.dumps(plan),flush=True);return
    if args.command=='launch-startup-repair':
        require(not args.headless,'Exactly three visible native clients required');return launch(config,binding,controller,args)
    require(plan['prepared_event'] is None,'Repair already prepared; no repeated foreground input')
    from .cli import require_human_tty
    with require_human_tty() as tty:
        tty.write('Distinct repaired-source scope only. Old intents stay consumed.\nType exactly:\n'+foreground_line(binding)+'\n> ');tty.flush();text=tty.readline().strip()
    if binding['kind']=='PRE_DISPATCH_MATERIAL_REPAIR':
        from .native_input_repair import ancestry
        _,_,case=ancestry(binding)
    else:
        base=FileBinding(**binding['base']).json();case=StoppedCompaction.parse(FileBinding(**base['case']).json())
    from .store import Store
    store=Store(case.home)
    try:print(json.dumps(prepare(store,config,binding,controller,text)),flush=True)
    finally:store.close()
