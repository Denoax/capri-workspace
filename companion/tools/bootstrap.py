#!/usr/bin/env python3
"""Protected native supervisor: one version, one bounded crash rollback, no updater trust key."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from versions import Versions,atomic

ROOT=Path(__file__).resolve().parent.parent
manager=Versions(ROOT)

def main():
    args=sys.argv[1:] or ['run'];command=args[0]
    if command=='rollback':
        # Explicit local command; routine health crashes use the separate automatic path.
        result=manager.rollback();print(json.dumps(result));return
    if command=='versions':print(json.dumps(manager.state(),indent=2));return
    if command!='run':
        current=manager.verify(manager.state()['current'])
        raise SystemExit(subprocess.call([sys.executable,str(current/'launcher.py'),*args]))
    stopping=False;child=None
    def stop(*_):
        nonlocal stopping
        stopping=True
        if child and child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    failures=0
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache')))/os.environ.get('CAPRI_RUNTIME_NAME','capri')
    while not stopping:
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
        failures=failures+1 if time.monotonic()-started<120 else 1
        if failures>=3:
            try:
                result=manager.rollback(automatic=True);atomic(ROOT/'last-rollback.json',result);failures=0
            except ValueError:
                print('Capri stopped after repeated crashes; no unused verified rollback is available.',file=sys.stderr);raise SystemExit(1)
        time.sleep(1)

if __name__=='__main__':main()
