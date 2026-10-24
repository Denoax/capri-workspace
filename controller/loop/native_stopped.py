"""Evidence-only stopped compaction inspection; fencing never permits dispatch.

No initializer, migration, process, socket or output file belongs in inspect().
The old checkpoint/event stays immutable. A fence only accounts for read-only
effects; generic resume and the final-review uncertainty guard remain intact.
"""
import contextlib
from dataclasses import dataclass, fields
import json
import os
from pathlib import Path
import sqlite3

from .adapter import process_identity
from .context import Checkpoint
from .native_startup import ReadOnlyState
from .settings import Settings
from .util import Rejected, identity, digest, tree


def require(condition, message):
    if not condition:
        raise Rejected(message)


class StoppedReadOnlyState(ReadOnlyState):
    """Immutable, fully checkpointed snapshot: never creates/updates SQLite SHM.

Immutable SQLite ignores WAL. Reject nonempty WAL instead of silently reading
stale authority or checkpointing somebody else's database. Mutation uses the
existing Store transaction/view and normal locks, never this snapshot reader.
"""
    def __init__(self, home):
        self.home = Path(home).resolve()
        path = self.home/'state/workflow.sqlite3'
        self.paths = [path, Path(str(path)+'-wal'), Path(str(path)+'-shm')]
        self.before = self.fingerprint()
        wal = self.paths[1]
        require(not wal.exists() or wal.stat().st_size == 0, 'Stopped database has uncheckpointed WAL; inspection cannot initialize/checkpoint it')
        self.db = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA query_only=ON')
        if self.db.execute('PRAGMA user_version').fetchone()[0] != 2:
            self.db.close()
            raise Rejected('Existing qualified Store schema required')

    def fingerprint(self):
        result = {}
        for path in self.paths:
            require(not path.is_symlink(), 'Symlinked state evidence')
            result[str(path)] = digest(path.read_bytes()) if path.is_file() else None
        return result

    def close(self):
        self.db.close()
        require(self.before == self.fingerprint(), 'State changed during immutable inspection; no authority established')


@dataclass(frozen=True)
class FileBinding:
    path: str
    sha256: str

    def __post_init__(self):
        require(isinstance(self.path, str) and isinstance(self.sha256, str) and len(self.sha256)==64 and
                all(c in '0123456789abcdef' for c in self.sha256), 'Invalid file binding type/digest')

    def read(self):
        p = Path(self.path)
        require(p.is_absolute() and not p.is_symlink() and p.is_file(), 'Missing/nonregular bound evidence')
        require(p.stat().st_size <= 32_000_000, 'Evidence exceeds bounded inspection')
        raw = p.read_bytes()
        require(digest(raw) == self.sha256, 'Evidence identity changed: ' + str(p))
        return raw

    def json(self):
        return json.loads(self.read())


@dataclass(frozen=True)
class StoppedCompaction:
    schema: int
    kind: str
    home: str
    runtime: str
    inputs: str
    task: str
    owner: str
    version: int
    task_generation: int
    packet_hash: str
    candidate_source: str
    recovery_source: str
    target_source: str
    target_root: str
    startup_operation: str
    maintenance_key: str
    scope_event: int
    intent_event: int
    bound_event: int
    uncertain_event: int
    prepared: FileBinding
    config: FileBinding
    registry: FileBinding
    supervisor: FileBinding
    checkpoint: FileBinding
    rehydration_events: FileBinding
    turn_context: FileBinding
    runtime_config: FileBinding
    received_frames: FileBinding
    compaction_receipt: FileBinding
    compaction_events: FileBinding
    maintenance_request: FileBinding
    terminals: tuple

    @classmethod
    def parse(cls, value):
        require(isinstance(value, dict) and set(value) == {f.name for f in fields(cls)}, 'Exact typed stopped-compaction case required')
        value = dict(value)
        names = ('prepared', 'config', 'registry', 'supervisor', 'checkpoint', 'rehydration_events',
                 'turn_context', 'runtime_config', 'received_frames', 'compaction_receipt', 'compaction_events', 'maintenance_request')
        try:
            for name in names:
                require(set(value[name]) == {'path', 'sha256'}, 'Exact evidence binding required')
                value[name] = FileBinding(**value[name])
            value['terminals'] = tuple(FileBinding(**v) for v in value['terminals'])
            result = cls(**value)
        except (TypeError, ValueError, KeyError) as ex:
            raise Rejected('Malformed stopped-compaction case') from ex
        require(type(result.schema) is int and result.schema == 1 and result.kind == 'STOPPED_READ_ONLY_COMPACTION', 'Unsupported recovery case')
        for name in ('version', 'task_generation', 'scope_event', 'intent_event', 'bound_event', 'uncertain_event'):
            require(type(getattr(result, name)) is int and getattr(result, name) > 0, 'Invalid version/event identity')
        require(result.scope_event < result.intent_event < result.bound_event < result.uncertain_event, 'Invalid recovery event order')
        require(all(isinstance(getattr(result, n), str) and getattr(result, n) for n in ('task', 'owner', 'startup_operation', 'maintenance_key')), 'Empty recovery identity')
        return result

    def key(self):
        from dataclasses import asdict
        return identity(asdict(self))


def event(view, seq):
    row = view.db.execute('SELECT seq,task,kind,data FROM events WHERE seq=?', (seq,)).fetchone()
    require(row is not None, 'Required immutable event missing')
    return dict(seq=row['seq'], task=row['task'], kind=row['kind'], data=json.loads(row['data']))


def fence_record(view, case):
    matches = []
    for row in view.db.execute("SELECT seq,data FROM events WHERE kind='NATIVE_STOPPED_MAINTENANCE_FENCED'"):
        value = json.loads(row['data'])
        if value.get('maintenance_key') == case.maintenance_key:
            require(value.get('case_hash') == case.key(), 'Fence key reused with changed evidence')
            matches.append(dict(event=row['seq'], **value))
    require(len(matches) <= 1, 'Conflicting fence authority')
    return matches[0] if matches else None


def inspect(config, value, controller, *, view=None):
    case = value if isinstance(value, StoppedCompaction) else StoppedCompaction.parse(value)
    controller = Path(controller).resolve()
    require(str(Path(config['home']).resolve()) == case.home, 'Wrong recovery home')
    require(identity(tree(controller.parent)) == case.recovery_source, 'Recovery-tool source drift')
    require(identity(tree(case.target_root)) == case.target_source and case.target_source != case.candidate_source, 'Target source transition is not bound')
    prior = case.prepared.json()
    binding = prior['binding']
    old_config = case.config.json()
    require(config == old_config and identity(config) == binding['config_hash'], 'Prior configuration changed')
    require(binding['owner'] == case.owner and binding['home'] == case.home and binding['source_hash'] == case.candidate_source, 'Historical scope/source mismatch')
    require(identity(tree(binding['controller'])) == binding['controller_hash'] and identity(tree(Path(binding['controller']).parent)) == case.candidate_source, 'Preserved controller drift')
    require(case.runtime == config['settings']['state_dir'], 'Wrong runtime')
    root = Path(case.runtime)
    with (StoppedReadOnlyState(case.home) if view is None else contextlib.nullcontext(view)) as state:
        state.require_current(case.owner)
        t = state.task(case.task)
        require((t['owner'], t['state'], t['version'], t['generation'], t['content_hash']) ==
                (case.owner, 'CANDIDATE_SEALED', case.version, case.task_generation, case.packet_hash), 'Exact sealed task/version/owner required')
        require(identity(t['packet']) == case.packet_hash, 'Packet identity changed')
        for original in t['packet'].get('instructions', []):
            FileBinding(original['path'], original['sha256']).read()
        seal = json.loads(t['seal'])
        require(seal['source_hash'] == case.candidate_source and tree(t['candidate']) == seal['files'], 'Candidate/source drift')
        require(not state.questions(case.owner, blocking=True), 'Pending question prevents fencing')
        require(not state.db.execute("SELECT id FROM human_inputs WHERE owner=? AND status='PENDING'", (case.owner,)).fetchone(), 'Pending human correction')
        require(not state.db.execute('SELECT token_hash FROM capabilities WHERE owner=? AND enabled=1', (case.owner,)).fetchone(), 'Live owner capability')
        require(not state.db.execute("SELECT id FROM attempts WHERE task=? AND status IN ('RUNNING','SPAWN_INTENT','DISPATCH_UNCERTAIN')", (case.task,)).fetchone(), 'Unresolved writer/attempt')
        scope = event(state, case.scope_event)
        require(scope['kind'] == 'NATIVE_STARTUP' and scope['data']['milestone'] == 'SCOPE_CAPTURED' and
                scope['data']['operation'] == case.startup_operation and prior['scope_event'] == case.scope_event and
                scope['data']['details'] == dict(old_core_claim='PRESERVED', origin='FOREGROUND_CONTROLLING_TTY', text=prior['scope_text']), 'Historical genuine scope differs')
        intent, bound, uncertain = [event(state, n) for n in (case.intent_event, case.bound_event, case.uncertain_event)]
        for row, milestone in ((intent, 'MAINTENANCE_INTENT'), (bound, 'MAINTENANCE_READ_ONLY_BOUND'), (uncertain, 'MAINTENANCE_UNCERTAIN')):
            require(row['kind'] == 'NATIVE_STARTUP' and row['data']['operation'] == case.startup_operation and
                    row['data']['parameters_hash'] == identity(binding) and row['data']['milestone'] == milestone and
                    row['data']['details']['key'] == case.maintenance_key, 'Maintenance event binding differs')
        old = bound['data']['details']
        require(old['action'] == intent['data']['details']['action'] == 'compact-role' and old['role'] == uncertain['data']['details']['role'] == 'doer', 'Only stopped read-only compaction is supported')
        require(old['generation'] == intent['data']['details']['generation'] and old['old_thread'] == intent['data']['details']['thread'], 'Historical backend identity differs')
        completed = [json.loads(r['data']) for r in state.db.execute("SELECT data FROM events WHERE task=? AND kind='NATIVE_ATTEMPT_RESULT' AND seq<?", (case.task, case.intent_event))]
        completed = [r for r in completed if r.get('role') == 'doer' and r.get('role_generation') == old['generation']]
        require(len(completed) == 1 and completed[0].get('status') == 'COMPLETED' and completed[0].get('thread') == old['old_thread'] and
                completed[0].get('pid') == old['pid'] and completed[0].get('start_identity') == old['process'] and
                completed[0].get('source_after') == case.candidate_source, 'Historical write-backend completion identity is unproven')
        require(old['checkpoint'] == case.checkpoint.path and old['checkpoint_sha256'] == case.checkpoint.sha256, 'Immutable checkpoint reference differs')
        require(uncertain['data']['details']['error'] == 'Native turn exceeded wall budget; reconcile effects', 'Unrecognized incomplete outcome')
        registry = case.registry.json()
        require(set(registry) == {'thinker','doer','reviewer'} and case.registry.path == str(root/'registry.json'), 'Wrong role registry')
        actual = registry['doer']
        settings = Settings(**config['settings'])
        require(all(row.get('model') == settings.model and row.get('effort') == settings.efforts[role] and row['phase'] == 'read'
                    for role,row in registry.items()), 'Stopped role/settings profile differs')
        require(actual['generation'] == old['generation'] + 1 and actual['phase'] == 'read' and actual['thread'] == old['old_thread'], 'Unproven read-only remount identity')
        require(actual['lineage'][-1] == dict(old_thread=old['old_thread'], new_thread=actual['thread'], old_generation=old['generation'], new_generation=actual['generation']), 'Remount lineage is absent')
        checkpoint = case.checkpoint.json()
        authority = checkpoint['state']['authority']
        Checkpoint(Path(case.checkpoint.path), case.home).validate(authority)
        lease = authority['lease_generations']
        require(lease == dict(task=case.task, task_generation=case.task_generation, role_generation=actual['generation'], role='doer',
                thread=actual['thread'], lease='native-writer:'+case.task, server=str(actual['pid'])+':'+actual['process_identity'],
                process=actual['process_identity'], phase='read'), 'Contemporaneous read-only checkpoint proof missing')
        require(authority['contract_requirements'] == t['packet'] and authority['request_corrections'] == t['packet']['request'], 'Checkpoint lost exact request/requirements')
        require(authority['source_instructions']['candidate'] == old['source'] == seal['files'] and
                authority['source_instructions']['inputs'] == old['inputs'], 'Checkpoint source/input binding differs')
        require(case.runtime_config.path == str(root/'doer/runtime/config.toml') and case.runtime_config.read().decode() == Settings(**config['settings']).config('doer','read'), 'Read-only runtime profile differs')
        require(Path(case.inputs).is_relative_to(Path(case.home)/'inputs'/case.task) and tree(case.inputs) == old['inputs'], 'Mounted original inputs changed')
        validated = [event(state, r['seq']) for r in state.db.execute("SELECT seq FROM events WHERE task=? AND kind='REHYDRATION_VALIDATED' AND seq>? AND seq<?", (case.task, case.intent_event, case.bound_event))]
        require(len(validated) == 1 and validated[0]['data']['checkpoint'] == checkpoint['sha256'] and
                case.rehydration_events.path == str(Path(validated[0]['data']['capture'])/'events.jsonl'), 'Rehydration is not linked to immutable checkpoint events')
        rehydration = [json.loads(line) for line in case.rehydration_events.read().decode().splitlines()]
        starts = [r['message']['params']['turn']['id'] for r in rehydration if r['generation'] == actual['generation'] and r['message'].get('method') == 'turn/started']
        ends = [r['message']['params']['turn'] for r in rehydration if r['generation'] == actual['generation'] and r['message'].get('method') == 'turn/completed']
        require(len(starts) == 1 and len(ends) == 1 and ends[0]['id'] == starts[0] and ends[0]['status'] == 'completed', 'Completed generation-bound rehydration is missing')
        turns = []
        for line in case.turn_context.read().decode().splitlines():
            row = json.loads(line)
            if row.get('type') == 'turn_context' and row['payload'].get('turn_id') == starts[0]:
                turns.append({key:row['payload'][key] for key in ('sandbox_policy','permission_profile')})
        require(len(turns) == 1 and turns[0]['sandbox_policy']['type'] == 'read-only' and
                all(v['access'] != 'write' for v in turns[0]['permission_profile']['file_system']['entries']), 'Contemporaneous native read-only permissions missing')
        public = [json.loads(line) for line in case.compaction_events.read().decode().splitlines()]
        require(public and all(r['role'] == 'doer' and r['generation'] == actual['generation'] for r in public), 'Compaction capture generation differs')
        receipt = case.compaction_receipt.json()
        require(receipt == dict(status='UNCERTAIN', role='doer', thread=actual['thread']), 'Compaction cannot be reclassified as success')
        received = [json.loads(line) for line in case.received_frames.read().decode().splitlines()]
        received = [r for r in received if r.get('phase') == 'RECEIVED']
        require(received and all(r.get('role') == 'doer' and r.get('generation') == actual['generation'] and
                r.get('expected_thread') == actual['thread'] for r in received), 'Received-frame identity differs')
        supervisor = case.supervisor.json()
        require(case.supervisor.path == str(root/'supervisor.json') and supervisor.get('source') == case.candidate_source and
                supervisor.get('maintenance_operation') == case.startup_operation, 'Stopped supervisor binding differs')
        request = case.maintenance_request.json()
        expected = dict(task=case.task, version=case.version, owner=case.owner, packet_hash=case.packet_hash,
                        source_hash=case.candidate_source, controller_hash=binding['controller_hash'],
                        supervisor_pid=supervisor['pid'], supervisor_identity=supervisor['process_identity'],
                        role='doer', thread=old['old_thread'], role_generation=old['generation'])
        require(request['action'] == 'compact-role' and request['binding'] == expected and
                identity(dict(action=request['action'], binding=request['binding'])) == case.maintenance_key,
                'Immutable maintenance key does not bind the stopped supervisor/task')
        processes = [old['pid'], supervisor['pid']] + [row['pid'] for row in registry.values()]
        require(case.terminals, 'Owned terminal cleanup record missing')
        for spec in case.terminals:
            processes += [r['pid'] for r in spec.json().values()]
        require(all(process_identity(pid) is None for pid in processes), 'Live or PID-reused process prevents fencing')
        require(all(not os.path.lexists(root/name) for name in ('thinker.sock','doer.sock','reviewer.sock','operator.sock')), 'Runtime endpoint remains')
        later = [event(state, row['seq']) for row in state.db.execute('SELECT seq FROM events WHERE seq>?', (case.uncertain_event,))]
        for row in later:
            data = row['data']
            relevant = row['task'] == case.task or data.get('owner') == case.owner or data.get('operation') == case.startup_operation
            allowed = row['kind'] == 'NATIVE_CAPABILITY_REVOKED' or (row['kind'] in ('NATIVE_STOPPED_MAINTENANCE_FENCED','NATIVE_STOPPED_QUALIFICATION_PREPARED') and data.get('case_hash') == case.key())
            require(not relevant or allowed, 'Later task/owner/operation effect is unresolved')
        fenced = fence_record(state, case)
        if fenced:
            require(fenced.get('classification') == 'INCOMPLETE_COMPACTION_ACCOUNTED_READ_ONLY' and fenced.get('new_dispatch') == 'NOT_AUTHORIZED', 'Invalid fence classification')
        preparations = [r['seq'] for r in state.db.execute("SELECT seq,data FROM events WHERE kind='NATIVE_STOPPED_QUALIFICATION_PREPARED'") if json.loads(r['data']).get('case_hash') == case.key()]
        require(len(preparations) <= 1, 'Conflicting qualification preparations')
        return dict(status='STOPPED_COMPACTION_CHECKED', case_hash=case.key(), task=case.task, owner=case.owner,
                    maintenance_key=case.maintenance_key, old_event=case.bound_event, uncertain_event=case.uncertain_event,
                    old_identity={k:old[k] for k in ('old_thread','generation','pid','process')},
                    actual_identity={k:actual[k] for k in ('thread','generation','pid','process_identity','phase')},
                    candidate_source=case.candidate_source, old_controller=binding['controller_hash'],
                    recovery_source=case.recovery_source, target_source=case.target_source,
                    read_only_proof='IMMUTABLE_CHECKPOINT_AND_NATIVE_TURN_CONTEXT', compaction='INCOMPLETE',
                    fence_event=fenced['event'] if fenced else None,
                    prepared_event=preparations[0] if preparations else None, new_dispatch='NOT_AUTHORIZED')


def commit_fence(store, config, case, controller):
    """Called only after the existing foreground boundary; tests use synthetic Store."""
    with store.lock('native-startup'), store.lock('native-writer'), store.transaction():
        result = inspect(config, case, controller, view=store)
        require(result['fence_event'] is None, 'Fence already committed; inspect without replay')
        data = dict(result, classification='INCOMPLETE_COMPACTION_ACCOUNTED_READ_ONLY',
                    origin='FOREGROUND_CONTROLLING_TTY')
        seq = store.event(case.task, 'NATIVE_STOPPED_MAINTENANCE_FENCED', data)
        return dict(status='STOPPED_COMPACTION_FENCED', event=seq, case_hash=case.key(), new_dispatch='NOT_AUTHORIZED')


def qualification_plan(config, case, controller, runtime, *, view=None):
    result = inspect(config, case, controller, view=view)
    require(result['fence_event'] is not None, 'A committed stopped fence is required')
    require(result['prepared_event'] is None, 'Preparation consumed; inspect rather than replay')
    require(Path(runtime).is_absolute() and not os.path.lexists(runtime) and runtime != case.runtime, 'New disposable runtime must be unused')
    return dict(result, status='NEW_QUALIFICATION_PLAN_CHECKED', target_runtime=runtime,
                foreground_scope='REQUIRED_FOR_DISTINCT_SOURCE_CONDITION', old_scope='HISTORICAL_NOT_REPLAYED',
                launch='NOT_IMPLEMENTED_BY_THIS_FENCE', new_dispatch='NOT_AUTHORIZED')


def prepare_qualification(store, config, case, controller, runtime, scope_text):
    with store.lock('native-startup'), store.lock('native-writer'), store.transaction():
        plan = qualification_plan(config, case, controller, runtime, view=store)
        require(scope_text == scope_line(case, runtime), 'Exact source-bound foreground scope required')
        seq = store.event(case.task, 'NATIVE_STOPPED_QUALIFICATION_PREPARED', dict(plan,
            origin='FOREGROUND_CONTROLLING_TTY', scope=scope_text))
        return dict(status='NEW_QUALIFICATION_SCOPE_PREPARED', event=seq, new_dispatch='NOT_AUTHORIZED')


def scope_line(case, runtime):
    return 'Prepare disposable qualification for '+case.task+' using source '+case.target_source+' at '+runtime+'; preserve the fenced incomplete compaction, original requirements, limits and human gates.'


def run_cli(config, args, controller):
    require(args.binding is not None, 'Bound stopped-compaction evidence required')
    case = StoppedCompaction.parse(json.loads(args.binding.read_text()))
    result = inspect(config, case, controller)
    if args.command == 'prepare-stopped-qualification':
        require(args.new_runtime is not None, 'An unused disposable runtime is required')
        runtime = str(args.new_runtime)
        result = qualification_plan(config, case, controller, runtime)
    if args.check or args.command == 'inspect-stopped-maintenance':
        print(json.dumps(result), flush=True)
        return
    if args.command == 'fence-stopped-maintenance':
        require(result['fence_event'] is None, 'Fence already committed; inspect without replay')
    # Same foreground-origin boundary as existing native preparation/fence
    # commands. No model role can supply this input or access this Store.
    from .cli import require_human_tty
    from .store import Store
    line = ('fence '+case.maintenance_key+' '+case.key()) if args.command == 'fence-stopped-maintenance' else scope_line(case, runtime)
    with require_human_tty() as tty:
        tty.write('Fence/preparation only; new dispatch remains NOT_AUTHORIZED.\nType exactly:\n'+line+'\n> ')
        tty.flush()
        require(tty.readline().strip() == line, 'Exact foreground instruction did not match')
    store = Store(case.home)
    try:
        result = commit_fence(store, config, case, controller) if args.command == 'fence-stopped-maintenance' else prepare_qualification(store, config, case, controller, runtime, line)
        print(json.dumps(result), flush=True)
    finally:
        store.close()
