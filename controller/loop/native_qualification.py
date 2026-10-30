"""Single-use admission from a stopped fence to a fresh disposable condition.

The original Store owns the admission. A fresh ordinary Engine/Store owns only
the new experiment, never a copy of the old task/answers/decision authority.
The pinned recovery tool and target controller have independent identities.
"""
import contextlib
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import uuid

from .native_startup import StartupJournal, checked_file, run_session
from .native_stopped import (FileBinding, StoppedCompaction, StoppedReadOnlyState,
                             event, inspect, require, scope_line)
from .settings import Settings
from .adapter import process_identity
from .util import Rejected, atomic, digest, identity, safe_path, tree

KIND = 'FRESH_NATIVE_QUALIFICATION'
INTENT = 'NATIVE_DISPOSABLE_QUALIFICATION_INTENT'


def verify_clients(adapter, terminals):
    """Require exact frontend/backend/thread/generation mappings before a turn."""
    rows=adapter.slots.save()
    require(set(rows)==set(adapter.slots.backends)=={'thinker','doer','reviewer'}, 'Exact three native backends required')
    terminals.sync(rows)
    panes=terminals.owned_panes()
    for role,row in rows.items():
        backend=adapter.slots.backends[role];record=terminals.records[role]
        require(len(backend.clients)==1 and backend.proc.poll() is None and
                process_identity(backend.proc.pid)==backend.start_identity and
                row['pid']==backend.proc.pid and row['thread']==backend.thread and row['generation']==backend.generation,
                'Native backend/client identity differs')
        require((record['thread'],record['generation'])==(backend.thread,backend.generation) and
                panes[role]==(record['pane'],str(record['pid']),'0') and
                process_identity(record['pid'])==record['process_identity'], 'Native visible frontend mapping differs')


def checked_terminal_endpoint(case):
    path=Path(case.runtime)/'ui.sock'
    if not os.path.lexists(path):return
    records=[s.json().get('_server',{}) for s in case.terminals]
    st=path.lstat()
    actual=dict(device=st.st_dev,inode=st.st_ino,uid=st.st_uid,ctime_ns=st.st_ctime_ns)
    require(stat.S_ISSOCK(st.st_mode) and st.st_uid==os.getuid() and
            any(r.get('socket_identity')==actual for r in records), 'Unowned retained terminal endpoint')
    # Reading the kernel table creates no socket. A retained unlinked listener
    # or a process holding this path is a hold, never a cleanup opportunity.
    entries=[line.split()[-1] for line in Path('/proc/net/unix').read_text().splitlines()[1:] if len(line.split())>=8]
    require(str(path) not in entries, 'Retained terminal endpoint is still registered')


def parse(value):
    keys = {'schema', 'kind', 'case', 'recovery_controller', 'target_controller_hash',
            'target_config', 'materials', 'request', 'context_packet'}
    require(isinstance(value, dict) and set(value) == keys and
            type(value['schema']) is int and value['schema'] == 1 and value['kind'] == KIND, 'Exact qualification binding required')
    for name in ('case', 'target_config'):
        require(set(value[name]) == {'path', 'sha256'}, 'Exact qualification file binding required')
        FileBinding(**value[name]).read()
    require(isinstance(value['materials'], list) and 0 < len(value['materials']) <= 256, 'Bound original materials required')
    return value


def admission_rows(view, case):
    rows = []
    for row in view.db.execute('SELECT seq,data FROM events WHERE kind=?', (INTENT,)):
        data = json.loads(row['data'])
        if data.get('case_hash') == case.key() or data.get('maintenance_key') == case.maintenance_key:
            require(data.get('case_hash') == case.key(), 'Consumed maintenance key cannot be rebound')
            rows.append(dict(event=row['seq'], **data))
    require(len(rows) <= 1, 'Conflicting qualification launch intents')
    return rows


def load_materials(binding):
    material = {}
    for item in binding['materials']:
        require(set(item) == {'name', 'path', 'sha256'}, 'Exact material binding required')
        name = item['name']; safe_path('/material-root', name)
        require(name not in material, 'Duplicate qualification material')
        material[name] = FileBinding(item['path'], item['sha256']).read()
        # The normal owner/checkpoint/resume inventory retains its 8 MB guard.
        # A larger archive must arrive as ordered parts, not fail after intent.
        require(len(material[name]) <= 8_000_000, 'Qualification material exceeds native per-file snapshot limit: '+name)
        # Bulk source ZIPs are read-only evidence, never inline prompt content.
        # Packet/stage/tool/compaction limits remain unchanged.
        require(sum(map(len,material.values())) <= 32_000_000, 'Original material budget exceeded')
    required = {'REFERENCE_LED_DESIGN.md', 'preserved-requirements.json',
                'original-request.json', 'successor-request.json', 'old-packet.json',
                'historical-prepared.json', 'current-context/INDEX.json'}
    require(required <= set(material), 'Complete preserved/current originals missing')
    require(json.loads(material['successor-request.json']) == binding['request'], 'Qualification request drift')
    from .native_packet import load
    index_path = checked_file(binding['context_packet'])
    index = load(index_path.parent)
    require(material['current-context/INDEX.json'] == index_path.read_bytes(), 'Context index differs')
    for section in index['sections']:
        require(digest(material['current-context/'+section['name']]) == section['sha256'], 'Context section drift')
    for name, record in index['originals'].items():
        require(digest(material[name]) == record['sha256'], 'Authoritative original drift')
    return material, index


def check(old_config, value, controller, *, view=None, require_prepared=True):
    """Pure and initializer-free. Requires a stopped, checkpointed original DB."""
    binding = parse(value)
    case = StoppedCompaction.parse(FileBinding(**binding['case']).json())
    recovery = Path(binding['recovery_controller'])
    require(recovery.is_absolute(), 'Pinned recovery controller must be absolute')
    # Calling the target inspector with the pinned tool path preserves the exact
    # V3 source binding; the target controller is independently checked below.
    stopped = inspect(old_config, case, recovery, view=view)
    checked_terminal_endpoint(case)
    controller = Path(controller).resolve()
    require(str(controller.parent) == case.target_root and
            identity(tree(controller)) == binding['target_controller_hash'], 'Target controller identity differs')
    target = FileBinding(**binding['target_config']).json()
    require(target.get('controller') == str(controller), 'Target configuration controller differs')
    home = Path(target['home']); runtime = target['settings']['state_dir']
    require(home.is_absolute() and home.resolve() == home and home != Path(case.home) and
            home.is_relative_to(case.home), 'Fresh qualification home required')
    require(not os.path.lexists(home), 'Qualification destination exists; never replay startup')
    require(Path(runtime).resolve() == Path(runtime) and Path(runtime).is_relative_to(home) and runtime != case.runtime and
            not os.path.lexists(runtime), 'Fresh private runtime required')
    old_settings = dict(old_config['settings']); new_settings = dict(target['settings'])
    old_settings.pop('state_dir'); new_settings.pop('state_dir')
    require(old_settings == new_settings, 'Role/model/budget/isolation settings must remain unchanged')
    settings = Settings(**target['settings'])
    require(Path(settings.auth_file).is_file(), 'Configured existing authentication mount unavailable')
    require(settings.model == 'gpt-6.1-sol' and settings.efforts ==
            dict(thinker='medium', doer='medium', reviewer='high'), 'Exact three-role model profile required')
    require(max(len(os.fsencode(Path(runtime)/name)) for name in
                ('thinker.sock', 'reviewer.sock', 'operator.sock', 'ui.sock')) < 108, 'Native socket path too long')
    require(Path(settings.executable()).is_file() and
            digest(Path(settings.executable()).read_bytes()) == settings.binary_sha256, 'Pinned executable mismatch')
    require(all(shutil.which(name) for name in ('git', 'bwrap', 'tmux')), 'Supported-host prerequisites unavailable')
    repo = home/'fixtures/source'
    workflow = dict(target['workflow']); old_workflow = dict(old_config['workflow'])
    for name in ('authorized_repositories', 'notes'):
        workflow.pop(name, None); old_workflow.pop(name, None)
    require(workflow == old_workflow and target['workflow']['authorized_repositories'] == [str(repo)] and
            Path(target['workflow']['notes']).resolve() == Path(target['workflow']['notes']) and
            Path(target['workflow']['notes']).is_relative_to(home), 'Fresh workflow cannot broaden authority')
    require(set(target['roles']) == {'thinker', 'doer', 'reviewer'}, 'Exactly three visible roles required')
    for role, spec in target['roles'].items():
        require(set(spec) == {'workspace', 'inputs'} and all(Path(p).is_absolute() and Path(p).resolve() == Path(p) and
                Path(p).is_relative_to(home) for p in spec.values()), 'Role workspace/input must be private')
    material, index = load_materials(binding)
    owner = str(uuid.uuid5(uuid.NAMESPACE_URL, 'capri-qualification:'+case.key()+':'+runtime))
    require(index['binding'].get('owner') == owner and index['binding'].get('repo_source_hash') == case.target_source and
            index['binding'].get('controller_source_hash') == case.target_source and
            index['binding'].get('scope_hash') == digest(scope_line(case, runtime).encode()), 'Fresh context source/owner/scope differs')
    request = binding['request']
    require(request.get('text') == scope_line(case, runtime) and 'lineage' not in request and
            request.get('origin') == 'DERIVED_DISTINCT_FOREGROUND_QUALIFICATION', 'Distinct qualification request required')
    with (StoppedReadOnlyState(case.home) if view is None else contextlib.nullcontext(view)) as state:
        require(not admission_rows(state, case), 'Launch intent consumed; inspect held effects, never retry')
        task = state.task(case.task)
        require(json.loads(material['old-packet.json']) == task['packet'], 'Full original packet differs')
        require(json.loads(material['preserved-requirements.json']) == task['packet']['requirements'], 'N01-N08/SCOPE changed')
        require(json.loads(material['original-request.json']) == task['packet']['request'], 'Original request/corrections differ')
        require(material['historical-prepared.json'] == case.prepared.read(), 'Historical foreground receipt differs')
        core = checked_file(case.prepared.json()['binding']['predecessor_receipt'])
        preserved_answers = json.loads(core.read_text())['prepared']['lineage']['human_answers']
        require(request.get('human_answers', []) == preserved_answers and
                material.get('full-prepared.json') == core.read_bytes(), 'Captured human answers/core lineage differ')
        # The source preparation and launch are separate transitions. The scope
        # event alone never dispatches and the launch intent is single use.
        ready = stopped['fence_event'] is not None and stopped['prepared_event'] is not None
        if require_prepared:
            require(ready, 'Exact stopped fence and distinct source preparation required before launch')
        if stopped['prepared_event']:
            prepared = event(state, stopped['prepared_event'])['data']
            require(prepared.get('origin') == 'FOREGROUND_CONTROLLING_TTY' and
                    prepared.get('scope') == scope_line(case, runtime) and
                    prepared.get('target_runtime') == runtime and prepared.get('target_source') == case.target_source,
                    'Foreground source preparation does not cover this target/runtime')
    return dict(status='FRESH_QUALIFICATION_LAUNCH_CHECKED' if ready else 'FRESH_QUALIFICATION_NEEDS_FOREGROUND',
                case_hash=case.key(), binding_hash=identity(binding), owner=owner, original_repo=str(repo),
                home=str(home), runtime=runtime, target_source=case.target_source,
                target_controller=binding['target_controller_hash'], recovery_source=case.recovery_source,
                fence_event=stopped['fence_event'], prepared_event=stopped['prepared_event'],
                model_dispatch='NOT_STARTED', old_task='PRESERVED_CANDIDATE_SEALED',
                original_requirements=task['packet']['requirements'])


def commit_launch(store, old_config, binding, controller):
    """The existing original Store lock/transaction is the sole admission owner."""
    with store.lock('native-startup'), store.lock('native-writer'), store.transaction():
        plan = check(old_config, binding, controller, view=store)
        case = StoppedCompaction.parse(FileBinding(**binding['case']).json())
        seq = store.event(None, INTENT, dict(case_hash=case.key(), maintenance_key=case.maintenance_key,
            binding_hash=identity(binding), target_source=case.target_source, target_config=binding['target_config'],
            target_home=plan['home'], runtime=plan['runtime'], qualification_owner=plan['owner'],
            fence_event=plan['fence_event'], prepared_event=plan['prepared_event'],
            effect='MAY_CREATE_FRESH_HOME_AND_THREE_VISIBLE_CLIENTS', old_task='UNCHANGED', replay='FORBIDDEN'))
        return dict(plan, admission_event=seq)


def create_source(case, plan):
    """An ordinary fixture Git repository, created only after committed intent."""
    home = Path(plan['home']); home.mkdir(mode=0o700, parents=True, exist_ok=False)
    repo = Path(plan['original_repo'])
    shutil.copytree(case.target_root, repo, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    require(identity(tree(repo)) == case.target_source, 'Target changed during fresh source creation')
    for args in (('-c', 'init.templateDir=', 'init', '--quiet'), ('add', '--all'),
                 ('-c', 'user.name=CAPRI disposable fixture', '-c', 'user.email=fixture@localhost',
                  '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '--quiet', '-m', 'Frozen qualification source')):
        subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
    require(identity(tree(repo)) == case.target_source, 'Git fixture changed target content')


def launch(old_config, binding, controller, args):
    """No automatic retry: even a pre-model crash consumes this exact intent."""
    from .store import Store
    check(old_config, binding, controller)
    case = StoppedCompaction.parse(FileBinding(**binding['case']).json())
    store = Store(case.home)
    try:
        # Hold the original admission lock for the session. There is one old
        # Store writer, and only the normal new Engine owns experiment tasks.
        with store.lock('native-qualification'):
            plan = commit_launch(store, old_config, binding, controller)
            try:
                create_source(case, plan)
                target = FileBinding(**binding['target_config']).json()
                for spec in target['roles'].values():
                    for path in spec.values(): Path(path).mkdir(parents=True, exist_ok=True)
                material, _ = load_materials(binding)
                # Reuse the unchanged session orchestrator and normal submission.
                session = dict(operation='qualification-'+case.key(), owner=plan['owner'], source_hash=case.target_source,
                    controller_hash=binding['target_controller_hash'], config_hash=identity(target),
                    predecessor_receipt=case.prepared.json()['binding']['predecessor_receipt'],
                    fresh_qualification=True, workspace=str(Path(plan['home'])/'snapshots/thinker'),
                    inputs=str(Path(plan['home'])/'inputs/thinker'), registry=asdict(case.registry),
                    context_packet=binding['context_packet'], required_requirements=plan['original_requirements'],
                    verify_visible_clients=True)
                receipt = dict(binding=session, scope_text=binding['request']['text'], admission_event=plan['admission_event'])
                def revalidate():
                    require(identity(tree(controller)) == binding['target_controller_hash'] and
                            identity(tree(case.target_root)) == case.target_source, 'Target source changed after intent')
                    require(FileBinding(**binding['target_config']).json() == target, 'Target config changed after intent')
                    inspect(old_config, case, binding['recovery_controller'], view=store)
                    require(len(admission_rows(store, case)) == 1 and
                            admission_rows(store, case)[0]['binding_hash'] == identity(binding), 'Committed admission differs')
                result = run_session(target, args, controller, receipt, plan, session, material, binding['request'], revalidate)
                with store.transaction():
                    store.event(None, 'NATIVE_DISPOSABLE_QUALIFICATION_STOPPED', dict(case_hash=case.key(),
                        admission_event=plan['admission_event'], classification='INSPECT_NEW_ENGINE_RESULT', next_task='NOT_AUTHORIZED'))
                return result
            except BaseException as ex:
                with store.transaction():
                    store.event(None, 'NATIVE_DISPOSABLE_QUALIFICATION_HELD', dict(case_hash=case.key(),
                        admission_event=plan['admission_event'], error_type=type(ex).__name__,
                        classification='PARTIAL_EFFECTS_REQUIRE_EXPLICIT_RECONCILIATION', retry='FORBIDDEN'))
                raise
    finally:
        store.close()


def run_cli(config, args, controller):
    require(args.binding is not None, 'Bound fresh qualification admission required')
    binding = parse(json.loads(args.binding.read_text()))
    if args.check:
        result=check(config, binding, controller, require_prepared=False)
        print(json.dumps({k:v for k,v in result.items() if k!='original_requirements'}), flush=True)
        return
    require(not args.headless, 'Qualification requires three visible native clients; headless launch forbidden')
    return launch(config, binding, controller, args)
