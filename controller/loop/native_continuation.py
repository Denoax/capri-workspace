"""Bound foreground preparation for a native revision, never the legacy loop.

Preparation and the subsequent one-shot native launch are separate operations.
The authoritative re-contract is the existing append-only core receipt.
"""
import json
from pathlib import Path

from .adapter import process_identity
from .cli import _prepare_recontract, _claim_recontract_thinker, require_human_tty
from .util import Rejected, atomic, digest, identity, safe_path, tree


def inspect_binding(store, engine, binding, controller):
    if str(store.home.resolve()) != binding['home']:
        raise Rejected('Native re-contract home binding changed')
    if identity(engine.config) != binding['workflow_hash']:
        raise Rejected('Native continuation workflow configuration changed')
    if identity(tree(controller)) != binding['controller_hash']:
        raise Rejected('Native maintenance controller source changed')
    for item in binding['materials']:
        path = Path(item['path'])
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != item['sha256']:
            raise Rejected('Native continuation instruction material changed')
        safe_path(Path('/material-root'), item['name'])
    instruction = Path(binding['correction_file']).read_text().rstrip('\r\n')
    if not instruction or '\n' in instruction or digest(instruction.encode()) != binding['correction_sha256']:
        raise Rejected('Expected one-line scoped instruction changed')
    registry = Path(binding['registry'])
    if registry.is_symlink() or digest(registry.read_bytes()) != binding['registry_sha256']:
        raise Rejected('Prior role registry changed; do not remove or replace it')
    rows = json.loads(registry.read_text())
    if set(rows) != {'thinker', 'doer', 'reviewer'}:
        raise Rejected('Exact prior three-role registry required')
    for role, row in rows.items():
        if process_identity(row['pid']) is not None:
            raise Rejected('Prior role PID exists; reconcile ownership before native continuation')
        if (registry.parent / (role+'.sock')).exists():
            raise Rejected('Prior role endpoint remains; explicit reconciliation required')
    task = store.task(binding['task'])
    engine.verify_inputs(task)
    if task['content_hash'] != binding['packet_hash'] or task['generation'] != binding['generation']:
        raise Rejected('Parent packet/task generation changed')
    if task['candidate'] != binding['candidate'] or identity(tree(task['candidate'])) != binding['candidate_hash']:
        raise Rejected('Preserved candidate changed')
    for row in store.db.execute('SELECT status FROM attempts WHERE task=?', (task['id'],)):
        if row['status'] in ('SPAWN_INTENT', 'RUNNING', 'DISPATCH_UNCERTAIN'):
            raise Rejected('Unreconciled attempt cannot enter native revision')
    saved = store.recontract_receipt(task['id'])
    if saved:
        if task['state'] != 'SUPERSEDED' or saved['lineage']['correction'].rstrip(' \t') != instruction:
            raise Rejected('Committed native revision conflicts with this instruction')
        if task['version'] != binding['version']+1:
            raise Rejected('Committed parent version changed')
    elif task['state'] != 'BLOCKED' or task['version'] != binding['version']:
        raise Rejected('Held parent state/version changed')
    return task, instruction, saved


def prepare_native_revision(store, engine, binding, controller, *, check_only=False):
    task, instruction, saved = inspect_binding(store, engine, binding, controller)
    if check_only:
        return dict(status='NATIVE_RECONTRACT_CHECKED', task=task['id'],
                    version=task['version'], generation=task['generation'],
                    already_prepared=bool(saved), model_dispatch='NOT_STARTED',
                    legacy_service='NOT_STARTED', binding_hash=identity(binding))
    if not saved:
        with require_human_tty() as tty:
            tty.write('Native revision only; no legacy scheduler or model is started.\n'
                      'Parent '+task['id']+', packet '+task['content_hash']+
                      ', version '+str(task['version'])+', generation '+str(task['generation'])+'.\n'
                      'Paste the exact single-line scoped continuation instruction:\n> ')
            tty.flush()
            entered = tty.readline().rstrip('\r\n')
        # Clipboard padding is not a different scope. Pass the actual input to
        # the core unchanged so its receipt preserves what the operator entered.
        if entered.rstrip(' \t') != instruction:
            raise Rejected('Scoped instruction did not match; held task is unchanged')
        # Same scheduler lock and exact core function as prepare_recontract().
        # Validate the operator-visible binding under that lock before committing.
        with store.lock():
            _, _, saved = inspect_binding(store, engine, binding, controller)
            if not saved:
                repo, text, lineage = _prepare_recontract(store, engine, task['id'], entered)
                saved = dict(repo=repo, text=text, lineage=lineage)
    operation = saved['lineage']['recontract_operation']
    root = store.home/'inputs/native-recontract'/operation
    for item in binding['materials']:
        atomic(safe_path(root/'authority', item['name']), Path(item['path']).read_bytes(), exclusive=True)
    receipt = dict(schema_version=1, route='NATIVE_APP_SERVER_ONLY', binding=binding,
                   prepared=saved, material_root=str(root/'authority'),
                   input_comparison='EXACT_EXCEPT_TRAILING_ASCII_SPACES_OR_TABS',
                   model_dispatch='NOT_STARTED', legacy_service='NOT_STARTED',
                   origin='EXISTING_CORE_FOREGROUND_RECONTRACT_RECEIPT')
    path = root/'prepared.json'
    atomic(path, json.dumps(receipt, sort_keys=True)+'\n', exclusive=True)
    return dict(status='NATIVE_RECONTRACT_PREPARED', parent_task=task['id'],
                successor_owner=saved['lineage']['successor_owner'], operation=operation,
                receipt=str(path), receipt_sha256=digest(path.read_bytes()),
                model_dispatch='NOT_STARTED', legacy_service='NOT_STARTED',
                next_action='Checked native restoration and one-shot native Thinker claim; no exec fallback')


def claim_native_revision(store, engine, prepared_path, controller):
    """Trusted supervisor launch boundary; caller must restore owned slots first.

    This only claims the core-derived owner. It cannot launch a model or silently
    retry an uncertain launch, and is not exposed through a model tool.
    """
    receipt = json.loads(Path(prepared_path).read_text())
    if receipt['route'] != 'NATIVE_APP_SERVER_ONLY':
        raise Rejected('Native continuation route required')
    _, _, saved = inspect_binding(store, engine, receipt['binding'], controller)
    if saved != receipt['prepared']:
        raise Rejected('Prepared receipt differs from committed core lineage')
    for item in receipt['binding']['materials']:
        p = safe_path(Path(receipt['material_root']), item['name'])
        if digest(p.read_bytes()) != item['sha256']:
            raise Rejected('Resolved native instruction material drift')
    lineage = saved['lineage']
    _claim_recontract_thinker(store, lineage, lineage['successor_owner'])
    return saved


class PreparedNativeContinuation:
    """Trusted product boundary; no automatic retry, scheduler or human input."""
    def __init__(self, store, engine, adapter, config, prepared, expected_hash, controller):
        self.store, self.engine, self.adapter = store, engine, adapter
        self.config, self.path, self.controller = config, Path(prepared), Path(controller)
        self.expected_hash = expected_hash

    def check(self):
        raw = self.path.read_bytes()
        if digest(raw) != self.expected_hash:
            raise Rejected('Prepared receipt hash drift')
        receipt = json.loads(raw)
        if receipt.get('schema_version') != 1 or receipt.get('route') != 'NATIVE_APP_SERVER_ONLY':
            raise Rejected('Native prepared route required')
        binding = receipt['binding']
        if identity(self.config) != binding['config_hash']:
            raise Rejected('Native launch configuration drift')
        parent, instruction, saved = inspect_binding(self.store, self.engine, binding, self.controller)
        if saved != receipt['prepared']:
            raise Rejected('Prepared core receipt mismatch')
        slots = self.adapter.slots
        if slots.backends or slots.root.resolve() != Path(binding['registry']).parent.resolve():
            raise Rejected('Empty supervisor at exact prior registry root required')
        supervisor = slots.root/'supervisor.json'
        if supervisor.exists() and process_identity(json.loads(supervisor.read_text())['pid']) is not None:
            raise Rejected('Prior supervisor still exists')
        if self.store.db.execute("SELECT seq FROM events WHERE task=? AND kind='RECONTRACT_THINKER_INTENT'", (parent['id'],)).fetchone():
            raise Rejected('Already claimed; explicit checked recovery required')
        for item in binding['materials']:
            if digest(safe_path(Path(receipt['material_root']), item['name']).read_bytes()) != item['sha256']:
                raise Rejected('Resolved native instruction material drift')
        return receipt, saved, instruction

    def launch(self, workspace, inputs, token, intake_socket):
        # Claim before any process starts: an interrupted launch cannot be retried.
        with self.store.lock():
            receipt, saved, _ = self.check()
            claim_native_revision(self.store, self.engine, self.path, self.controller)
        slots = self.adapter.slots
        raw = Path(receipt['binding']['registry']).read_bytes()
        rows = json.loads(raw)
        atomic(slots.root/('registry-before-'+saved['lineage']['recontract_operation']+'.json'), raw, exclusive=True)
        self.owner = saved['lineage']['successor_owner']
        for role in ('thinker', 'doer', 'reviewer'):
            row = rows[role]
            spec = self.config['roles'][role]
            if role == 'doer' and not row.get('empty', True):
                slots.restore_saved_role(role, spec['workspace'], spec['inputs'], self.controller,
                    registry_hash=digest(raw), frozen_registry=raw)
            else:
                slots.start_role(role, workspace if role == 'thinker' else spec['workspace'],
                    inputs if role == 'thinker' else spec['inputs'], self.controller,
                    generation=row['generation']+1, phase='read',
                    **(dict(mcp=token, intake_socket=intake_socket) if role == 'thinker' else {}))
                b = slots.backends[role]
                b.lineage = row.get('lineage', []) + [dict(old_thread=row['thread'],
                    new_thread=b.thread, old_generation=row['generation'], new_generation=b.generation,
                    prepared_sha256=self.expected_hash, reason='EXPLICIT_PREPARED_CONTINUATION')]
        self.adapter.register_thinker(self.owner, token,held=True)
        self.adapter.prepared_owner = self.owner
        self.adapter.prepared_hash = self.expected_hash
        return slots.save()

    def restart(self, task, role, checkpoint, *, expected_pid, expected_process):
        if self.store.task(task)['owner'] != self.owner:
            raise Rejected('Restart owner mismatch')
        return self.adapter.restart_backend(task, role, checkpoint,
            expected_pid=expected_pid, expected_process=expected_process)


def check_unclaimed_continuation(config,args,controller):
    """Inspect the original route without Store/Notes/runtime initialization."""
    from types import SimpleNamespace
    from .native_startup import ReadOnlyState,check_owner_ledger
    from .engine import Engine
    raw=Path(args.prepared).read_bytes()
    if digest(raw)!=args.prepared_sha256:raise Rejected('Prepared receipt hash drift')
    receipt=json.loads(raw)
    if receipt.get('route')!='NATIVE_APP_SERVER_ONLY' or identity(config)!=receipt['binding']['config_hash']:
        raise Rejected('Prepared native route/configuration mismatch')
    verifier=SimpleNamespace(config=config['workflow'])
    verifier.verify_inputs=lambda task:Engine.verify_inputs(verifier,task)
    with ReadOnlyState(config['home']) as view:
        parent,_,saved=inspect_binding(view,verifier,receipt['binding'],controller)
        if saved!=receipt['prepared']:raise Rejected('Prepared core receipt mismatch')
        if view.db.execute("SELECT seq FROM events WHERE task=? AND kind='RECONTRACT_THINKER_INTENT'",(parent['id'],)).fetchone():
            raise Rejected('Original launch claim consumed; use separately bound native maintenance recovery')
    owner=saved['lineage']['successor_owner'];root=Path(config['settings']['state_dir'])
    if root.resolve()!=Path(receipt['binding']['registry']).parent.resolve():raise Rejected('Exact predecessor runtime required')
    check_owner_ledger(root,owner)
    for destination in (Path(config['home'])/'workspace/thinker'/owner,Path(config['home'])/'inputs/thinker'/owner):
        if destination.exists():raise Rejected('Prior snapshot exists; no overwrite or blind launch retry')
    return dict(status='NATIVE_CONTINUATION_CHECKED',owner=owner,model_dispatch='NOT_STARTED',state_initialized=False)


def run_prepared(config, args, controller):
    """Explicit operator command; uses committed input and stops after one task."""
    import fcntl
    import os
    import signal
    import threading
    import time
    from .store import Store
    from .engine import Engine, COMMON
    from .native import NativeAdapter, NativeIntake, NativeTerminals, capture_complete
    from .settings import Settings
    from .service import capability
    from .cli import snapshot, PROPOSAL_GUIDE
    from .native_lineage import PROJECTED_KEYS
    if not args.prepared or not args.prepared_sha256:
        raise Rejected('Exact prepared path and SHA-256 required')
    checked=check_unclaimed_continuation(config,args,controller)
    if args.check:
        print(json.dumps(checked),flush=True)
        return
    store = Store(Path(config['home']).resolve())
    adapter = intake = terminals = None
    try:
        engine = Engine(store, config['workflow'], defer_review=args.defer_review)
        adapter = NativeAdapter(engine, Settings(**config['settings']), evidence_check=capture_complete)
        engine.adapter = adapter
        root = adapter.slots.root
        with (root/'supervisor.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            continuation = PreparedNativeContinuation(store, engine, adapter, config,
                args.prepared, args.prepared_sha256, controller)
            receipt, saved, instruction = continuation.check()
            owner = saved['lineage']['successor_owner']
            workspace, inputs = snapshot(store.home, saved['repo'], owner, config=config['workflow'])
            if tree(workspace) != tree(saved['repo']):
                raise Rejected('Prepared Thinker snapshot drift')
            material = {'full-prepared.json': args.prepared.read_bytes(),
                'original-request.json': json.dumps(saved['lineage']['preserved_request']).encode(),
                'preserved-requirements.json': json.dumps(saved['lineage']['preserved_requirements']).encode()}
            for item in receipt['binding']['materials']:
                material['authority/'+item['name']] = safe_path(Path(receipt['material_root']), item['name']).read_bytes()
            lineage = {k: saved['lineage'][k] for k in PROJECTED_KEYS}
            lineage['full_core_lineage'] = dict(path=str(args.prepared.resolve()),
                sha256=args.prepared_sha256, origin='ACTUAL_COMMITTED_CORE_FOREGROUND_RECONTRACT')
            request = dict(text=instruction, origin='VERIFIED_CORE_FOREGROUND_RECONTRACT', lineage=lineage)
            material['successor-request.json'] = json.dumps(request).encode()
            engine.native_materials = material
            for name, data in material.items():
                atomic(safe_path(inputs, name), data, exclusive=True)
            intake = NativeIntake(store.home, config['workflow'])
            intake.start()
            token = adapter.create_held_capability(owner, dict(repo=saved['repo'], request=request, key=owner+':native-revision'))
            terminals = NativeTerminals(adapter.slots, headless=args.headless)
            continuation.launch(workspace, inputs, token, intake.path)
            atomic(root/'supervisor.json', json.dumps(dict(pid=os.getpid(),
                process_identity=process_identity(os.getpid()), cmdline_hex=Path('/proc/self/cmdline').read_bytes().hex(),
                prepared_sha256=args.prepared_sha256)))
            terminals.sync(adapter.slots.save())
            adapter.slots.mapping_changed = terminals.sync
            stopped = threading.Event()
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: stopped.set())
            print(json.dumps(dict(status='NATIVE_CONTINUATION_READY', attach={r:adapter.slots.attach(r) for r in ('thinker','doer','reviewer')})), flush=True)
            deadline = time.monotonic()+15
            while not stopped.is_set() and time.monotonic()<deadline and any(not b.clients for b in adapter.slots.backends.values()):
                stopped.wait(.05)
            if stopped.is_set() or any(not b.clients for b in adapter.slots.backends.values()):
                raise Rejected('Native frontend attachment incomplete; explicit recovery required')
            adapter.thinker_probe()
            adapter.release_thinker_tools()
            adapter.thinker_turn(COMMON+PROPOSAL_GUIDE+'\nRead full-prepared.json, original-request.json, preserved-requirements.json and successor-request.json. Inspect authority materials. Submit one exact scoped continuation using the prepared lineage; preserve all original requirements. Perform hosted primary-source research when needed. Stop after submission.')
            tasks = list(store.db.execute('SELECT id FROM tasks WHERE owner=?', (owner,)))
            if len(tasks) != 1:
                raise Rejected('Exactly one actual Thinker submission required')
            engine.run(tasks[0]['id'])
            result = engine.result(tasks[0]['id'], owner)
            if result['state'] == 'REPORTING':
                from .engine import REPORT_SCHEMA
                adapter.thinker_turn(COMMON+'Report the controller-bound result and stop: '+json.dumps(result), report_task=tasks[0]['id'], schema=REPORT_SCHEMA)
            print(json.dumps(engine.result(tasks[0]['id'], owner)), flush=True)
            while not stopped.wait(.2):
                if any(b.error or b.proc.poll() is not None for b in adapter.slots.backends.values()):
                    raise Rejected('Backend exited; explicit checked recovery required')
    finally:
        if adapter:
            adapter.slots.mapping_changed = None
            adapter.close()
        if terminals:
            terminals.close()
        if intake:
            intake.close()
        store.close()
