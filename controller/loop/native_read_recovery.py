"""Parent-only recovery of a proved, completed, read-validation failure.

Store records own authority. Files are reproducible projections; none can clear
a failed intent or authorize launch by itself. Unknown effects stay outside this
route, including any write, MCP call, absent terminal or unrecognized command.
"""
import copy
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import stat
import zipfile

from .adapter import process_identity
from .context import Checkpoint, derive_checkpoint
from .native_operator import unresolved_maintenance
from .native_startup import ReadOnlyState, StartupJournal
from .util import Rejected, atomic, digest, identity, tree


ROUTE = 'CHECKED_COMPLETED_READ_RECOVERY'
KINDS = ('NATIVE_READ_FAILURE_RECONCILED', 'NATIVE_READ_RECOVERY_ADMITTED')
BINDING_KEYS = {'schema', 'parent_config', 'parent_receipt', 'review', 'approval',
    'intent_event', 'failure_event', 'registry', 'supervisor', 'captures', 'checkpoints',
    'source_hash', 'controller_hash', 'config_hash'}


def require(value, reason):
    if not value:
        raise Rejected(reason)


def path_checked(value, root=None):
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts,
            'Absolute canonical recovery path required')
    require(not any(p.is_symlink() for p in (path, *path.parents)),
            'Symlinked recovery path')
    if root is not None:
        require(path.is_relative_to(Path(root)), 'Recovery path escaped its owner root')
    return path


def file_checked(spec, root=None):
    require(isinstance(spec, dict) and set(spec) == {'path', 'sha256'},
            'Exact recovery file binding required')
    path = path_checked(spec['path'], root)
    metadata = path.lstat()
    require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid(),
            'Recovery input must be an owned regular file')
    require(digest(path.read_bytes()) == spec['sha256'], 'Recovery input bytes changed: '+str(path))
    return path


def event(view, seq, kind):
    require(type(seq) is int and seq > 0, 'Exact event sequence required')
    row = view.db.execute('SELECT * FROM events WHERE seq=?', (seq,)).fetchone()
    require(row is not None and row['kind'] == kind, 'Required committed event is absent')
    return json.loads(row['data'])


def authority_records(view, parent_key, binding):
    found = {}
    for row in view.db.execute('SELECT seq,kind,data FROM events WHERE kind IN (?,?) ORDER BY seq', KINDS):
        data = json.loads(row['data'])
        if data.get('parent_key') != parent_key:
            continue
        require(data.get('parameters_hash') == identity(binding),
                'Failed parent already has a different successor binding')
        require(row['kind'] not in found, 'Duplicate failed-parent authority')
        found[row['kind']] = dict(seq=row['seq'], data=data)
    return found


def observed_authority(parent, old, failed):
    """An observed restore advances lineage, never certifies rehydration."""
    authority = copy.deepcopy(parent['state']['authority'])
    previous = authority['lease_generations']
    expected = dict(role_generation=old['generation'], thread=old['thread'],
        server=str(old['pid'])+':'+str(old['process_identity']),
        process=str(old['process_identity']), phase='read')
    require(all(previous.get(k) == v for k, v in expected.items()),
            'Original checkpoint does not match its retired role')
    current = dict(role_generation=failed['generation'], thread=failed['thread'],
        server=str(failed['pid'])+':'+str(failed['process_identity']),
        process=str(failed['process_identity']), phase='read')
    authority['lease_generations'].update(current)
    return authority, dict(kind='restart', old=expected, new=current)


def checkpoint_projection(home, original_path, old, failed, target):
    original = path_checked(original_path, home)
    parent = Checkpoint(original, home)
    value = json.loads(original.read_text())
    parent.validate(value['state']['authority'])
    authority, transition = observed_authority(value, old, failed)
    artifacts = dict(value['state']['artifacts'])
    artifacts[str(original.relative_to(home))] = digest(original.read_bytes())
    state = dict(authority=authority, artifacts=artifacts)
    envelope = dict(state=state, sha256=identity(state))
    raw = json.dumps(envelope, sort_keys=True).encode()
    return dict(path=str(target), sha256=digest(raw), state_sha256=identity(state),
        original=str(original), authority=authority, transition=transition)


def capture_proof(path, row, prompt, final, command=None, *, role='thinker', optional_commands=()):
    """Check public lifecycle and the exact read-only command, without reasoning."""
    from .native import matches_read_command
    records = [json.loads(line) for line in path.read_text().splitlines()]
    starts, ends, commands, finals, messages = [], [], {}, [], []
    required_commands = [command] if isinstance(command,str) else list(command or [])
    allowed_commands = required_commands + list(optional_commands)
    selected_commands = set()
    times = []
    allowed = {'thread/status/changed', 'thread/settings/updated', 'turn/started',
        'turn/completed', 'item/started', 'item/completed', 'item/agentMessage/delta',
        'turn/moderationMetadata', 'thread/tokenUsage/updated',
        'account/rateLimits/updated', 'thread/readState/changed',
        'item/commandExecution/outputDelta'}
    for record in records:
        require(record.get('role') == role and record.get('generation') == row['generation'],
                'Capture role/generation differs')
        times.append(datetime.fromisoformat(record['time']).timestamp())
        message = record['message']
        method, params = message.get('method'), message.get('params', {})
        require(method in allowed, 'Unrecognized effect in recovery capture')
        require('threadId' not in params or params['threadId'] == row['thread'],
                'Capture thread differs')
        if method == 'turn/started':
            starts.append(params['turn']['id'])
        if 'turnId' in params:
            require(len(starts) == 1 and params['turnId'] == starts[0], 'Capture turn differs')
        if method == 'turn/completed':
            turn = params['turn']
            require(turn['status'] == 'completed' and turn.get('error') is None,
                    'Recovery capture has no successful terminal')
            ends.append(turn['id'])
        if method not in ('item/started', 'item/completed'):
            continue
        item = params.get('item', {})
        require(item.get('type') in {'userMessage', 'agentMessage', 'commandExecution'},
                'Non-read tool or effect in recovery capture')
        if item['type'] == 'commandExecution':
            matching = [c for c in allowed_commands if matches_read_command(item.get('command'), c)]
            require(len(matching) == 1, 'Command outside the frozen read allowlist')
            key = item['id']
            if method == 'item/started':
                require(key not in commands and matching[0] not in selected_commands, 'Duplicate read start')
                selected_commands.add(matching[0])
                commands[key] = False
            else:
                require(key in commands and not commands[key] and item.get('exitCode') == 0
                        and item.get('status') == 'completed', 'Read command did not complete')
                commands[key] = True
        if method == 'item/completed' and item['type'] == 'userMessage':
            messages.append(item['content'])
        if method == 'item/completed' and item['type'] == 'agentMessage' and item.get('phase') == 'final_answer':
            finals.append(item.get('text'))
    require(len(starts) == 1 and starts == ends, 'Missing/contradictory terminal lifecycle')
    require(len(finals) == 1 and final(finals[0]), 'Recovery final output differs')
    require(len(messages) == 1 and len(messages[0]) == 1 and
            messages[0][0].get('type') == 'text' and
            (prompt(messages[0][0].get('text')) if callable(prompt) else messages[0][0].get('text') == prompt),
            'Capture was not the exact controller-bound read request')
    require(set(required_commands) <= selected_commands and len(commands) == len(selected_commands)
            and all(commands.values()),
            'Incomplete or extra read effects')
    require(times and max(times)-min(times) <= 240, 'Captured turn exceeds original stage limit')
    return dict(turn=starts[0], start=min(times), end=max(times), tools=len(commands),
        sha256=digest(path.read_bytes()))


def receipt_frames(root, role, row):
    """Every received frame must have a validation result; dormant roles run no turn."""
    path = path_checked(root/role/str(row['generation'])/'received-frames.jsonl', root)
    received, validated = {}, set()
    for line in path.read_text().splitlines():
        value = json.loads(line)
        seq = value['sequence']
        if value['phase'] == 'RECEIVED':
            require(seq not in received and value['role'] == role and value['generation'] == row['generation'],
                    'Frame receipt identity/order differs')
            envelope = value['envelope']
            require(not envelope.get('malformed'), 'Malformed received frame')
            if role != 'thinker':
                require(envelope.get('method') not in ('turn/started','turn/completed','item/started','item/completed'),
                        'A dormant role may have executed work')
            received[seq] = envelope
        else:
            require(value['phase'] == 'VALIDATED' and seq in received and seq not in validated,
                    'Unresolved/rejected received frame')
            validated.add(seq)
    require(received and set(received) == validated, 'Incomplete received-frame evidence')
    return dict(path=str(path), sha256=digest(path.read_bytes()), frames=len(received))


def check_service_lock(home):
    service_lock = path_checked(home/'state/service.lock', home)
    if service_lock.exists():
        with service_lock.open('rb') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Rejected('A controller intake service still owns this home') from error
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def retired_terminals(root, registry):
    from types import SimpleNamespace
    from .native import NativeTerminals
    require(not os.path.lexists(root/'terminal-registry.json'), 'Terminal ownership is still active')
    matches = []
    for path in root.glob('terminal-registry-closed-*.json'):
        path_checked(path, root)
        record = json.loads(path.read_text())
        if all(record.get(role, {}).get('thread') == row['thread'] and
                record.get(role, {}).get('generation') == row['generation']
                for role, row in registry.items()):
            matches.append((path, record))
    require(len(matches) == 1, 'Unique closed native frontend ownership required')
    path, record = matches[0]
    require(set(record) == {'thinker','doer','reviewer','_server'} and
            all(process_identity(row['pid']) is None for row in record.values()),
            'A frontend or terminal server is still live or reused')
    socket = None
    if os.path.lexists(root/'ui.sock'):
        socket = NativeTerminals(SimpleNamespace(root=root)).inspect_stale_socket()
        require(socket['prior_record'] == str(path), 'Closed terminal socket has another owner')
    return dict(path=str(path), sha256=digest(path.read_bytes()), retained_socket=socket)


def inspect(config, binding, controller, *, view=None):
    try:
        if isinstance(binding,dict) and type(binding.get('schema')) is int and binding['schema']==2:
            from .native_maintenance_recovery import inspect_precondition
            return inspect_precondition(config,binding,controller,view=view)
        return _inspect(config, binding, controller, view=view)
    except Rejected:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Rejected('Incomplete or malformed completed-read recovery evidence: '+str(error)) from error


def _inspect(config, binding, controller, *, view=None):
    """Pure inspection; no Store initializer, file publication or model startup."""
    require(isinstance(binding, dict) and set(binding) == BINDING_KEYS and
            type(binding['schema']) is int and binding['schema'] == 1, 'Exact read-recovery binding required')
    controller = path_checked(controller)
    require(config.get('controller') == str(controller) and identity(config) == binding['config_hash']
            and identity(tree(controller)) == binding['controller_hash']
            and identity(tree(controller.parent)) == binding['source_hash'], 'Corrected source/config differs')
    file_checked(binding['approval'])
    old_config = json.loads(file_checked(binding['parent_config']).read_text())
    require(config == dict(old_config, controller=str(controller)),
            'Recovery cannot change home, model, budgets, workflow or role inputs')
    old_controller = path_checked(old_config['controller'])
    parent_path = file_checked(binding['parent_receipt'], config['home'])
    parent = json.loads(parent_path.read_text())
    require(parent.get('route') == 'CHECKED_NATIVE_SOURCE_REVISION',
            'Only the reviewed failed source-revision restart is eligible')
    old_binding = parent['maintenance_binding']
    require(identity(old_config) == old_binding['config_hash']
            and identity(tree(old_controller)) == old_binding['controller_hash']
            and identity(tree(old_controller.parent)) == old_binding['source_hash'], 'Failed source/config changed')
    before, after = tree(old_controller.parent), tree(controller.parent)
    changed = {n for n in before.keys() | after.keys() if before.get(n) != after.get(n)}
    allowed = {'controller/loop/native_resume.py','controller/loop/native_read_recovery.py',
        'controller/native_loopctl.py','docs/COMPLETED_READ_RECOVERY.md'}
    require(changed and all(n in after and (n in allowed or n.startswith('controller/tests/test_')
            and n.endswith('.py')) for n in changed), 'Recovery exceeds its bounded implementation scope')
    require(binding['source_hash'] != old_binding['source_hash'], 'Distinct corrected source required')
    if view is None:
        with ReadOnlyState(config['home']) as reader:
            return inspect(config, binding, controller, view=reader)
    home, root = path_checked(config['home']), path_checked(config['settings']['state_dir'])
    from .native_resume import source_revision_binding, projected_source_revision, source_revision_line
    revision = parent['source_revision']
    base_config, base_path, base = source_revision_binding(old_config, revision['binding'], old_controller)
    for name in ('previous_config','previous_receipt','approval'):
        file_checked(revision['binding'][name])
    admission = event(view, revision['admission_event'], 'NATIVE_RUNTIME_SOURCE_REVISION')
    require(admission.get('origin') == 'FOREGROUND_CONTROLLING_TTY'
            and admission.get('binding_hash') == identity(revision['binding'])
            and admission.get('text') == source_revision_line(revision['binding'], base)
            and parent == projected_source_revision(base, revision['binding'], revision['admission_event']),
            'Failed parent lacks its exact committed source authority')
    base_history = StartupJournal(view, base['maintenance_binding']['operation'], base['maintenance_binding']).records()
    require(not unresolved_maintenance(base_history) and any(r['milestone'] == 'RUNTIME_CHECKPOINTED'
            and r['details']['receipt_sha256'] == digest(base_path.read_bytes()) for r in base_history),
            'Original checkpoint authority/uncertainty differs')
    history = StartupJournal(view, old_binding['operation'], old_binding).records()
    require([r['milestone'] for r in history] == ['RUNTIME_RESUME_INTENT','RUNTIME_RESUME_FAILED'],
            'Failed attempt history is not the bounded restart failure')
    intent, failure = history
    require(intent['seq'] == binding['intent_event'] and failure['seq'] == binding['failure_event']
            and all(r['details']['receipt_sha256'] == binding['parent_receipt']['sha256'] for r in history),
            'Consumed intent/failure receipt differs')
    parent_key = identity(dict(parent_receipt_sha256=binding['parent_receipt']['sha256'],
        intent_event=intent['seq'], failure_event=failure['seq']))
    records = authority_records(view, parent_key, binding)
    view.require_current(parent['owner'])
    task = view.task(parent['task'])
    require(task['owner'] == parent['owner'] and task['state'] == 'CANDIDATE_SEALED'
            and task['version'] == parent['task_version'] and task['content_hash'] == parent['packet_hash']
            and identity(task['packet']) == task['content_hash']
            and tree(task['candidate']) == parent['source_before_stop']
            and json.loads(task['seal'])['source_hash'] == identity(parent['source_before_stop']),
            'Current sealed task/owner/packet/candidate differs')
    require(not view.db.execute('SELECT 1 FROM capabilities WHERE owner=? AND enabled=1', (parent['owner'],)).fetchone(),
            'An owner capability is active')
    require(not view.db.execute("SELECT 1 FROM attempts WHERE task=? AND status IN ('SPAWN_INTENT','RUNNING','DISPATCH_UNCERTAIN')", (parent['task'],)).fetchone()
            and not view.db.execute('SELECT 1 FROM decisions WHERE task=?', (parent['task'],)).fetchone(),
            'An active attempt or decision conflicts with recovery')
    require(file_checked(binding['registry'], root) == root/'registry.json'
            and file_checked(binding['supervisor'], root) == root/'supervisor.json', 'Stopped identity files are misplaced')
    registry_raw = (root/'registry.json').read_bytes()
    registry = json.loads(registry_raw)
    require(set(registry) == {'thinker','doer','reviewer'}, 'Exactly three stopped roles required')
    supervisor = json.loads((root/'supervisor.json').read_text())
    require(process_identity(supervisor['pid']) is None
            and supervisor['source'] == old_binding['source_hash']
            and supervisor['maintenance_operation'] == old_binding['operation'], 'Supervisor ownership is unresolved')
    argv = bytes.fromhex(supervisor['cmdline_hex']).rstrip(b'\0').decode().split('\0')
    require(argv[1:] == [str(old_controller/'native_loopctl.py'), '--config', binding['parent_config']['path'],
            'resume-runtime', '--prepared', binding['parent_receipt']['path'],
            '--prepared-sha256', binding['parent_receipt']['sha256']], 'Failed supervisor command differs')
    require(not os.path.lexists(root/'operator.sock') and not os.path.lexists(home/'state/intake.sock')
            and file_checked(dict(path=str(root/'operator.key'),sha256=parent['operator_key_sha256']), root),
            'Operator endpoint/key changed')
    check_service_lock(home)
    frame_proof = {}
    for role, row in registry.items():
        old = parent['registry'][role]
        require(row['generation'] == old['generation']+1 and row['phase'] == 'read'
                and row.get('model') == old.get('model') and row.get('effort') == old.get('effort')
                and process_identity(row['pid']) is None and process_identity(old['pid']) is None
                and not os.path.lexists(root/(role+'.sock')), 'Role generation/phase/process ownership differs')
        if role == 'reviewer':
            require(old['empty'] and row['empty'] and not row['lineage'], 'Reviewer is no longer empty')
        else:
            require(row['thread'] == old['thread'] and row.get('prior_thread') == old['thread']
                    and row['lineage'] == old['lineage']+[dict(old_thread=old['thread'],new_thread=row['thread'],
                        old_generation=old['generation'],new_generation=row['generation'])], 'Role restore lineage differs')
        spec = parent['roles'][role]
        require(tree(path_checked(spec['workspace'], home)) == spec['source']
                and tree(path_checked(spec['inputs'], home)) == spec['input_files'], 'Role source/inputs changed')
        frame_proof[role] = receipt_frames(root, role, row)
    checkpoints = binding['checkpoints']
    require(set(checkpoints) == {'owner','doer','observed_owner'}, 'All original/observed checkpoint hashes required')
    for role, key in [('owner','owner_checkpoint'),('doer','doer_checkpoint')]:
        require(file_checked(checkpoints[role], home) == Path(parent[key]), 'Original checkpoint path differs')
    owner_cp = checkpoint_projection(home, parent['owner_checkpoint'], parent['registry']['thinker'],
        registry['thinker'], Path(parent['owner_checkpoint']).parent/'controller-restart-owner.json')
    require(owner_cp['authority']['questions_answers'] == dict(
        pending=view.questions(parent['owner'],blocking=True), answers=view.human_answers(parent['owner'])),
        'Original answers/questions changed')
    require(checkpoints['observed_owner'] == dict(path=owner_cp['path'],sha256=owner_cp['sha256'])
            and file_checked(checkpoints['observed_owner'], home), 'Observed owner checkpoint differs')
    doer_cp = checkpoint_projection(home, parent['doer_checkpoint'], parent['registry']['doer'],
        registry['doer'], home/'inputs/native-completed-read-recovery'/parent_key/'observed-doer.json')
    rows = view.db.execute('SELECT seq,kind,data FROM events WHERE seq>? AND seq<? ORDER BY seq',
        (intent['seq'],failure['seq'])).fetchall()
    require([r['kind'] for r in rows] == ['NATIVE_CAPABILITY_STAGED_HELD','NATIVE_THINKER_REGISTERED',
        'NATIVE_THINKER_CAPABILITY_HELD','NATIVE_OWNER_DISPATCH','NATIVE_OWNER_DISPATCH'],
        'Unexpected effect during failed restart')
    values = [json.loads(r['data']) for r in rows]
    require(all(v.get('owner') == parent['owner'] for v in values)
            and values[1]['thread'] == registry['thinker']['thread']
            and values[1]['generation'] == registry['thinker']['generation']
            and [v.get('probe') for v in values[-2:]] == [True,False], 'Read-only capability/dispatch lineage differs')
    captures = binding['captures']
    require(set(captures) == {'probe','read'}, 'Both actual captures required')
    review = file_checked(binding['review'])
    with zipfile.ZipFile(review) as archive:
        manifest = json.loads(archive.read('MANIFEST.json'))['files']
        for name, label, dispatch in [('probe','probe',values[-2]),('reread','read',values[-1])]:
            member = 'actual-native/'+name+'-capture-reference.json'
            raw = archive.read(member)
            require(digest(raw) == manifest[member]['sha256'], 'Prior capture reference changed')
            ref = json.loads(raw)
            require(captures[label] == dict(path=ref['original_path'],sha256=ref['original_sha256'])
                    and Path(ref['original_path']) == path_checked(dispatch['capture'], home)/'events.jsonl',
                    'Capture does not match its frozen prior review and committed dispatch')
    from .native import original_read_command, grade_original_reads
    from .native_packet import load, grade_reads, feasibility
    folder = Path(parent['roles']['thinker']['inputs'])/'current-context'
    packet = load(folder)
    plan = feasibility(packet, task['packet'], checks=0, research=0, submission=0,
        finishing_seconds=0, research_seconds=0)
    originals = {'/inputs/current-context/'+s['name']:s['sha256'] for s in packet['sections']}
    expected = dict(owner=parent['owner'], checkpoint=owner_cp['state_sha256'], originals=originals)
    command = original_read_command(originals)
    probe_path, read_path = file_checked(captures['probe'], home), file_checked(captures['read'], home)
    probe = capture_proof(probe_path, registry['thinker'], 'No tools. Final exactly READY.', lambda text:text=='READY')
    read = capture_proof(read_path, registry['thinker'],
        'Read originals using '+command+'\nReturn exactly '+json.dumps(expected),
        lambda text:json.loads(text)==expected, command)
    require(probe['turn'] != read['turn'] and probe['end'] <= read['start']
            and read['end']-probe['start'] <= 240, 'Combined stage/lifecycle order differs')
    require(grade_original_reads(read_path.parent, originals) and not grade_reads(read_path.parent, folder),
            'Not the proved combined-versus-sectioned validation failure')
    terminal_proof = retired_terminals(root, registry)
    cleanup = 0
    for row in view.db.execute('SELECT kind,data FROM events WHERE seq>? ORDER BY seq', (failure['seq'],)):
        value = json.loads(row['data'])
        if row['kind'] == 'NATIVE_CAPABILITY_REVOKED' and value.get('owner') == parent['owner']:
            cleanup += 1
        elif row['kind'] in KINDS:
            require(value.get('parent_key') == parent_key and value.get('parameters_hash') == identity(binding),
                    'A different recovery authority followed this failure')
        elif row['kind'] == 'NATIVE_STARTUP':
            require(value.get('operation') == 'completed-read-'+parent_key,
                    'Another startup followed this failure')
        else:
            raise Rejected('Unexpected effects followed the failed read')
    require(cleanup == 1, 'Exact failed-capability cleanup evidence required')
    prefix = [dict(r) for r in view.db.execute('SELECT * FROM events WHERE seq<=? ORDER BY seq', (failure['seq'],))]
    proof = dict(parent_key=parent_key, parent_receipt=binding['parent_receipt'],
        old_source=old_binding['source_hash'], task=task['id'], owner=task['owner'],
        task_version=task['version'], packet_hash=task['content_hash'],
        candidate_source=identity(parent['source_before_stop']), registry_sha256=digest(registry_raw), registry=registry,
        supervisor=binding['supervisor'], journal_prefix_sha256=identity(prefix),
        probe=probe, read=read, received_frames=frame_proof, retired_terminals=terminal_proof,
        read_plan=plan,
        owner_checkpoint=owner_cp, observed_doer_checkpoint=doer_cp,
        changed_paths=sorted(changed), classification='COMPLETED_READ_VALIDATION_FAILURE',
        rehydration_completed=False, writes_authorized=False)
    require(all(record['data']['proof_hash'] == identity(proof) for record in records.values()),
            'Committed recovery proof differs')
    return dict(parent=parent, registry=registry, registry_raw=registry_raw, proof=proof,
        proof_hash=identity(proof), parent_key=parent_key, records=records)


def confirmation(binding, result):
    return 'recover '+result['parent_key']+' '+binding['source_hash']+' '+result['proof_hash']


def reconcile(store, config, binding, controller):
    with store.lock('native-startup'), store.lock('native-writer'), store.transaction():
        result = inspect(config, binding, controller, view=store)
        found = result['records'].get(KINDS[0])
        if found:
            return found['seq']
        return store.event(result['proof']['task'], KINDS[0], dict(parent_key=result['parent_key'],
            parameters_hash=identity(binding), proof_hash=result['proof_hash'],
            binding=binding, proof=result['proof'], origin='AUTHORIZED_PARENT_EVIDENCE_RECONCILIATION'))


def admit(store, config, binding, controller, text):
    """Exact foreground instruction admits bytes; reconciliation alone cannot."""
    with store.lock('native-startup'), store.lock('native-writer'), store.transaction():
        result = inspect(config, binding, controller, view=store)
        require(KINDS[0] in result['records'], 'Committed read-failure reconciliation required')
        if KINDS[1] in result['records']:
            return result['records'][KINDS[1]]['seq']
        require(text == confirmation(binding, result), 'Exact corrected-source foreground instruction required')
        return store.event(result['proof']['task'], KINDS[1], dict(parent_key=result['parent_key'],
            parameters_hash=identity(binding), proof_hash=result['proof_hash'], binding=binding,
            proof=result['proof'], reconciliation_event=result['records'][KINDS[0]]['seq'],
            origin='FOREGROUND_CONTROLLING_TTY', text=text))


def projection(home, record):
    data, seq = record['data'], record['seq']
    binding, proof = data['binding'], data['proof']
    parent = json.loads(file_checked(binding['parent_receipt'], home).read_text())
    saved = copy.deepcopy(parent)
    saved.update(route=ROUTE, operation=proof['parent_key'], registry_sha256=proof['registry_sha256'],
        registry=copy.deepcopy(proof['registry']),
        owner_checkpoint=proof['owner_checkpoint']['path'],
        doer_checkpoint=proof['observed_doer_checkpoint']['path'], controller_hash=binding['controller_hash'])
    saved['registry_hash'] = identity(saved['registry'])
    saved['maintenance_binding'].update(operation='completed-read-'+proof['parent_key'],
        source_hash=binding['source_hash'], controller_hash=binding['controller_hash'], config_hash=binding['config_hash'])
    if binding.get('schema') == 2:
        saved['operator_key_sha256'] = binding['operator_key']['sha256']
    saved['completed_read_recovery'] = dict(binding=binding, admission_event=seq)
    return saved


def publish(store, binding):
    """Recover exact projections after committed authority, never dispatch."""
    parent = json.loads(file_checked(binding['parent_receipt'], store.home).read_text())
    key = identity(dict(parent_receipt_sha256=binding['parent_receipt']['sha256'], intent_event=binding['intent_event'],
        failure_event=binding['failure_event']))
    with store.lock('native-startup'), store.lock('native-writer'):
        records = authority_records(store, key, binding)
        require(KINDS[0] in records and KINDS[1] in records, 'No committed source admission for publication')
        record = records[KINDS[1]]
        require(record['data']['proof_hash'] == identity(record['data']['proof'])
                and record['data']['proof_hash'] == records[KINDS[0]]['data']['proof_hash'],
                'Committed proof content differs')
        require(record['data']['reconciliation_event'] == records[KINDS[0]]['seq'], 'Reconciliation authority differs')
        cp = record['data']['proof']['observed_doer_checkpoint']
        original, target = Checkpoint(Path(cp['original']), store.home), Checkpoint(Path(cp['path']), store.home)
        derive_checkpoint(original, target, cp['authority'], cp['transition'])
        require(digest(target.path.read_bytes()) == cp['sha256'], 'Observed lineage projection differs')
        saved = projection(store.home, record)
        path = Path(store.home)/'inputs/native-completed-read-recovery'/key/'prepared.json'
        path_checked(path, store.home)
        raw = json.dumps(saved, sort_keys=True).encode()+b'\n'
        atomic(path, raw, exclusive=True)
        return dict(status='COMPLETED_READ_RECOVERY_PREPARED', receipt=str(path), receipt_sha256=digest(raw),
            admission_event=record['seq'], parent_key=key, source=binding['source_hash'],
            model_dispatch='NOT_STARTED', acceptance='NOT_PERFORMED', integration='NOT_PERFORMED')


def inspect_launch(config, path, expected_hash, controller):
    path = file_checked(dict(path=str(path), sha256=expected_hash), config['home'])
    saved = json.loads(path.read_text())
    require(saved.get('route') == ROUTE and set(saved.get('completed_read_recovery', {})) == {'binding','admission_event'},
            'Unsupported completed-read recovery projection')
    binding = saved['completed_read_recovery']['binding']
    with ReadOnlyState(config['home']) as view:
        result = inspect(config, binding, controller, view=view)
        require(KINDS[0] in result['records'] and KINDS[1] in result['records'], 'Orphan receipt has no committed authority')
        record = result['records'][KINDS[1]]
        require(record['seq'] == saved['completed_read_recovery']['admission_event']
                and record['data']['origin'] == 'FOREGROUND_CONTROLLING_TTY'
                and record['data']['text'] == confirmation(binding, result)
                and saved == projection(config['home'], record), 'Receipt differs from exact committed source authority')
        cp = result['proof']['observed_doer_checkpoint']
        file_checked(dict(path=cp['path'],sha256=cp['sha256']), config['home'])
        for name in ('owner_checkpoint','doer_checkpoint'):
            checkpoint = Checkpoint(Path(saved[name]), config['home'])
            checkpoint.validate(json.loads(checkpoint.path.read_text())['state']['authority'])
        journal = StartupJournal(view, saved['maintenance_binding']['operation'], saved['maintenance_binding'])
        require(not journal.records(), 'Recovery launch intent consumed; reconcile actual effects, never retry')
    return saved, result['registry_raw']


def run_cli(config, args, controller):
    from .store import Store
    binding = json.loads(args.binding.read_text())
    if args.command == 'inspect-read-recovery':
        result = inspect(config, binding, controller)
        print(json.dumps(dict(status='COMPLETED_READ_RECOVERY_CHECKED', parent_key=result['parent_key'],
            proof_hash=result['proof_hash'], source=binding['source_hash'],
            reconciled=KINDS[0] in result['records'], admitted=KINDS[1] in result['records'],
            foreground_line=confirmation(binding, result), model_dispatch='NOT_STARTED')))
        return
    if args.command == 'prepare-read-recovery':
        result = inspect(config, binding, controller)
        text = None
        if KINDS[1] not in result['records']:
            from .cli import require_human_tty
            with require_human_tty() as tty:
                tty.write('New corrected-source scope only; failed intent stays consumed.\nType exactly:\n'+confirmation(binding,result)+'\n> ')
                tty.flush()
                text = tty.readline().strip()
        store = Store(Path(config['home']))
        try:
            reconcile(store, config, binding, controller)
            if text is not None:
                admit(store, config, binding, controller, text)
            print(json.dumps(publish(store, binding)), flush=True)
        finally:
            store.close()
        return
    require(args.command == 'publish-read-recovery', 'Unsupported parent read-recovery action')
    store = Store(Path(config['home']))
    try:
        print(json.dumps(publish(store, binding)), flush=True)
    finally:
        store.close()
