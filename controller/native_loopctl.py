#!/usr/bin/env python3
"""Foreground native supervisor. No auto-dispatch or production guard changes."""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import threading
import shutil
import subprocess

from loop.adapter import process_identity
from loop.native import NativeAdapter, NativeIntake, NativeTerminals, capture_complete
from loop.settings import Settings, ROLES
from loop.util import Rejected, atomic, redact, now, tree, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('command', choices=('start', 'status', 'attach', 'stop', 'recontract', 'continue', 'prepare-maintenance', 'recover-startup', 'finish-review', 'maintenance', 'resume-runtime', 'fence-owner-intake'))
    parser.add_argument('--role', choices=ROLES)
    parser.add_argument('--action',choices=('compact-role','replace-role','checkpoint-runtime','reconcile-maintenance'))
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--prepared-sha256')
    parser.add_argument('--defer-review', action='store_true')
    parser.add_argument('--binding', type=Path, help='Frozen native re-contract binding')
    parser.add_argument('--check', action='store_true', help='Check re-contract binding without input or state transition')
    parser.add_argument('--headless', action='store_true', help='Print exact attach commands without opening terminals')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    settings = Settings(**config['settings'])
    root = Path(settings.state_dir).resolve()
    registry = root / 'registry.json'
    owner = root / 'supervisor.json'
    if args.command == 'fence-owner-intake':
        if not args.binding:raise Rejected('Exact stopped owner-intake binding required')
        from loop.native_owner_fence import fence
        print(json.dumps(fence(config,json.loads(args.binding.read_text()),Path(__file__).resolve().parent,check_only=args.check)),flush=True)
        return
    if args.command == 'prepare-maintenance':
        if not args.binding:raise Rejected('Exact native maintenance binding required')
        from loop.native_startup import prepare
        print(json.dumps(prepare(config,json.loads(args.binding.read_text()),Path(__file__).resolve().parent,check_only=args.check)),flush=True)
        return
    if args.command == 'recover-startup':
        if not args.prepared or not args.prepared_sha256:raise Rejected('Exact derived receipt/hash required')
        from loop.native_startup import run_recovery
        return run_recovery(config,args,Path(__file__).resolve().parent)
    if args.command == 'resume-runtime':
        if not args.prepared or not args.prepared_sha256:raise Rejected('Exact runtime checkpoint receipt/hash required')
        from loop.native_resume import run_resume
        return run_resume(config,args,Path(__file__).resolve().parent)
    if args.command == 'maintenance':
        if not args.binding or not args.action:raise Rejected('Bound parent maintenance action required')
        from loop.native_operator import request_review
        print(json.dumps(request_review(root,json.loads(args.binding.read_text()),args.action)),flush=True)
        return
    if args.command == 'finish-review':
        if not args.binding:raise Rejected('Exact sealed review/evidence binding required')
        from loop.native_operator import request_review
        print(json.dumps(request_review(root,json.loads(args.binding.read_text()))),flush=True)
        return
    if args.command == 'continue':
        from loop.native_continuation import run_prepared
        return run_prepared(config, args, Path(__file__).resolve().parent)
    if args.command == 'recontract':
        if not args.binding:
            raise Rejected('--binding is required for native re-contract')
        from loop.store import Store
        from loop.engine import Engine
        from loop.native_continuation import prepare_native_revision
        binding = json.loads(args.binding.read_text())
        if identity(config) != binding['config_hash']:
            raise Rejected('Native continuation configuration binding changed')
        store = Store(Path(config['home']).resolve())
        try:
            result = prepare_native_revision(store, Engine(store,config['workflow']),
                binding, Path(__file__).resolve().parent,
                check_only=args.check)
            print(json.dumps(result,indent=2),flush=True)
        finally:
            store.close()
        return
    if args.command == 'status':
        from loop.native_status import native_status
        print(json.dumps(native_status(root,settings,home=config['home']),indent=2))
        return
    if args.command == 'attach':
        rows=json.loads(registry.read_text())
        if not args.role:raise Rejected('--role required')
        row=rows[args.role]
        command=[settings.executable()]
        command+=['--remote',row['endpoint']] if row.get('empty',True) else ['resume','--remote',row['endpoint'],row['thread']]
        print(shlex.join(command))
        return
    if args.command == 'stop':
        saved = json.loads(owner.read_text())
        pid = saved['pid']
        fd = os.pidfd_open(pid)
        try:
            if process_identity(pid) != saved['process_identity']:
                raise Rejected('Supervisor process identity changed')
            command = Path('/proc/' + str(pid) + '/cmdline').read_bytes()
            if command.hex() != saved['cmdline_hex']:
                raise Rejected('Supervisor command changed')
            signal.pidfd_send_signal(fd, signal.SIGTERM)
        finally:
            os.close(fd)
        print(json.dumps({'status': 'STOP_REQUESTED', 'completion': 'RECONCILE_PROCESS_EXIT'}))
        return
    if not args.headless and not shutil.which('tmux'):
        raise Rejected('Existing tmux required for three terminal slots; use explicit --headless for attach commands')
    from loop.store import Store
    from loop.engine import Engine, COMMON
    from loop.service import capability
    from loop.cli import require_human_tty, snapshot, PROPOSAL_GUIDE
    import uuid
    home = Path(config['home']).resolve()
    workflow = config['workflow']
    store = Store(home)
    engine = Engine(store,workflow,defer_review=args.defer_review)
    adapter = NativeAdapter(engine,settings,evidence_check=capture_complete)
    engine.adapter = adapter
    slots = adapter.slots
    intake = NativeIntake(home,workflow)
    terminals = NativeTerminals(slots,headless=args.headless)
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    lock_path = root / 'supervisor.lock'
    import fcntl
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as ex:
            raise Rejected('Native supervisor already owns this root') from ex
        # Freeze prior rows before writing this supervisor's metadata. Existing
        # ownership is never interpreted as authority to start another task.
        if registry.exists():
            frozen=registry.read_bytes()
            atomic(root/('registry-prestart-'+str(uuid.uuid4())+'.json'),frozen,exclusive=True)
            raise Rejected('Existing three-role registry preserved; restore via checked recovery APIs before new startup')
        atomic(owner, json.dumps({'pid': os.getpid(), 'process_identity': process_identity(os.getpid()),
            'cmdline_hex': Path('/proc/self/cmdline').read_bytes().hex()}))
        try:
            intake.start()
            with require_human_tty() as tty:
                tty.write('New bounded native task request (blank stops):\n> ')
                human_text = tty.readline().strip()
            if not human_text:
                return
            owner_id = str(uuid.uuid4())
            repo = config['roles']['thinker']['workspace']
            workspace,inputs = snapshot(home,repo,owner_id,config=workflow)
            with store.transaction():
                event = store.event(None,'HUMAN_REQUEST',dict(owner=owner_id,text=human_text,origin='FOREGROUND_CONTROLLING_TTY',time=now()))
            request = dict(text=human_text,event=event,origin='FOREGROUND_CONTROLLING_TTY')
            token = adapter.create_held_capability(owner_id,dict(repo=str(Path(repo).resolve()),request=request,key=owner_id+':1'))
            for role in ROLES:
                spec = config['roles'][role]
                slots.start_role(role, workspace if role=='thinker' else spec['workspace'], inputs if role=='thinker' else spec['inputs'],config['controller'],
                    mcp=token if role=='thinker' else None,intake_socket=intake.path if role=='thinker' else None)
            adapter.register_thinker(owner_id,token,held=True)
            terminals.sync(slots.save())
            slots.mapping_changed = terminals.sync
            if not args.headless:
                print(json.dumps({'terminal_attach':terminals.attach_command()}),flush=True)
            print(json.dumps({'status': 'NATIVE_FOREGROUND_CONTROLLER', 'attach': {r: slots.attach(r) for r in ROLES},
                              'limitations': 'Write-profile live qualification and recovery orchestration remain required'}), flush=True)
            adapter.thinker_probe()
            adapter.release_thinker_tools()
            adapter.thinker_turn(COMMON+PROPOSAL_GUIDE+'\nExact foreground request:\n'+human_text)
            task = store.db.execute('SELECT id FROM tasks WHERE owner=?',(owner_id,)).fetchone()
            if not task: raise Rejected('No native scoped submission')
            engine.run(task['id'])
            result = engine.result(task['id'],owner_id)
            if result['state']=='REPORTING':
                from loop.engine import REPORT_SCHEMA
                adapter.thinker_turn(COMMON+'Report this controller-bound result and stop at AWAITING_HUMAN: '+json.dumps(result),report_task=task['id'],schema=REPORT_SCHEMA)
            print(json.dumps(engine.result(task['id'],owner_id),indent=2),flush=True)
            # No next task, acceptance or successor loop. Native terminals remain
            # visible until the operator issues stop or Ctrl-C.
            while not stopped.wait(.2):
                if any(b.error or b.proc.poll() is not None for b in slots.backends.values()):
                    raise Rejected('Backend failed; reconcile recorded lifecycle before restart')
        finally:
            slots.mapping_changed = None
            try:
                adapter.close()
            finally:
                try:
                    terminals.close()
                finally:
                    intake.close()
                    store.close()


if __name__ == '__main__':
    try:
        main()
    except (Rejected, OSError, KeyError, ValueError) as ex:
        print(json.dumps({'status': 'BLOCKED', 'error': str(ex)}), file=sys.stderr)
        raise SystemExit(2)
