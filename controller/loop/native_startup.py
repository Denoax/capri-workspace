"""Native-only maintenance admission; old core claims/receipts are immutable.

Checks use SQLite mode=ro, not Store initialization. Existing Store events are
sole authority. Receipt files are reproducible projections, never a second DB.
"""
from pathlib import Path
import json
import contextlib
import re
import os
import sqlite3
import shutil

from .adapter import process_identity
from .cli import require_human_tty
from .contract import source
from .store import Store
from .util import Rejected, atomic, digest, identity, safe_path, tree


class ReadOnlyState:
    task = Store.task
    require_current = Store.require_current
    questions = Store.questions
    recontract_receipt = Store.recontract_receipt
    human_answers = Store.human_answers

    def __init__(self, home):
        self.home = Path(home).resolve()
        self.db = sqlite3.connect((self.home/'state/workflow.sqlite3').as_uri()+'?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA query_only=ON')
        if self.db.execute('PRAGMA user_version').fetchone()[0] != 2:
            self.db.close()
            raise Rejected('Read-only startup requires the existing qualified Store schema')

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def checked_file(spec):
    path = Path(spec['path'])
    if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != spec['sha256']:
        raise Rejected('Startup material identity changed: '+str(path))
    return path


def owner_directory(root, owner):
    """Keep same-owner legacy history; never retire another owner's ledger."""
    root = Path(root)/'thinker'
    legacy = root/'owner-binding.json'
    if legacy.exists():
        if legacy.is_symlink():
            raise Rejected('Symlinked predecessor owner binding')
        value = json.loads(legacy.read_text())
        if not isinstance(value, dict) or not isinstance(value.get('owner'), str) or not value['owner']:
            raise Rejected('Unknown legacy owner attribution')
        if value['owner'] == owner:
            return root
    return root/'owners'/digest(owner.encode())


def check_owner_ledger(root, owner, frozen=None):
    folder = owner_directory(root, owner)
    binding, ledger = folder/'owner-binding.json', folder/'owner-context.json'
    if ledger.exists() and not binding.exists():
        raise Rejected('Interrupted owner creation has an unattributed context ledger')
    if binding.exists():
        if binding.is_symlink():
            raise Rejected('Symlinked owner binding')
        saved = json.loads(binding.read_text())
        if saved.get('owner') != owner or frozen is not None and saved != frozen:
            raise Rejected('Owner source/scope/input binding differs')
    if ledger.exists():
        saved = json.loads(ledger.read_text())
        if ledger.is_symlink() or saved.get('sha256') != identity(saved.get('state')):
            raise Rejected('Owner context ledger is corrupt')
        if saved['state']['identity']['task'] != 'owner:'+owner:
            raise Rejected('Owner ledger task identity differs')
    return dict(directory=str(folder), binding_sha256=digest(binding.read_bytes()) if binding.exists() else None,
                context_sha256=digest(ledger.read_bytes()) if ledger.exists() else None)


def restored_request(binding, receipt, receipt_path, receipt_sha256):
    from .native_lineage import PROJECTED_KEYS
    old=json.loads(checked_file(binding['predecessor_receipt']).read_text())
    lineage={key:old['prepared']['lineage'][key] for key in PROJECTED_KEYS}
    lineage['full_core_lineage']=dict(path=binding['predecessor_receipt']['path'],
        sha256=binding['predecessor_receipt']['sha256'],origin='ACTUAL_COMMITTED_CORE_FOREGROUND_RECONTRACT')
    return dict(text=receipt['scope_text'],origin='FOREGROUND_NATIVE_MAINTENANCE_SCOPE',lineage=lineage,
        corrections=[dict(text=receipt['scope_text'],origin='FOREGROUND_CONTROLLING_TTY',event=receipt['scope_event'])],
        native_maintenance=dict(receipt=str(Path(receipt_path).resolve()),sha256=receipt_sha256,
            scope_event=receipt['scope_event'],scope=receipt['scope_text']))


def packet_preflight(config,binding,scope,*,receipt=None,receipt_path=None,receipt_sha256=None):
    """Use the unchanged validator, then measure ALL Engine-added frozen fields."""
    from .engine import Engine
    from .contract import validate
    from .native_lineage import compact_native_request
    from .native_packet import load, feasibility, read_guide
    index=load(checked_file(binding['context_packet']).parent)
    path=receipt_path or Path(config['home'])/'inputs/native-maintenance'/binding['operation']/'prepared.json'
    # Preparation reserves a conservative event-number width. Actual admission
    # repeats this with the committed projection before recording launch intent.
    projected=receipt or dict(scope_text=scope,scope_event=9999999999999999)
    request=restored_request(binding,projected,path,receipt_sha256 or '0'*64)
    with ReadOnlyState(config['home']) as view:
        answers=request['lineage'].get('human_answers',[])+view.human_answers(binding['owner'])
    if answers:request['human_answers']=answers  # Same final augmentation as Engine.submit.
    if index['answers_hash']!=identity(answers):
        raise Rejected('Current-context bound answers are stale')
    proposal=json.loads(checked_file(binding['planned_proposal']).read_text())
    if proposal['requirements']!=json.loads(checked_file(binding['exact_requirements']).read_text()):
        raise Rejected('Planned proposal changed exact N01-N08 values')
    import copy
    proposal=copy.deepcopy(proposal)
    proposal['steps'][0]['goal']+='x'*800  # Maximum allowed sourced-research addition.
    old=json.loads(checked_file(binding['predecessor_receipt']).read_text())
    repo=old['prepared']['repo']
    engine=Engine.__new__(Engine);engine.config=config['workflow']
    frozen=validate(proposal,repo,compact_native_request(request),engine.instructions(repo))
    frozen.update(lineage=request['lineage'],task_revision=request['lineage']['revision'])
    payload=[dict(type='text',text=read_guide(index),text_elements=[])]
    if len(json.dumps(payload).encode())>60000:
        raise Rejected('Complete native current-context read payload exceeds byte budget')
    return feasibility(index,frozen)


def preflight(config, binding, controller, *, receipt=None, receipt_path=None, receipt_sha256=None):
    """Pure shared check before input, intent, snapshots, capabilities or slots."""
    if binding.get('schema_version') != 1 or binding.get('route') != 'NATIVE_MAINTENANCE_RECOVERY':
        raise Rejected('Exact native maintenance binding required')
    if not isinstance(binding.get('operation'), str) or not re.fullmatch(r'[a-z0-9-]{1,64}',binding['operation']):
        raise Rejected('Unsafe native operation identity')
    if identity(config) != binding['config_hash']:
        raise Rejected('Native maintenance configuration changed')
    controller = Path(controller).resolve()
    if str(controller) != binding['controller'] or config['controller'] != str(controller) or identity(tree(controller)) != binding['controller_hash']:
        raise Rejected('New controller identity changed')
    if identity(tree(controller.parent)) != binding['source_hash']:
        raise Rejected('New maintenance source changed')
    accounted_owner_fence = False
    if binding.get('owner_fence'):
        # A fence is never an admission. Recheck its exact stopped effects here
        # before asking for a distinct new source/scope, and again before intent.
        from .native_owner_fence import inspect as inspect_fence, recorded as recorded_fence
        fence_binding=json.loads(checked_file(binding['owner_fence']).read_text())
        if binding.get('generation_registry')!=fence_binding['registry'] or binding['owner']!=fence_binding['owner']:
            raise Rejected('New role generation lineage differs from the fenced registry')
        with ReadOnlyState(config['home']) as view:
            fenced=recorded_fence(view,fence_binding)
            if not fenced:raise Rejected('Reviewed owner intake must be fenced before new admission')
            inspect_fence(config,fence_binding,controller,view=view,revalidate=True)
        accounted_owner_fence=True
    from .settings import Settings
    settings = Settings(**config['settings'])
    if max(len(os.fsencode(Path(settings.state_dir)/name)) for name in ('thinker.sock','operator.sock','ui.sock'))>=108:
        raise Rejected('Native private socket path exceeds installed Unix limit')
    if not Path(settings.executable()).is_file() or digest(Path(settings.executable()).read_bytes()) != settings.binary_sha256:
        raise Rejected('Pinned executable mismatch')
    if not all(shutil.which(cmd) for cmd in ('bwrap','tmux')):
        raise Rejected('Native supported-host prerequisites unavailable')
    old = json.loads(checked_file(binding['predecessor_receipt']).read_text())
    old_controller = Path(binding['predecessor_controller'])
    if identity(tree(old_controller)) != old['binding']['controller_hash']:
        raise Rejected('Preserved predecessor controller changed')
    owner = old['prepared']['lineage']['successor_owner']
    if owner != binding['owner'] or old['binding']['home'] != config['home']:
        raise Rejected('Maintenance scope is not the existing prepared owner/home')
    registry_path = checked_file(binding['registry'])
    if str(registry_path) != old['binding']['registry']:
        raise Rejected('Stopped registry location differs')
    rows = json.loads(registry_path.read_text())
    if set(rows) != {'thinker','doer','reviewer'}:
        raise Rejected('Exact three stopped role records required')
    for role, row in rows.items():
        if process_identity(row['pid']) is not None or os.path.lexists(registry_path.parent/(role+'.sock')):
            raise Rejected('Old role process/endpoint is unresolved')
        if row.get('empty') is not True:
            raise Rejected('Legacy pre-model recovery cannot infer effects of an occupied thread')
    supervisor = registry_path.parent/'supervisor.json'
    if supervisor.exists() and process_identity(json.loads(supervisor.read_text())['pid']) is not None:
        raise Rejected('Old supervisor still exists')
    stopped = json.loads(checked_file(binding['stopped_launch']).read_text())
    if (stopped.get('model_turns') != 0 or stopped.get('prepared_owner') != owner or
            stopped.get('error') != 'Native Thinker scope/source/correction drift; explicit revision required'):
        raise Rejected('Stopped launch lacks accounted pre-probe rejection evidence')
    proved=stopped.get('role_slots',{})
    if set(proved)!=set(rows) or any(any(proved[role].get(key)!=row.get(key) for key in ('pid','thread','generation','empty')) for role,row in rows.items()):
        raise Rejected('Stopped launch role/generation proof differs from preserved registry')
    for item in binding['materials']:
        checked_file(item)
        safe_path('/material-root', item['name'])
    scope_path = checked_file(binding['scope'])
    scope = scope_path.read_text().rstrip('\r\n')
    if not scope or '\n' in scope:
        raise Rejected('Exactly one bound maintenance scope line required')
    if binding.get('context_packet'):
        from .native_packet import load
        index=load(checked_file(binding['context_packet']).parent)
        if (index['binding'].get('owner')!=owner or index['binding'].get('scope_hash')!=digest(scope.encode())
                or index['binding'].get('controller_source_hash')!=binding['source_hash']):
            raise Rejected('Prepared current-context scope/source differs')
        fit=packet_preflight(config,binding,scope,receipt=receipt,receipt_path=receipt_path,receipt_sha256=receipt_sha256)
    else:
        fit=None
    home = Path(config['home']).resolve()
    with ReadOnlyState(home) as store:
        store.require_current(owner)
        parent = store.task(old['prepared']['lineage']['parent_task'])
        if parent['state'] != 'SUPERSEDED' or store.recontract_receipt(parent['id']) != old['prepared']:
            raise Rejected('Old committed core receipt no longer matches')
        if identity(parent['packet']) != parent['content_hash'] or source(parent['packet']['source']['repo']) != parent['packet']['source']:
            raise Rejected('Original frozen source/packet drift')
        for item in parent['packet']['instructions']:
            checked_file(item)
        if identity(tree(parent['candidate'])) != old['binding']['candidate_hash']:
            raise Rejected('Preserved sealed candidate drift')
        claim = store.db.execute("SELECT seq,data FROM events WHERE task=? AND kind='RECONTRACT_THINKER_INTENT'", (parent['id'],)).fetchall()
        if len(claim) != 1 or claim[0]['seq'] != binding['claim_seq'] or json.loads(claim[0]['data']).get('owner') != owner:
            raise Rejected('Exact consumed predecessor claim required; never replay it')
        if store.db.execute('SELECT id FROM tasks WHERE owner=?',(owner,)).fetchone():
            raise Rejected('Existing task requires its own task recovery/report route')
        if store.db.execute('SELECT token_hash FROM capabilities WHERE owner=? AND enabled=1',(owner,)).fetchone():
            raise Rejected('Old capability remains enabled')
        for row in store.db.execute("SELECT kind,data FROM events WHERE seq>?", (binding['claim_seq'],)):
            data = json.loads(row['data'])
            if data.get('owner') == owner and row['kind'] in ('NATIVE_OWNER_DISPATCH','THINKER_TURN','NATIVE_STARTUP_PROBE_DISPATCH_INTENT') and not accounted_owner_fence:
                raise Rejected('Dispatched or uncertain owner turn requires effect reconciliation')
        other = store.db.execute("SELECT id FROM tasks WHERE state NOT IN ('SUPERSEDED','ACCEPTED','REJECTED','CANCELED')").fetchone()
        if other:
            raise Rejected('Existing task/human gate holds this home')
    for label, path in [('workspace',binding['workspace']), ('inputs',binding['inputs']), ('runtime',config['settings']['state_dir'])]:
        path = Path(path)
        if not path.is_absolute() or not path.resolve().is_relative_to(home):
            raise Rejected('Private startup destination outside bound home')
        if os.path.lexists(path):
            raise Rejected('Startup destination already exists; verify explicit recovery, never overwrite: '+label)
    old_owner = check_owner_ledger(registry_path.parent, owner)
    result = dict(schema_version=1, route=binding['route'], operation=binding['operation'], owner=owner,
                  binding_hash=identity(binding), config_hash=identity(config), source_hash=binding['source_hash'],
                  controller_hash=binding['controller_hash'], predecessor_receipt_sha256=binding['predecessor_receipt']['sha256'],
                  consumed_claim_seq=binding['claim_seq'], registry_sha256=binding['registry']['sha256'],
                  original_repo=old['prepared']['repo'], core_lineage_hash=identity(old['prepared']['lineage']), old_owner_ledger=old_owner,
                  scope=scope, classification=('FENCED_REVIEWED_OWNER_ABORT; NEW_SCOPE_REQUIRED' if accounted_owner_fence else 'ACCOUNTED_BEFORE_FIRST_PROBE; NEW_SCOPE_REQUIRED'),
                  model_dispatch='NOT_STARTED', legacy_service='NOT_STARTED',packet_feasibility=fit)
    return result


class StartupJournal:
    def __init__(self, store, operation, parameters):
        self.store, self.operation, self.parameters = store, operation, parameters
        self.parameter_hash = identity(parameters)

    def records(self):
        rows = self.store.db.execute("SELECT seq,data FROM events WHERE kind='NATIVE_STARTUP' ORDER BY seq").fetchall()
        result = []
        for row in rows:
            data = json.loads(row['data'])
            if data.get('operation') == self.operation:
                if data['parameters_hash'] != self.parameter_hash:
                    raise Rejected('Startup operation key reused with different parameters')
                result.append(dict(seq=row['seq'], **data))
        return result

    def append(self, milestone, details=None):
        with (contextlib.nullcontext() if self.store.db.in_transaction else self.store.transaction()):
            history = self.records()
            if milestone == 'LAUNCH_INTENT' and any(r['milestone']=='LAUNCH_INTENT' for r in history):
                raise Rejected('Launch intent consumed; explicit reconciliation required, no automatic retry')
            if milestone in ('PROBE_DISPATCH_INTENT','WORK_DISPATCH_INTENT') and any(r['milestone']==milestone for r in history):
                raise Rejected('External turn intent consumed; reconcile actual effects, never repeat')
            return self.store.event(None,'NATIVE_STARTUP',dict(operation=self.operation,parameters_hash=self.parameter_hash,
                parameters=self.parameters if not history else None, milestone=milestone, details=details or {}))


def prepare(config, binding, controller, *, check_only=False):
    # Read-only construction is intentional: Store.__init__ can migrate/hold tasks.
    with ReadOnlyState(config['home']) as view:
        prior = StartupJournal(view,binding['operation'],binding).records()
    if any(row['milestone']=='LAUNCH_INTENT' for row in prior):
        return dict(status='HELD_RECONCILIATION_REQUIRED',operation=binding['operation'],last_proved=prior[-1]['milestone'],model_dispatch='NOT_RETRIED')
    plan = preflight(config, binding, controller)
    if check_only:
        return dict(status='NATIVE_MAINTENANCE_CHECKED', plan=plan)
    if prior:
        scopes = [r for r in prior if r['milestone']=='SCOPE_CAPTURED']
        if not scopes:
            raise Rejected('Existing interrupted preparation is held for explicit reconciliation')
        entered = scopes[0]['details']['text']
    else:
        with require_human_tty() as tty:
            tty.write('New native maintenance scope; old core claim stays consumed.\n'
                      'New source '+binding['source_hash']+'\nPaste the bound single-line scope:\n> ')
            tty.flush()
            entered = tty.readline().rstrip('\r\n')
        if entered.rstrip(' \t') != plan['scope']:
            raise Rejected('Maintenance scope did not match; no authority recorded')
    store = Store(Path(config['home']))
    try:
        with store.lock('native-startup'):
            preflight(config,binding,controller)
            journal = StartupJournal(store,binding['operation'],binding)
            if not journal.records():
                with store.transaction():
                    journal.append('PREFLIGHT_VALIDATED',dict(plan_hash=identity(plan)))
                    journal.append('SCOPE_CAPTURED',dict(text=entered,origin='FOREGROUND_CONTROLLING_TTY',old_core_claim='PRESERVED'))
            rows = journal.records()
            scope = next(r for r in rows if r['milestone']=='SCOPE_CAPTURED')
            receipt = dict(schema_version=1,route='NATIVE_MAINTENANCE_RECOVERY',binding=binding,
                           scope_event=scope['seq'],scope_text=scope['details']['text'],origin='DERIVED_NATIVE_SCOPE_NOT_A_CORE_CLAIM_RESET')
            path = store.home/'inputs/native-maintenance'/binding['operation']/'prepared.json'
            atomic(path,json.dumps(receipt,sort_keys=True)+'\n',exclusive=True)
            return dict(status='NATIVE_MAINTENANCE_PREPARED',receipt=str(path),receipt_sha256=digest(path.read_bytes()),
                        old_claim='STILL_CONSUMED',model_dispatch='NOT_STARTED',legacy_service='NOT_STARTED')
    finally:
        store.close()


def inspect_prepared(config, receipt_path, expected_hash, controller):
    raw=Path(receipt_path).read_bytes()
    if digest(raw)!=expected_hash:
        raise Rejected('Derived maintenance receipt hash changed')
    receipt=json.loads(raw)
    if receipt.get('route')!='NATIVE_MAINTENANCE_RECOVERY':
        raise Rejected('Native-only derived recovery receipt required')
    binding=receipt['binding']
    with ReadOnlyState(config['home']) as view:
        journal=StartupJournal(view,binding['operation'],binding)
        rows=journal.records()
        scope=next((r for r in rows if r['seq']==receipt['scope_event'] and r['milestone']=='SCOPE_CAPTURED'),None)
        if not scope or scope['details']['text']!=receipt['scope_text']:
            raise Rejected('Derived authority projection differs from committed foreground event')
        if any(r['milestone']=='LAUNCH_INTENT' for r in rows):
            return receipt, dict(status='HELD_RECONCILIATION_REQUIRED',last_proved=rows[-1]['milestone'],
                operation=binding['operation'],model_dispatch='NOT_RETRIED')
    plan=preflight(config,binding,controller,receipt=receipt,receipt_path=receipt_path,receipt_sha256=expected_hash)
    return receipt,plan


def run_recovery(config,args,controller):
    """Public product entry; one native derived admission, never a core re-claim."""
    import os
    import signal
    import threading
    import time
    from .engine import Engine,COMMON
    from .native import NativeAdapter,NativeIntake,NativeTerminals,capture_complete
    from .settings import Settings,policy_path
    from .service import capability
    from .cli import PROPOSAL_GUIDE
    from .native_lineage import PROJECTED_KEYS
    receipt,plan=inspect_prepared(config,args.prepared,args.prepared_sha256,controller)
    if plan.get('status')=='HELD_RECONCILIATION_REQUIRED' or args.check:
        print(json.dumps(dict(status=plan.get('status','NATIVE_MAINTENANCE_LAUNCH_CHECKED'),plan=plan,model_dispatch='NOT_STARTED')),flush=True)
        return
    binding=receipt['binding'];store=Store(Path(config['home']));adapter=intake=terminals=operator=None
    journal=StartupJournal(store,binding['operation'],binding)
    stopped=threading.Event();task_id=None
    try:
        with store.lock('native-startup'):
            receipt,plan=inspect_prepared(config,args.prepared,args.prepared_sha256,controller)
            if plan.get('status')=='HELD_RECONCILIATION_REQUIRED':
                raise Rejected('Derived launch intent already consumed')
            journal.append('LAUNCH_INTENT',dict(old_core_claim='PRESERVED_CONSUMED',source=binding['source_hash']))
            repo=Path(plan['original_repo']);workspace=Path(binding['workspace']);inputs=Path(binding['inputs'])
            import shutil
            shutil.copytree(repo,workspace,ignore=shutil.ignore_patterns('.git','__pycache__'))
            if tree(workspace)!=tree(repo):raise Rejected('Native snapshot source drift')
            inputs.mkdir(parents=True)
            atomic(inputs/'REFERENCE_LED_DESIGN.md',policy_path(config['workflow']).read_bytes(),exclusive=True)
            old=json.loads(checked_file(binding['predecessor_receipt']).read_text())
            request=restored_request(binding,receipt,args.prepared,args.prepared_sha256)
            material=dict(**{'full-prepared.json':checked_file(binding['predecessor_receipt']).read_bytes(),
                'maintenance-prepared.json':Path(args.prepared).read_bytes(),
                'original-request.json':json.dumps(old['prepared']['lineage']['preserved_request']).encode(),
                'preserved-requirements.json':json.dumps(old['prepared']['lineage']['preserved_requirements']).encode(),
                'successor-request.json':json.dumps(request).encode()})
            for item in binding['materials']:material['authority/'+item['name']]=checked_file(item).read_bytes()
            if binding.get('context_packet'):
                from .native_packet import load
                packet_folder=checked_file(binding['context_packet']).parent
                index=load(packet_folder)
                for name,record in index['originals'].items():
                    if name not in material or digest(material[name])!=record['sha256']:
                        raise Rejected('Current-context original does not match actual mounted input: '+name)
                material['current-context/INDEX.json']=(packet_folder/'INDEX.json').read_bytes()
                for section in index['sections']:
                    material['current-context/'+section['name']]=(packet_folder/section['name']).read_bytes()
            for name,data in material.items():atomic(safe_path(inputs,name),data,exclusive=True)
            settings=Settings(**config['settings']);engine=Engine(store,config['workflow'],defer_review=True)
            adapter=NativeAdapter(engine,settings,evidence_check=capture_complete);engine.adapter=adapter;engine.native_materials=material
            intake=NativeIntake(store.home,config['workflow']);intake.start()
            token=adapter.create_held_capability(binding['owner'],dict(repo=str(repo),request=request,key=binding['owner']+':native-revision'))
            rows=json.loads(checked_file(binding.get('generation_registry',binding['registry'])).read_text())
            for role in ('thinker','doer','reviewer'):
                spec=config['roles'][role]
                adapter.slots.start_role(role,workspace if role=='thinker' else spec['workspace'],inputs if role=='thinker' else spec['inputs'],controller,
                    generation=rows[role]['generation']+1,phase='read',
                    **(dict(mcp=token,intake_socket=intake.path) if role=='thinker' else {}))
            adapter.register_thinker(binding['owner'],token,held=True)
            adapter.prepared_owner=binding['owner'];adapter.prepared_hash=binding['predecessor_receipt']['sha256']
            adapter.owner_recovery_names=binding.get('owner_recovery_names',[])
            root=adapter.slots.root
            atomic(root/'supervisor.json',json.dumps(dict(pid=os.getpid(),process_identity=process_identity(os.getpid()),cmdline_hex=Path('/proc/self/cmdline').read_bytes().hex(),source=binding['source_hash'],maintenance_operation=binding['operation'])),exclusive=True)
            journal.append('SLOTS_CREATED',dict(registry=adapter.slots.save()))
            terminals=NativeTerminals(adapter.slots,headless=args.headless);terminals.sync(adapter.slots.save());adapter.slots.mapping_changed=terminals.sync
            for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopped.set())
            print(json.dumps(dict(status='NATIVE_MAINTENANCE_READY',attach=terminals.attach_command(),operation=binding['operation'])),flush=True)
            deadline=time.monotonic()+15
            while not stopped.is_set() and time.monotonic()<deadline and any(not b.clients for b in adapter.slots.backends.values()):stopped.wait(.05)
            if stopped.is_set() or any(not b.clients for b in adapter.slots.backends.values()):raise Rejected('Native attachment timeout; explicit recovery required')
            if identity(tree(controller))!=binding['controller_hash'] or identity(tree(Path(controller).parent))!=binding['source_hash']:
                raise Rejected('Frozen source changed after startup intent; hold before probe')
            journal.append('CLIENTS_ATTACHED')
            journal.append('PROBE_DISPATCH_INTENT',dict(thread=adapter.slots.backends['thinker'].thread))
            adapter.thinker_probe();journal.append('PROBE_COMPLETED')
            if binding.get('context_packet'):
                adapter.qualify_owner_packet()
                journal.append('CURRENT_CONTEXT_DELIVERY_VALIDATED',dict(
                    integrity='EXACT_CURRENT_SECTIONS',exposure='PUBLIC_TURN_OUTPUTS_CHECKED',
                    behavior='UNVERIFIED_UNTIL_TASK_AND_CHECKS'))
            adapter.release_thinker_tools();journal.append('SCOPE_RELEASED')
            journal.append('WORK_DISPATCH_INTENT',dict(thread=adapter.slots.backends['thinker'].thread))
            reading=('The complete current instruction/requirement/answer sections were just delivered and checked. '
                'Use that stable index; retrieve historical originals only for a specific missing fact. '
                'Do not repeat discovery or identical reads without naming an invalidation/missing section. '
                if binding.get('context_packet') else 'Read the exact maintenance scope, complete preserved requirements and authority materials. ')
            if binding.get('context_packet'):
                from .native_packet import load,work_guide
                reading+=work_guide(load(checked_file(binding['context_packet']).parent))
            adapter.thinker_turn(COMMON+PROPOSAL_GUIDE+'\n'+reading+'Perform restricted hosted research and original-page inspection. Submit one coherent task preserving the exact original eight requirements and full core lineage. Current scoped instruction:\n'+receipt['scope_text'])
            tasks=store.db.execute('SELECT id FROM tasks WHERE owner=?',(binding['owner'],)).fetchall()
            if len(tasks)!=1:raise Rejected('Exactly one native maintenance submission required')
            task_id=tasks[0]['id'];journal.append('TASK_SUBMITTED',dict(task=task_id,thread=adapter.slots.backends['thinker'].thread))
            adapter.hold_thinker_tools()
            engine.run(task_id)
            result=engine.result(task_id,binding['owner'])
            if result['state']!='CANDIDATE_SEALED':raise Rejected('Native qualification did not reach sealed hold')
            journal.append('QUALIFICATION_HOLD',dict(task=task_id,result=result))
            # Parent/operator action is served by this same process/Store; it never
            # starts another scheduler, hidden model or competing SQLite writer.
            from .native_operator import NativeOperator
            operator=NativeOperator(engine,adapter,binding,controller,journal);operator.start()
            print(json.dumps(dict(status='QUALIFICATION_HOLD',result=result,operator=str(operator.path))),flush=True)
            while not stopped.is_set():
                operator.poll(.2)
                if operator.stop_requested:break
                if any((b.error or b.proc.poll() is not None) and role not in operator.uncertain_roles for role,b in adapter.slots.backends.items()):raise Rejected('Native backend stopped; checked recovery required')
    except BaseException as ex:
        from .native_owner_outcomes import OwnerHold
        if isinstance(ex,OwnerHold):
            journal.append('OWNER_HELD',ex.result)
            print(json.dumps(ex.result),flush=True)
            return
        prior=journal.records();last=prior[-1]['milestone'] if prior else 'NONE'
        dispatched=any(r['milestone'] in ('PROBE_DISPATCH_INTENT','WORK_DISPATCH_INTENT') for r in prior)
        journal.append('FAILED_OR_UNCERTAIN',dict(last_proved=last,error=str(ex),classification='EXECUTION_REQUIRES_RECONCILIATION' if dispatched else 'STARTUP_REQUIRES_EFFECT_AUDIT',task=task_id))
        raise
    finally:
        if operator:operator.close()
        if adapter:
            adapter.slots.mapping_changed=None;adapter.close()
        if terminals:terminals.close()
        if intake:intake.close()
        store.close()
