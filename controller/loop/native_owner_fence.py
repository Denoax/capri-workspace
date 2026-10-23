"""Fence the reviewed, stopped, read-only stabilization intake before any task.

This is deliberately a narrow recovery profile. The missing thirteenth receive
record is retained as a gap. No general unknown/write attempt can use this route.
Existing Store events are authority; receipt files are reproducible projections.
"""
import contextlib
import json
import os
from pathlib import Path
import re

from .adapter import process_identity
from .cli import require_human_tty
from .native_startup import ReadOnlyState, checked_file
from .store import Store
from .util import Rejected, NeedsInput, atomic, digest, identity, tree

REVIEWED = dict(
    receipt='af3798bda55221e49d91456fa8e3d5b42547e2c61f52674d76cd1f3c016527ad',
    source='968d4787df0812bb41e02dd10cc58c97f637aae7c1c2b8c97cde93e76644d142',
    captures=['a104ce797c957c70164e7141fa5c2795818ab039d15679481e51d9889dd8a342',
              '2c4f272e18974ebc8f34e0d4f5f6d0485095fd5b4271e32ba8d8a733383aa1ab'],
    claim=194, scope=198, cutoff=213)


def recorded(view, binding):
    rows=view.db.execute("SELECT seq,data FROM events WHERE kind='NATIVE_OWNER_INTAKE_FENCED' ORDER BY seq").fetchall()
    matches=[]
    for row in rows:
        data=json.loads(row['data'])
        if data['operation']==binding['operation']:
            if data['binding_hash']!=identity(binding):
                raise Rejected('Owner fence operation key reused with changed parameters')
            matches.append((row['seq'],data))
    if len(matches)>1:
        raise Rejected('Conflicting owner fence events')
    return matches[0] if matches else None


def result(seq, data):
    return dict(status='FENCED_OWNER_INTAKE',operation=data['operation'],event=seq,
        owner=data['owner'],binding_hash=data['binding_hash'],old_claim='STILL_CONSUMED',
        old_abort='PRESERVED',new_dispatch='NOT_AUTHORIZED',
        receipt_gap='LOST_THIRTEENTH_START_NOT_RECONSTRUCTED')


def inspect(config, binding, controller, *, view=None, revalidate=False, _profile=None):
    profile=REVIEWED if _profile is None else _profile  # Synthetic fixture only; CLI has no override.
    if (binding.get('schema')!=1 or binding.get('route')!='NATIVE_OWNER_INTAKE_FENCE'
            or not re.fullmatch(r'[a-z0-9-]{1,64}',binding.get('operation',''))):
        raise Rejected('Exact owner-intake fence binding required')
    controller=Path(controller).resolve()
    if (str(controller)!=config['controller'] or identity(tree(controller))!=binding['controller_hash']
            or identity(tree(controller.parent))!=binding['source_hash'] or identity(config)!=binding['config_hash']):
        raise Rejected('Fence implementation/configuration identity changed')
    home=Path(config['home']).resolve()
    with (ReadOnlyState(home) if view is None else contextlib.nullcontext(view)) as state:
        prior=recorded(state,binding)
        if prior and not revalidate:return dict(recorded=result(*prior))
        old_raw=checked_file(binding['native_receipt']).read_bytes()
        if digest(old_raw)!=profile['receipt']:
            raise Rejected('Only the reviewed native scope receipt can use this fence')
        old=json.loads(old_raw);old_binding=old['binding'];owner=binding['owner']
        if (old_binding['owner']!=owner or old_binding['home']!=str(home)
                or old_binding['source_hash']!=profile['source'] or old['scope_event']!=profile['scope']):
            raise Rejected('Reviewed owner/source/scope lineage differs')
        if identity(tree(old_binding['controller']))!=old_binding['controller_hash'] or identity(tree(Path(old_binding['controller']).parent))!=profile['source']:
            raise Rejected('Preserved controller/source drift')
        checked_file(old_binding['predecessor_receipt'])
        old_config=json.loads(checked_file(binding['prior_config']).read_text())
        if identity(old_config)!=old_binding['config_hash']:
            raise Rejected('Actual prior configuration differs')
        if old_config['settings']['model']!='gpt-6.1-sol' or old_config['settings']['efforts']!={'thinker':'medium','doer':'medium','reviewer':'high'}:
            raise Rejected('Unreviewed prior role/model profile')
        state.require_current(owner)
        if state.db.execute('SELECT id FROM tasks WHERE owner=?',(owner,)).fetchone():
            raise Rejected('Owner has a task; use its task-specific recovery')
        if state.db.execute("SELECT id FROM human_inputs WHERE owner=? AND status='PENDING'",(owner,)).fetchone() or state.questions(owner,blocking=True):
            raise NeedsInput('Pending bound human input/question requires the existing core answer route')
        if state.db.execute('SELECT token_hash FROM capabilities WHERE owner=? AND enabled=1',(owner,)).fetchone():
            raise Rejected('Owner capability remains active')
        events=[dict(r) for r in state.db.execute('SELECT seq,kind,data FROM events WHERE seq>=? AND seq<=? ORDER BY seq',
            (profile['claim'],profile['cutoff']))]
        for row in events:row['data']=json.loads(row['data'])
        if identity(events)!=binding['events_hash']:
            raise Rejected('Claim/scope/launch/failure event lineage changed')
        claim=next((r for r in events if r['seq']==profile['claim']),None)
        scope=next((r for r in events if r['seq']==profile['scope']),None)
        if (not claim or claim['kind']!='RECONTRACT_THINKER_INTENT' or claim['data'].get('owner')!=owner
                or not scope or scope['kind']!='NATIVE_STARTUP' or scope['data']['milestone']!='SCOPE_CAPTURED'
                or scope['data']['details']['origin']!='FOREGROUND_CONTROLLING_TTY'
                or scope['data']['details']['text']!=old['scope_text']):
            raise Rejected('Genuine scope/consumed claim differs')
        startup=[r for r in events if r['kind']=='NATIVE_STARTUP' and r['data']['operation']==old_binding['operation']]
        if (not startup or startup[0]['data']['parameters']!=old_binding
                or startup[-1]['data']['milestone']!='FAILED_OR_UNCERTAIN'
                or startup[-1]['data']['details']!=dict(classification='EXECUTION_REQUIRES_RECONCILIATION',
                    error='Native turn exceeded exposed tool budget',last_proved='WORK_DISPATCH_INTENT',task=None)):
            raise Rejected('Not the reviewed stopped intake abort')
        dispatch=[r for r in events if r['kind']=='NATIVE_OWNER_DISPATCH' and r['data'].get('owner')==owner]
        if len(dispatch)!=2 or [r['data'].get('probe') for r in dispatch]!=[True,False]:
            raise Rejected('Unexpected owner turn count')
        later=state.db.execute("SELECT kind,data FROM events WHERE seq>?",(profile['cutoff'],)).fetchall()
        for row in later:
            data=json.loads(row['data'])
            if (row['kind']=='NATIVE_OWNER_INTAKE_FENCED' and data.get('operation')==binding['operation']
                    and data.get('binding_hash')==identity(binding)):
                continue
            if data.get('owner')==owner or data.get('operation')==old_binding['operation']:
                raise Rejected('Additional owner effects require their own reconciliation')
        rows=json.loads(checked_file(binding['registry']).read_text())
        slots=next(r['data']['details']['registry'] for r in startup if r['data']['milestone']=='SLOTS_CREATED')
        if set(rows)!=set(slots) or set(rows)!={'thinker','doer','reviewer'}:
            raise Rejected('Three-role registry differs')
        for role,row in rows.items():
            for key in ('pid','process_identity','thread','generation','phase','model','effort','endpoint'):
                if row.get(key)!=slots[role].get(key):raise Rejected('Role/generation identity drift')
            if row['phase']!='read' or process_identity(row['pid']) is not None or os.path.lexists(Path(row['endpoint'].removeprefix('unix://'))):
                raise Rejected('Role is writable, live, PID-reused or has an endpoint')
        supervisor=json.loads(checked_file(binding['supervisor']).read_text())
        if process_identity(supervisor['pid']) is not None:
            raise Rejected('Supervisor is live or its PID was reused')
        for spec in binding.get('terminal_records',[]):
            terminal=json.loads(checked_file(spec).read_text())
            if any(process_identity(row['pid']) is not None for row in terminal.values()):
                raise Rejected('Native terminal client/server is live or PID-reused')
        for endpoint in binding['absent_endpoints']:
            if os.path.lexists(endpoint):raise Rejected('Owned endpoint remains active')
        if binding.get('stale_terminal_socket'):
            from .native import NativeTerminals
            terminal=NativeTerminals.__new__(NativeTerminals)
            terminal.socket=Path(binding['stale_terminal_socket']['path']);terminal.root=terminal.socket.parent
            proof=terminal.inspect_stale_socket()
            if proof['socket_identity']!=binding['stale_terminal_socket']['identity']:
                raise Rejected('Retained stopped terminal socket identity changed')
        owner_record=json.loads(checked_file(binding['owner_binding']).read_text())
        if (owner_record['owner']!=owner or owner_record['workspace']!=old_binding['workspace']
                or owner_record['source_hash']!=identity(tree(owner_record['scope']['repo']))
                or tree(old_binding['workspace'])!=tree(owner_record['scope']['repo'])
                or tree(old_binding['inputs'])!=owner_record['inputs']):
            raise Rejected('Unknown source/input/write effect')
        if owner_record['scope']['request']['native_maintenance']['sha256']!=profile['receipt']:
            raise Rejected('Owner scope does not bind the genuine native receipt')
        ledger=json.loads(checked_file(binding['owner_context']).read_text())
        if identity(ledger['state'])!=ledger['sha256'] or ledger['state']['identity']['thread']!=rows['thinker']['thread']:
            raise Rejected('Old context/counter identity differs')
        for number,row in enumerate(dispatch):
            capture=Path(row['data']['capture'])/'events.jsonl'
            if digest(capture.read_bytes())!=profile['captures'][number]:
                raise Rejected('Unreviewed/unknown capture or tool effects')
        return dict(owner=owner,old_operation=old_binding['operation'],old_claim_seq=profile['claim'],
            scope_event=profile['scope'],aborted_turn=ledger['state']['identity']['turn'],
            registry_hash=binding['registry']['sha256'],old_context_hash=binding['owner_context']['sha256'],
            observed_completed_tools=12,source_unchanged=True,old_processes_stopped=True,
            retained_terminal_socket='EXACT_OWNED_NON_LISTENER' if binding.get('stale_terminal_socket') else 'ABSENT',
            receipt_gap='LOST_THIRTEENTH_START_NOT_RECONSTRUCTED',
            classification='REVIEWED_READ_ONLY_STOPPED_EFFECTS; FENCE_ONLY_NO_DISPATCH')


def fence(config, binding, controller, *, check_only=False):
    plan=inspect(config,binding,controller,revalidate=check_only)
    if check_only:return dict(status='OWNER_INTAKE_FENCE_CHECKED',plan=plan,model_dispatch='NOT_STARTED')
    if not plan.get('recorded'):
        line='fence '+binding['operation']+' '+identity(binding)
        with require_human_tty() as tty:
            tty.write('Fence the reviewed stopped intake only; no new admission or model.\nType exactly:\n'+line+'\n> ')
            tty.flush()
            if tty.readline().strip()!=line:raise Rejected('Exact owner fence confirmation did not match')
    state=Store(config['home'])
    try:
        with state.lock('native-startup'),state.lock('native-writer'):
            with state.transaction():
                plan=inspect(config,binding,controller,view=state)
                prior=recorded(state,binding)
                if not prior:
                    data=dict(operation=binding['operation'],owner=binding['owner'],binding_hash=identity(binding),
                              binding=binding,inspection=plan,origin='FOREGROUND_CONTROLLING_TTY',new_dispatch='NOT_AUTHORIZED')
                    seq=state.event(None,'NATIVE_OWNER_INTAKE_FENCED',data)
                    prior=(seq,data)
            answer=result(*prior)
            path=Path(config['home'])/'inputs/native-owner-fences'/binding['operation']/'receipt.json'
            atomic(path,json.dumps(answer,sort_keys=True)+'\n',exclusive=True)
            return dict(**answer,receipt=str(path),receipt_sha256=digest(path.read_bytes()))
    finally:
        state.close()
