"""Prove a maintenance precondition rejection with no subsequent model turn.

This second bounded profile preserves the old uncertainty record. It requires
the preceding complete source-bound restart and independently checks all public
turns, checkpoints, received-frame outcomes and retired runtime ownership.
"""
from dataclasses import asdict
import json
import math
import os
import shlex
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import zipfile

from .context import Checkpoint, Policy
from .native_read_recovery import (BINDING_KEYS, KINDS, ROUTE, require, path_checked,
    file_checked, event, authority_records, checkpoint_projection, capture_proof,
    retired_terminals, projection, confirmation, check_service_lock)
from .native_startup import ReadOnlyState, StartupJournal
from .adapter import process_identity
from .util import Rejected, digest, identity, tree


KEYS = BINDING_KEYS | {'resume_event','maintenance_request','context_ledger','operator_key'}


def frame_history(root, role, row, cutoff, allowed_turns):
    path=path_checked(root/role/str(row['generation'])/'received-frames.jsonl',root)
    received,done,turns={},set(),[]
    for line in path.read_text().splitlines():
        value=json.loads(line);seq=value['sequence']
        if value['phase']=='RECEIVED':
            require(seq not in received and value['role']==role and value['generation']==row['generation'],
                'Frame receipt role/generation/order differs')
            envelope=value['envelope'];require(not envelope.get('malformed'),'Malformed received frame')
            method=envelope.get('method')
            if method in ('turn/started','turn/completed','item/started','item/completed'):
                require(value['time']<cutoff,'A new model/tool effect followed the maintenance intent')
            if method=='turn/started':
                turns.append(envelope['turn']['id'])
            received[seq]=envelope
        else:
            require(value['phase']=='VALIDATED' and seq in received and seq not in done,
                'Missing/rejected frame validation')
            done.add(seq)
    require(received and set(received)==done and turns==allowed_turns,
        'Unaccounted model turns or incomplete received-frame evidence')
    return dict(path=str(path),sha256=digest(path.read_bytes()),turns=turns,
        frames=len(received),model_turns_after_intent=0)


def inspect_precondition(config,binding,controller,*,view=None):
    require(set(binding)==KEYS and type(binding['schema']) is int and binding['schema']==2,
        'Exact no-dispatch maintenance recovery binding required')
    controller=path_checked(controller)
    require(config.get('controller')==str(controller) and identity(config)==binding['config_hash']
        and identity(tree(controller))==binding['controller_hash']
        and identity(tree(controller.parent))==binding['source_hash'],'Corrected maintenance source/config differs')
    file_checked(binding['approval'])
    old_config=json.loads(file_checked(binding['parent_config']).read_text())
    require(config==dict(old_config,controller=str(controller)),
        'Maintenance recovery cannot change model/settings/workflow/roles/home')
    home,root=path_checked(config['home']),path_checked(config['settings']['state_dir'])
    parent=json.loads(file_checked(binding['parent_receipt'],home).read_text())
    require(parent.get('route')==ROUTE,'The preceding committed source-bound recovery is required')
    old_binding=parent['maintenance_binding'];old_controller=path_checked(old_config['controller'])
    require(identity(old_config)==old_binding['config_hash']
        and identity(tree(old_controller))==old_binding['controller_hash']
        and identity(tree(old_controller.parent))==old_binding['source_hash'],'Preserved running source/config changed')
    before,after=tree(old_controller.parent),tree(controller.parent)
    changed={n for n in before.keys()|after.keys() if before.get(n)!=after.get(n)}
    allowed={'controller/loop/native_operator.py','controller/loop/native_read_recovery.py',
        'controller/loop/native_maintenance_recovery.py','docs/COMPLETED_READ_RECOVERY.md'}
    require(changed and all(n in after and (n in allowed or n.startswith('controller/tests/test_')
        and n.endswith('.py')) for n in changed),'Maintenance repair exceeds its bounded parent recovery seam')
    if view is None:
        with ReadOnlyState(home) as reader:
            return inspect_precondition(config,binding,controller,view=reader)
    previous=parent['completed_read_recovery']
    admitted=event(view,previous['admission_event'],KINDS[1])
    reconciled=event(view,admitted['reconciliation_event'],KINDS[0])
    require(admitted['binding']==previous['binding']
        and admitted['origin']=='FOREGROUND_CONTROLLING_TTY'
        and admitted['parameters_hash']==identity(admitted['binding'])
        and admitted['proof_hash']==identity(admitted['proof'])==reconciled['proof_hash']==identity(reconciled['proof'])
        and admitted['parent_key']==reconciled['parent_key']==admitted['proof']['parent_key']
        and admitted['parameters_hash']==reconciled['parameters_hash']
        and parent==projection(home,dict(seq=previous['admission_event'],data=admitted))
        and admitted['text']==confirmation(admitted['binding'],dict(
            parent_key=admitted['parent_key'],proof_hash=admitted['proof_hash'])),
        'Preceding recovery lacks exact committed authority')
    history=StartupJournal(view,old_binding['operation'],old_binding).records()
    require([r['milestone'] for r in history]==['RUNTIME_RESUME_INTENT','RUNTIME_RESUMED',
        'MAINTENANCE_INTENT','MAINTENANCE_UNCERTAIN'],'Not the bounded post-restart maintenance failure')
    started,resumed,intent,failure=history
    require(started['details']['receipt_sha256']==binding['parent_receipt']['sha256']
        and resumed['seq']==binding['resume_event'] and intent['seq']==binding['intent_event']
        and failure['seq']==binding['failure_event'],'Maintenance parent events differ')
    key=identity(dict(parent_receipt_sha256=binding['parent_receipt']['sha256'],
        intent_event=intent['seq'],failure_event=failure['seq']))
    records=authority_records(view,key,binding)
    view.require_current(parent['owner']);task=view.task(parent['task'])
    require(task['owner']==parent['owner'] and task['state']=='CANDIDATE_SEALED'
        and task['version']==parent['task_version'] and task['content_hash']==parent['packet_hash']
        and identity(task['packet'])==task['content_hash']
        and tree(task['candidate'])==parent['source_before_stop']
        and json.loads(task['seal'])['source_hash']==identity(parent['source_before_stop']),
        'Sealed task/owner/packet/candidate changed')
    require(not view.db.execute('SELECT 1 FROM capabilities WHERE owner=? AND enabled=1',(parent['owner'],)).fetchone()
        and not view.db.execute("SELECT 1 FROM attempts WHERE task=? AND status IN ('SPAWN_INTENT','RUNNING','DISPATCH_UNCERTAIN')",(task['id'],)).fetchone()
        and not view.db.execute('SELECT 1 FROM decisions WHERE task=?',(task['id'],)).fetchone(),
        'An active writer/capability/decision conflicts with recovery')
    require(file_checked(binding['registry'],root)==root/'registry.json'
        and file_checked(binding['supervisor'],root)==root/'supervisor.json', 'Stopped registry/supervisor is misplaced')
    raw=(root/'registry.json').read_bytes();registry=json.loads(raw)
    require(registry==resumed['details']['roles'] and set(registry)=={'thinker','doer','reviewer'},
        'Registry differs from the completed restart')
    supervisor=json.loads((root/'supervisor.json').read_text())
    require(process_identity(supervisor['pid']) is None and supervisor['source']==old_binding['source_hash']
        and supervisor['maintenance_operation']==old_binding['operation'],'Supervisor ownership is unresolved')
    argv=bytes.fromhex(supervisor['cmdline_hex']).rstrip(b'\0').decode().split('\0')
    require(argv[1:]==[str(old_controller/'native_loopctl.py'),'--config',binding['parent_config']['path'],
        'resume-runtime','--prepared',binding['parent_receipt']['path'],
        '--prepared-sha256',binding['parent_receipt']['sha256']],'Failed supervisor command differs')
    require(file_checked(binding['operator_key'],root)==root/'operator.key'
        and not os.path.lexists(root/'operator.sock') and not os.path.lexists(home/'state/intake.sock'),
        'Operator/intake ownership remains unresolved')
    check_service_lock(home)
    request=json.loads(file_checked(binding['maintenance_request']).read_text())
    expected=dict(task=task['id'],version=task['version'],owner=task['owner'],packet_hash=task['content_hash'],
        source_hash=identity(parent['source_before_stop']),controller_hash=old_binding['controller_hash'],
        supervisor_pid=supervisor['pid'],supervisor_identity=supervisor['process_identity'],
        role='doer',thread=registry['doer']['thread'],role_generation=registry['doer']['generation'])
    require(request==expected and intent['details']['action']=='compact-role'
        and intent['details']['key']==identity(dict(action='compact-role',binding=request))
        and intent['details']['role']=='doer' and intent['details']['generation']==registry['doer']['generation']
        and failure['details']['key']==intent['details']['key'] and failure['details']['role']=='doer',
        'Maintenance request/intent does not match the readonly generation')
    cutoff_row=view.db.execute('SELECT time FROM events WHERE seq=?',(intent['seq'],)).fetchone()
    cutoff=cutoff_row['time']
    for role,row in registry.items():
        old=parent['registry'][role]
        require(row['generation']==old['generation']+1 and row['phase']=='read'
            and row.get('model')==old.get('model') and row.get('effort')==old.get('effort')
            and process_identity(row['pid']) is None and not os.path.lexists(root/(role+'.sock')),
            'Role process/phase/profile differs')
        if role=='reviewer':require(row['empty'] and old['empty'],'Reviewer is no longer unused')
        else:require(row['thread']==old['thread'],'Read-only restart changed a continuing thread')
        spec=parent['roles'][role]
        require(tree(path_checked(spec['workspace'],home))==spec['source']
            and tree(path_checked(spec['inputs'],home))==spec['input_files'],'Role source/inputs changed')
    require(set(binding['checkpoints'])=={'owner','doer','observed_owner','completed_doer'},
        'Original and completed checkpoint bindings required')
    for label,field in [('owner','owner_checkpoint'),('doer','doer_checkpoint')]:
        require(file_checked(binding['checkpoints'][label],home)==Path(parent[field]), 'Original checkpoint path differs')
    owner_original=json.loads(Path(parent['owner_checkpoint']).read_text())
    # The qualified restart uses this authority-derived filename, preserving the
    # earlier failed-restart checkpoint rather than overwriting its shared name.
    from .native_read_recovery import observed_authority
    owner_authority,_=observed_authority(owner_original,parent['registry']['thinker'],registry['thinker'])
    owner_target=Path(parent['owner_checkpoint']).parent/('controller-restart-owner-'+identity(owner_authority)+'.json')
    owner_cp=checkpoint_projection(home,parent['owner_checkpoint'],parent['registry']['thinker'],registry['thinker'],owner_target)
    require(binding['checkpoints']['observed_owner']==dict(path=owner_cp['path'],sha256=owner_cp['sha256'])
        and file_checked(binding['checkpoints']['observed_owner'],home),'Completed owner checkpoint differs')
    doer_path=file_checked(binding['checkpoints']['completed_doer'],home)
    require(doer_path.parent==Path(parent['doer_checkpoint']).parent and doer_path.name.startswith('derived-'),
        'Completed Doer checkpoint is misplaced')
    doer_cp=checkpoint_projection(home,parent['doer_checkpoint'],parent['registry']['doer'],registry['doer'],doer_path)
    require(binding['checkpoints']['completed_doer']['sha256']==doer_cp['sha256'], 'Completed Doer checkpoint differs')
    current_questions=dict(pending=view.questions(parent['owner'],blocking=True),answers=view.human_answers(parent['owner']))
    require(owner_cp['authority']['questions_answers']==current_questions
        and doer_cp['authority']['questions_answers']==current_questions,'Original answers/questions changed')
    rows=[dict(r) for r in view.db.execute('SELECT * FROM events WHERE seq>? AND seq<? ORDER BY seq',
        (started['seq'],resumed['seq']))]
    require([r['kind'] for r in rows]==['NATIVE_CAPABILITY_STAGED_HELD','NATIVE_THINKER_REGISTERED',
        'NATIVE_THINKER_CAPABILITY_HELD','NATIVE_OWNER_DISPATCH','NATIVE_OWNER_DISPATCH',
        'RECOVERY_CHECKPOINT_DERIVED','READ_ONLY_PROBE_INTENT','REHYDRATION_INTENT','REHYDRATION_VALIDATED'],
        'Unexpected effects during the preceding restart')
    values=[json.loads(r['data']) for r in rows]
    require(all(v.get('owner')==parent['owner'] for v in values[:5])
        and values[3].get('probe') is True and values[4].get('probe') is False
        and values[5]['derived_sha256']==doer_cp['state_sha256']
        and values[7]['checkpoint']==values[8]['checkpoint']==doer_cp['state_sha256']
        and values[7]['capture']==values[8]['capture'], 'Completed restart lineage/reread proof differs')
    labels={'probe':values[3],'read':values[4],'doer_probe':values[6],'doer_read':values[7]}
    require(set(binding['captures'])==set(labels),'All four completed role captures required')
    with zipfile.ZipFile(file_checked(binding['review'])) as archive:
        manifest=json.loads(archive.read('MANIFEST.json'))['files']
        for label,entry in labels.items():
            name='actual-native/'+label+'-capture-reference.json';data=archive.read(name)
            require(digest(data)==manifest[name]['sha256'],'Frozen capture reference changed')
            ref=json.loads(data)
            require(binding['captures'][label]==dict(path=ref['original_path'],sha256=ref['original_sha256'])
                and Path(ref['original_path'])==path_checked(entry['capture'],home)/'events.jsonl',
                'Capture is not the frozen committed original')
    from .native import rehydration_payload, grade_original_reads
    from .native_packet import load, read_guide, read_commands, grade_reads, feasibility
    folder=Path(parent['roles']['thinker']['inputs'])/'current-context';packet=load(folder)
    originals={'/inputs/current-context/'+s['name']:s['sha256'] for s in packet['sections']}
    expected_owner=dict(owner=parent['owner'],checkpoint=owner_cp['state_sha256'],originals=originals)
    paths={label:file_checked(spec,home) for label,spec in binding['captures'].items()}
    probe=capture_proof(paths['probe'],registry['thinker'],'No tools. Final exactly READY.',lambda text:text=='READY')
    read=capture_proof(paths['read'],registry['thinker'],read_guide(packet)+'\nReturn exactly '+json.dumps(expected_owner),
        lambda text:json.loads(text)==expected_owner,read_commands(packet))
    require(grade_reads(paths['read'].parent,folder,runtime=root/'thinker/runtime',
        thread=registry['thinker']['thread'],turn=read['turn']), 'Completed owner sections are not model-visible')
    doer_expected=dict(packet_hash=task['content_hash'],source_hash=identity(parent['source_before_stop']),
        requirements_hash=task['packet']['requirements_hash'],thread=registry['doer']['thread'],
        role_generation=registry['doer']['generation'],task_generation=task['generation'])
    prompt='First send commentary ACK:'+task['content_hash']+'\nRead-only telemetry probe. Use no tools. Then final answer must be only this exact JSON: '+json.dumps(doer_expected)
    doer_probe=capture_proof(paths['doer_probe'],registry['doer'],prompt,
        lambda text:json.loads(text)==doer_expected,role='doer')
    backend=SimpleNamespace(inputs=Path(parent['roles']['doer']['inputs']),workspace=Path(parent['roles']['doer']['workspace']))
    payload,expected_doer,doer_originals=rehydration_payload(task,backend,doer_cp['authority'],doer_cp['state_sha256'])
    from .native import original_read_command
    # The retained successful turn also reread this exact bounded packet slice.
    # This is a literal immutable-input read, not a generic shell/read whitelist.
    packet_slice = shlex.join(['python3','-c',
        'import pathlib; print(pathlib.Path("/inputs/packet.json").read_text()[10000:27000])'])
    marker='Final answer must equal this JSON after checking the originals: '
    prefix=payload[0]['text'].rsplit(marker,1)[0]+marker
    def exact_original_prompt(text):
        return (isinstance(text,str) and text.startswith(prefix)
            and identity(json.loads(text[len(prefix):]))==identity(expected_doer))
    doer_read=capture_proof(paths['doer_read'],registry['doer'],exact_original_prompt,
        lambda text:identity(json.loads(text))==identity(expected_doer),original_read_command(doer_originals),role='doer',
        optional_commands=[packet_slice])
    require(grade_original_reads(paths['doer_read'].parent,doer_originals), 'Doer original reads were not completed')
    start_time=datetime.fromisoformat(view.db.execute('SELECT time FROM events WHERE seq=?',(started['seq'],)).fetchone()['time']).timestamp()
    end_time=datetime.fromisoformat(view.db.execute('SELECT time FROM events WHERE seq=?',(resumed['seq'],)).fetchone()['time']).timestamp()
    require(all(start_time<=value['start']<=value['end']<=end_time
        for value in [probe,read,doer_probe,doer_read]),'Capture is outside its committed restart interval')
    require(probe['end']<=read['start'] and read['end']-probe['start']<=240
        and doer_probe['end']<=doer_read['start'] and doer_read['end']-doer_probe['start']<=240,
        'Original combined-stage order/budgets differ')
    ledger=file_checked(binding['context_ledger'],root)
    require(ledger==root/'doer/tasks'/digest(task['id'].encode())/'context-ledger.json','Doer ledger is misplaced')
    saved=json.loads(ledger.read_text());state=saved['state']
    observed=state['reading']['observed_at'];intent_time=datetime.fromisoformat(cutoff).timestamp()
    require(saved['sha256']==identity(state) and not state['rehydrating'] and not state['restart'] and not state['compaction']
        and state['identity']['thread']==registry['doer']['thread']
        and state['identity']['role_generation']==registry['doer']['generation']
        and state['identity']['turn']==doer_read['turn']
        and state['identity']['role']=='doer' and state['identity']['task']==task['id']
        and state['identity']['revision']==task['revision'] and state['identity']['task_generation']==task['generation']
        and state['identity']['model']==config['settings']['model']
        and state['identity']['server']==str(registry['doer']['pid'])+':'+registry['doer']['process_identity']
        and state['identity']['process']==registry['doer']['process_identity']
        and state['identity']['producer']=='codex-cli/0.163.0'
        and state['identity']['schema']=='CLI_SCHEMA_PROFILE:d7bf28b381dacc32a837abd2c4829e9fe28f78e6c8e8380dff7112eb8d9d1b9f'
        and state['reading']['identity']==state['identity']
        and state['policy']==asdict(Policy(**config['settings']['context_policy'])) and math.isfinite(observed)
        and intent_time-observed>config['settings']['context_policy']['max_age'],
        'Not the observed stale-usage, pre-dispatch hold rejection')
    frame_proof={role:frame_history(root,role,row,cutoff,
        [probe['turn'],read['turn']] if role=='thinker' else
        [doer_probe['turn'],doer_read['turn']] if role=='doer' else []) for role,row in registry.items()}
    cleanup=0
    for row in view.db.execute('SELECT kind,data FROM events WHERE seq>? ORDER BY seq',(resumed['seq'],)):
        value=json.loads(row['data'])
        if row['kind']=='NATIVE_STARTUP':
            require(value.get('operation') in {old_binding['operation'],'completed-read-'+key}, 'Unrelated startup after completion')
        elif row['kind']=='NATIVE_CAPABILITY_REVOKED' and value.get('owner')==parent['owner']:cleanup+=1
        elif row['kind'] in KINDS:require(value.get('parent_key')==key,'Different successor authority')
        else:raise Rejected('Unexpected effect after the maintenance boundary')
    require(cleanup==1,'Exact stopped-capability cleanup required')
    prefix=[dict(r) for r in view.db.execute('SELECT * FROM events WHERE seq<=? ORDER BY seq',(failure['seq'],))]
    proof=dict(parent_key=key,parent_receipt=binding['parent_receipt'],old_source=old_binding['source_hash'],
        task=task['id'],owner=task['owner'],task_version=task['version'],packet_hash=task['content_hash'],
        candidate_source=identity(parent['source_before_stop']),registry_sha256=digest(raw),registry=registry,
        supervisor=binding['supervisor'],journal_prefix_sha256=identity(prefix),probe=probe,read=read,
        doer_probe=doer_probe,doer_read=doer_read,received_frames=frame_proof,
        retired_terminals=retired_terminals(root,registry),owner_checkpoint=owner_cp,observed_doer_checkpoint=doer_cp,
        changed_paths=sorted(changed),classification='READ_MAINTENANCE_PRECONDITION_REJECTION_NO_NEW_MODEL_TURN',
        rehydration_completed=True,writes_authorized=False,context_ledger=binding['context_ledger'],
        read_plan=feasibility(packet,task['packet'],checks=0,research=0,submission=0,finishing_seconds=0,research_seconds=0))
    require(all(r['data']['proof_hash']==identity(proof) for r in records.values()),'Committed maintenance proof differs')
    # The new operator has a new held scope. Never pretend its original key was
    # retained from the earlier restart's projection.
    parent=dict(parent,operator_key_sha256=binding['operator_key']['sha256'])
    return dict(parent=parent,registry=registry,registry_raw=raw,proof=proof,proof_hash=identity(proof),
        parent_key=key,records=records)
