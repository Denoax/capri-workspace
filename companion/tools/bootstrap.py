#!/usr/bin/env python3
"""Protected native supervisor: one version, one bounded crash rollback, no updater trust key."""
import json
import fcntl
import re
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from versions import Versions,atomic

ROOT=Path(__file__).resolve().parent.parent
manager=Versions(ROOT)

def claim_runtime():
    name=os.environ.get('CAPRI_RUNTIME_NAME','capri')
    if not re.fullmatch(r'capri(?:-test-[a-z0-9]{1,12})?',name):raise SystemExit('Invalid private runtime name')
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache')))/name
    runtime.mkdir(mode=0o700,parents=True,exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_uid!=os.getuid():raise SystemExit('Runtime directory ownership mismatch')
    fd=os.open(runtime/'bootstrap.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd);return runtime,None
    return runtime,fd

def main():
    args=sys.argv[1:] or ['run'];command=args[0]
    if command=='rollback':
        _,ownership=claim_runtime()
        if ownership is None:raise SystemExit('Stop the running Capri service before rollback')
        # Explicit local command; routine health crashes use the separate automatic path.
        result=manager.rollback();print(json.dumps(result));return
    if command=='versions':print(json.dumps(manager.state(),indent=2));return
    if command!='run':
        current=manager.verify(manager.state()['current'])
        raise SystemExit(subprocess.call([sys.executable,str(current/'launcher.py'),*args]))
    runtime,ownership=claim_runtime()
    if ownership is None:
        print('Capri is already running; its version and task state were preserved.');return
    stopping=False;child=None
    def stop(*_):
        nonlocal stopping
        stopping=True
        if child and child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    failures=0
    while not stopping:
        if (ROOT/'bootstrap/session-hook.json').exists():
            from session_start import ready
            if not ready():return
        state=manager.state();digest=state['current'];current=manager.verify(digest)
        # Metadata is authoritative; recover a crash between durable metadata and its symlink projection.
        if not (ROOT/'current').is_symlink() or (ROOT/'current').resolve()!=current:manager.switch(digest)
        env=os.environ.copy();env['CAPRI_VERSION']=digest;env['CAPRI_BOOTSTRAP_PID']=str(os.getpid())
        started=time.monotonic();good=False
        child=subprocess.Popen(['/usr/bin/python3',str(ROOT/'bootstrap/parent_exec.py'),str(os.getpid()),'--',sys.executable,str(current/'launcher.py'),*args],env=env,cwd=current)
        while child.poll() is None and not stopping:
            try:
                health=json.loads((runtime/'health.json').read_text())
                owned=health.get('version')==digest and health.get('launcher_pid')==child.pid
                if owned and health.get('ipc') and health.get('render') and health.get('drafts') and time.monotonic()-started>=30:
                    if not good and (not health.get('account_connected') or health.get('model_catalog')):manager.mark_good(digest);good=True
            except (OSError,ValueError):pass
            time.sleep(.25)
        if stopping:
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            return
        try:health=json.loads((runtime/'health.json').read_text())
        except (OSError,ValueError):health={}
        owned=health.get('version')==digest and health.get('launcher_pid')==child.pid
        if owned and health.get('shutdown_requested'):
            if health.get('restart_requested'):
                failures=0;continue
            return
        if child.returncode==0 and json.loads((current/'version-record.json').read_text()).get('provenance',{}).get('legacy'):
            return
        if (ROOT/'bootstrap/session-hook.json').exists():
            from session_start import ready
            if not ready():return
        failures=failures+1 if time.monotonic()-started<120 else 1
        if failures>=3:
            try:
                result=manager.rollback(automatic=True);atomic(ROOT/'last-rollback.json',result);failures=0
            except ValueError:
                print('Capri stopped after repeated crashes; no unused verified rollback is available.',file=sys.stderr);raise SystemExit(1)
        time.sleep(1)

if __name__=='__main__':main()
