"""Explicit new condition after a completed, read-only owner source hold.

The prior owner has no submitted task. All its turns must have matching successful
terminals, its capability must be revoked, and its files/processes must be proven
unchanged/stopped. This is neither an uncertain-execution retry nor core re-contract.
"""
import contextlib
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
import uuid

from .adapter import process_identity
from .native_stopped import FileBinding,StoppedCompaction,StoppedReadOnlyState,event,inspect,require
from .native_startup_repair import records,condition,stopped_effects
from .native_qualification import load_materials,checked_terminal_endpoint,create_source
from .native_startup import run_session
from .settings import Settings
from .util import identity,tree,digest

PREPARED='NATIVE_OWNER_MATERIAL_PREPARED'
INTENT='NATIVE_OWNER_MATERIAL_INTENT'


def parse(b):
    keys={'schema','kind','base','intent_event','owner_hold_event','old_database','registry','supervisor',
          'terminals','received','captures','target_root','target_source','controller_hash','config',
          'materials','context_packet','request','retained_ui'}
    require(isinstance(b,dict) and set(b)==keys and type(b['schema']) is int and b['schema']==1 and
            b['kind']=='COMPLETED_OWNER_SOURCE_REVISION','Exact completed owner-source binding required')
    for n in ('base','old_database','registry','supervisor','config'):FileBinding(**b[n]).read()
    require(type(b['intent_event']) is int and b['intent_event']>0 and type(b['owner_hold_event']) is int and b['owner_hold_event']>0,
            'Exact prior intent/owner-hold events required')
    return b


def retained_ui(b,root,terminals):
    if b['retained_ui'] is None:
        return checked_terminal_endpoint(SimpleNamespace(runtime=str(root),terminals=terminals))
    # This new, explicitly bound condition preserves the old inactive artifact.
    # It grants neither cleanup nor resume of a historical UI socket whose ctime
    # differs from its closed record. Model transport endpoints remain absent.
    audit=FileBinding(**b['retained_ui']).json();p=root/'ui.sock';st=p.lstat()
    observed=dict(device=st.st_dev,inode=st.st_ino,uid=st.st_uid,ctime_ns=st.st_ctime_ns)
    require(audit['kind']=='PRESERVED_INACTIVE_UI_CTIME_DRIFT' and audit['path']==str(p) and audit['observed']==observed and
            stat.S_ISSOCK(st.st_mode) and st.st_uid==os.getuid() and stat.S_IMODE(root.stat().st_mode)==0o700,'Retained UI artifact identity differs')
    servers=[s.json().get('_server',{}) for s in terminals]
    require(len(servers)==1 and all(observed[k]==servers[0]['socket_identity'][k] for k in ('device','inode','uid')) and
            audit['prior']==servers[0]['socket_identity'],'Retained UI inode/owner differs')
    attach=FileBinding(**audit['attach']).json()
    require(attach['kind']=='OUTER_TERMINAL_ATTACH_EXISTING_THREE_NATIVE_SLOTS' and attach['argv'][0]=='/usr/bin/kitty' and
        attach['argv'][-6:]==['tmux','-S',str(p),'attach-session','-t','roles'] and process_identity(attach['pid']) is None,
        'Recorded outer UI attach remains unresolved')
    require(not any(str(p)==line.split()[-1] for line in Path('/proc/net/unix').read_text().splitlines()[1:] if len(line.split())>=8),
        'Retained UI is still registered in the kernel')


def foreground_line(b):
    return ('Authorize completed owner source-delivery revision '+str(b['intent_event'])+' using source '+b['target_source']+
        ' and binding '+identity(b)+'; preserve all prior inputs, holds and limits; finish the existing V4 scope and stop at AWAITING_HUMAN without acceptance or integration.')


def completed_turn(spec,row):
    events=[json.loads(line) for line in FileBinding(**spec).read().splitlines()]
    require(events and all(e['role']=='thinker' and e['generation']==row['generation'] for e in events),'Owner capture producer differs')
    starts=[];ends=[]
    for e in events:
        msg=e['message'];p=msg.get('params',{})
        if msg.get('method') in ('turn/started','turn/completed'):
            require(p.get('threadId')==row['thread'],'Owner lifecycle thread differs')
            (starts if msg['method']=='turn/started' else ends).append(p['turn'])
    require(len(starts)==len(ends)==1 and starts[0]['id']==ends[0]['id'] and ends[0]['status']=='completed',
            'Every prior owner turn needs its matching successful terminal')
    return starts[0]['id']


def owner_effects(b,old,view):
    legacy=FileBinding(**old['base']).json();case=StoppedCompaction.parse(FileBinding(**legacy['case']).json())
    prior=inspect(case.config.json(),case,legacy['recovery_controller'],view=view)
    stopped_effects(old,legacy,case,view) # Preserve the already accounted pre-model ancestry.
    intent=event(view,b['intent_event']);require(intent['kind']=='NATIVE_PREMODEL_STARTUP_REPAIR_INTENT' and
        intent['data']['binding_hash']==identity(old) and intent['data']['source']==old['target_source'],'Prior repaired launch identity differs')
    scope=event(view,intent['data']['prepared_event']);require(scope['kind']=='NATIVE_PREMODEL_STARTUP_REPAIR_PREPARED' and
        scope['data']['binding_hash']==identity(old) and scope['data']['origin']=='FOREGROUND_CONTROLLING_TTY','Prior repaired foreground scope differs')
    cfg=FileBinding(**old['config']).json();home=Path(cfg['home']);root=Path(cfg['settings']['state_dir'])
    require(b['old_database']['path']==str(home/'state/workflow.sqlite3') and b['registry']['path']==str(root/'registry.json') and
            b['supervisor']['path']==str(root/'supervisor.json'),'Held owner destination differs')
    reg=FileBinding(**b['registry']).json();sup=FileBinding(**b['supervisor']).json();require(set(reg)=={'thinker','doer','reviewer'},'Exact held slots required')
    with StoppedReadOnlyState(home) as state:
        for table in ('tasks','attempts','questions','human_inputs'):
            require(state.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0,'Held owner has task/attempt/human effects')
        startup=[json.loads(r['data']) for r in state.db.execute("SELECT data FROM events WHERE kind='NATIVE_STARTUP' ORDER BY seq")]
        expected=['LAUNCH_INTENT','SLOTS_CREATED','CLIENTS_ATTACHED','PROBE_DISPATCH_INTENT','PROBE_COMPLETED',
                  'CURRENT_CONTEXT_DELIVERY_VALIDATED','SCOPE_RELEASED','WORK_DISPATCH_INTENT','OWNER_HELD']
        require([r['milestone'] for r in startup]==expected,'Unexplained or uncertain held-owner milestones')
        held=event(state,b['owner_hold_event']);require(held['kind']=='NATIVE_STARTUP' and held['data']==startup[-1],'Exact owner hold event differs')
        result=startup[-1]['details'];require(result['outcome']=='INSUFFICIENT_SOURCE' and result['gate']=='BLOCKED' and
            result['model_dispatch']=='STOPPED' and result['questions']==[],'Only a completed source hold is supported')
        session=startup[0]['parameters'];owner=session['owner']
        require(owner==str(uuid.uuid5(uuid.NAMESPACE_URL,'capri-startup-repair:'+condition(old))),'Prior prepared owner differs')
        require(all(r['parameters_hash']==identity(session) and r['operation']==session['operation'] for r in startup) and
                session['source_hash']==old['target_source'] and session['controller_hash']==old['controller_hash'] and
                session['config_hash']==identity(cfg),'Held session source/config differs')
        initial=startup[1]['details']['registry'];stable=('pid','thread','generation','process_identity','phase','model','effort','endpoint','socket_inode','lineage')
        require(set(initial)==set(reg) and all(all(initial[r][k]==reg[r][k] for k in stable) for r in reg),'Held backend identity drift')
        caps=state.db.execute('SELECT owner,scope,enabled FROM capabilities').fetchall()
        require(len(caps)==1 and caps[0]['owner']==owner and caps[0]['enabled']==0 and
            json.loads(caps[0]['scope'])['request']==old['request'] and json.loads(caps[0]['scope'])['repo']==str(home/'fixtures/source'),
            'Held owner capability differs or remains live')
        sessions=state.db.execute('SELECT id,owner,role,runtime,active FROM sessions').fetchall()
        require(len(sessions)==1 and dict(sessions[0])==dict(id=reg['thinker']['thread'],owner=owner,role='thinker',runtime=str(root/'thinker/runtime'),active=0),
                'Held Thinker session identity differs')
        dispatch=[dict(seq=r['seq'],**json.loads(r['data'])) for r in state.db.execute("SELECT seq,data FROM events WHERE kind='NATIVE_OWNER_DISPATCH' ORDER BY seq")]
        require(len(dispatch)==3 and [r['probe'] for r in dispatch]==[True,False,False] and
                all(r['owner']==owner and r['thread']==reg['thinker']['thread'] for r in dispatch),'Unexpected owner dispatch history')
        allowed={'NATIVE_STARTUP','NATIVE_OWNER_DISPATCH','NATIVE_CAPABILITY_STAGED_HELD','NATIVE_THINKER_REGISTERED',
                 'NATIVE_THINKER_CAPABILITY_HELD','NATIVE_THINKER_CAPABILITY_RELEASED','NATIVE_CAPABILITY_REVOKED'}
        require(all(r['kind'] in allowed for r in state.db.execute('SELECT kind FROM events')),'Unexplained owner effect')
    FileBinding(**b['old_database']).read()
    require(set(b['captures'])=={str(r['seq']) for r in dispatch},'Complete owner captures required')
    turns=[]
    for r in dispatch:
        spec=b['captures'][str(r['seq'])];require(spec['path']==str(Path(r['capture'])/'events.jsonl'),'Owner capture path differs')
        turns.append(completed_turn(spec,reg['thinker']))
    require(len(set(turns))==3,'Duplicate completed owner turn')
    settings=Settings(**cfg['settings']);pids=[sup['pid']]
    require(sup.get('source')==old['target_source'] and sup.get('maintenance_operation')==session['operation'],'Held supervisor differs')
    require(set(b['received'])==set(reg),'Complete role receive evidence required')
    for role,row in reg.items():
        require(row['phase']=='read' and row['model']==settings.model and row['effort']==settings.efforts[role] and
            row['empty']==(role!='thinker'),'Unexpected role/phase/model work')
        spec=b['received'][role];require(spec['path']==str(root/role/str(row['generation'])/'received-frames.jsonl'),'Receive path differs')
        frames=[json.loads(line) for line in FileBinding(**spec).read().splitlines()];received=[f for f in frames if f['phase']=='RECEIVED']
        require(received and all(f['role']==role and f['generation']==row['generation'] and f.get('expected_thread') in (None,row['thread']) for f in received) and
                not any(f['phase']=='REJECTED' for f in frames),'Rejected/wrong-generation receive effects')
        starts=[f for f in received if f['envelope'].get('method')=='turn/started']
        require(len(starts)==(3 if role=='thinker' else 0),'Uncaptured role/model turn')
        pids.append(row['pid'])
    terminals=tuple(FileBinding(**s) for s in b['terminals']);require(terminals,'Closed terminal ownership required')
    for spec in terminals:
        require(Path(spec.path).parent==root and Path(spec.path).name.startswith('terminal-registry-closed-'),'Wrong closed terminal record')
        pids += [v['pid'] for v in spec.json().values()]
    require(all(process_identity(p) is None for p in pids),'Live/PID-reused held process')
    require(all(not os.path.lexists(root/n) for n in ('thinker.sock','doer.sock','reviewer.sock','operator.sock')) and
            not any((root/'input-receipts').glob('*.json')),'Endpoint or unattested input remains')
    retained_ui(b,root,terminals)
    require(identity(tree(home/'fixtures/source'))==old['target_source'] and identity(tree(session['workspace']))==old['target_source'],
            'Held source/snapshot changed')
    require(tree(session['inputs'])=={r['name']:dict(sha256=r['sha256'],mode=0o600) for r in old['materials']},'Held original inputs changed')
    return case,cfg,dict(classification='COMPLETED_READ_ONLY_OWNER_SOURCE_HOLD',prior_intent=b['intent_event'],
        owner_hold=b['owner_hold_event'],owner=owner,completed_turns=turns,submitted_tasks=0,old_case=case.key())


def check(config,value,controller,*,view=None,require_prepared=True):
    b=parse(value);old=FileBinding(**b['base']).json();legacy=FileBinding(**old['base']).json();case=StoppedCompaction.parse(FileBinding(**legacy['case']).json())
    require(config==case.config.json(),'Original configuration changed')
    with (StoppedReadOnlyState(case.home) if view is None else contextlib.nullcontext(view)) as state:
        case,prior_cfg,proof=owner_effects(b,old,state)
        require(not records(state,b,INTENT),'Owner material revision intent consumed; no replay')
        prepared=records(state,b,PREPARED);require(bool(prepared) or not require_prepared,'Distinct owner-material foreground scope required')
        if prepared:require(prepared[0]['origin']=='FOREGROUND_CONTROLLING_TTY' and prepared[0]['text']==foreground_line(b),'Owner material scope differs')
    controller=Path(controller).resolve();target=FileBinding(**b['config']).json();home=Path(target['home']);runtime=target['settings']['state_dir']
    require(str(controller.parent)==b['target_root'] and identity(tree(controller.parent))==b['target_source'] and b['target_source']!=old['target_source'] and
            identity(tree(controller))==b['controller_hash'],'Exact new owner-material source required')
    require(home.is_absolute() and home.resolve()==home and home.is_relative_to(case.home) and home!=Path(prior_cfg['home']) and
            not os.path.lexists(home) and Path(runtime).parent==home and Path(runtime).name=='r','Unused owner-material destination required')
    expected=json.loads(json.dumps(prior_cfg));expected.update(home=str(home),controller=str(controller));expected['settings']['state_dir']=runtime
    expected['workflow'].update(notes=str(home/'notes'),authorized_repositories=[str(home/'fixtures/source')])
    expected['roles']={r:dict(workspace=str(home/'slots'/r/'workspace'),inputs=str(home/'slots'/r/'inputs')) for r in ('thinker','doer','reviewer')}
    require(target==expected,'Owner-material config cannot broaden scope or change limits')
    settings=Settings(**target['settings']);require(Path(settings.auth_file).is_file() and digest(Path(settings.executable()).read_bytes())==settings.binary_sha256,
        'Pinned executable/auth mount unavailable');require(len(os.fsencode(Path(runtime)/'reviewer.sock'))<108,'Native socket path too long')
    material,index=load_materials(b)
    prior_material={r['name']:FileBinding(r['path'],r['sha256']).read() for r in old['materials'] if not r['name'].startswith('current-context/')}
    require(all(material.get(n)==raw for n,raw in prior_material.items() if n!='successor-request.json'),'Historical original was changed or omitted')
    require(b['request']['human_answers']==old['request']['human_answers'] and 'lineage' not in b['request'],'Captured answers changed')
    owner=str(uuid.uuid5(uuid.NAMESPACE_URL,'capri-owner-material:'+condition(b)))
    require(index['binding'].get('owner')==owner and index['binding'].get('repo_source_hash')==b['target_source'] and
        index['binding'].get('controller_source_hash')==b['target_source'] and index['binding'].get('scope_hash')==digest(b['request']['text'].encode()),'Current owner context differs')
    from .native_packet import source_delivery,verify_source_materials
    selected=source_delivery(index['binding'],index['originals']);require(selected is not None,'Explicit current source delivery required')
    verify_source_materials(material,index)
    return dict(status='OWNER_MATERIAL_LAUNCH_CHECKED' if prepared else 'OWNER_MATERIAL_NEEDS_FOREGROUND',binding_hash=identity(b),
        owner=owner,home=str(home),runtime=runtime,original_repo=str(home/'fixtures/source'),source=b['target_source'],controller=b['controller_hash'],
        proof=proof,prepared_event=prepared[0]['event'] if prepared else None,model_dispatch='NOT_STARTED')


def prepare(store,config,b,controller,text):
    with store.lock('native-startup'),store.lock('native-writer'),store.transaction():
        plan=check(config,b,controller,view=store,require_prepared=False);require(plan['prepared_event'] is None,'Owner revision already prepared')
        require(text==foreground_line(b),'Exact owner-material foreground scope required')
        seq=store.event(None,PREPARED,dict(prior_intent=b['intent_event'],binding_hash=identity(b),text=text,origin='FOREGROUND_CONTROLLING_TTY',
            proof=plan['proof'],source=b['target_source'],new_dispatch='NOT_AUTHORIZED'))
        return dict(status='OWNER_MATERIAL_PREPARED',event=seq,source=b['target_source'],model_dispatch='NOT_STARTED')


def launch(config,b,controller,args):
    from .store import Store
    check(config,b,controller);store=Store(config['home'])
    try:
        with store.lock('native-qualification'):
            with store.lock('native-startup'),store.lock('native-writer'),store.transaction():
                plan=check(config,b,controller,view=store)
                seq=store.event(None,INTENT,dict(prior_intent=b['intent_event'],binding_hash=identity(b),source=b['target_source'],prepared_event=plan['prepared_event'],home=plan['home'],replay='FORBIDDEN'))
            try:
                create_source(SimpleNamespace(target_root=b['target_root'],target_source=b['target_source']),plan)
                target=FileBinding(**b['config']).json()
                for spec in target['roles'].values():
                    for path in spec.values():Path(path).mkdir(parents=True,exist_ok=True)
                old=FileBinding(**b['base']).json();legacy=FileBinding(**old['base']).json();case=StoppedCompaction.parse(FileBinding(**legacy['case']).json())
                material,_=load_materials(b)
                session=dict(operation='owner-material-'+condition(b),owner=plan['owner'],source_hash=b['target_source'],controller_hash=b['controller_hash'],
                    config_hash=identity(target),predecessor_receipt=case.prepared.json()['binding']['predecessor_receipt'],fresh_qualification=True,
                    workspace=str(Path(plan['home'])/'snapshots/thinker'),inputs=str(Path(plan['home'])/'inputs/thinker'),registry=b['registry'],
                    context_packet=b['context_packet'],required_requirements=json.loads(material['preserved-requirements.json']),verify_visible_clients=True)
                def revalidate():
                    owner_effects(b,old,store);require(identity(tree(Path(controller).parent))==b['target_source'] and FileBinding(**b['config']).json()==target,'Owner-material source/config drift')
                    require(len(records(store,b,INTENT))==1,'Committed owner revision intent missing')
                return run_session(target,args,controller,dict(binding=session,scope_text=b['request']['text'],admission_event=seq),plan,session,material,b['request'],revalidate)
            except BaseException as ex:
                with store.transaction():store.event(None,'NATIVE_OWNER_MATERIAL_HELD',dict(prior_intent=b['intent_event'],binding_hash=identity(b),admission_event=seq,error_type=type(ex).__name__,retry='FORBIDDEN'))
                raise
    finally:store.close()


def run_cli(config,args,controller):
    require(args.binding is not None,'Exact owner-material binding required');b=parse(json.loads(args.binding.read_text()));plan=check(config,b,controller,require_prepared=False)
    if args.check or args.command=='inspect-owner-material':print(json.dumps(plan),flush=True);return
    if args.command=='launch-owner-material':require(not args.headless,'Three visible native clients required');return launch(config,b,controller,args)
    require(plan['prepared_event'] is None,'Owner-material scope already prepared; do not repeat input')
    from .cli import require_human_tty
    with require_human_tty() as tty:
        tty.write('New source/material condition; prior completed hold is preserved.\nType exactly:\n'+foreground_line(b)+'\n> ');tty.flush();text=tty.readline().strip()
    from .store import Store
    store=Store(config['home'])
    try:print(json.dumps(prepare(store,config,b,controller,text)),flush=True)
    finally:store.close()
