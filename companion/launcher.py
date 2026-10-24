#!/usr/bin/env python3
"""Manual native lifecycle and narrow local controls. No autostart by default."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

BASE=Path(__file__).resolve().parent
RUNTIME=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache')))/'capri'


def control(method):
    import socket
    token=(RUNTIME/'ui.token').read_text()
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(3)
        client.connect(str(RUNTIME/'core.sock'))
        stream=client.makefile('rwb')
        stream.write((json.dumps({'version':1,'role':'observer','token':token})+'\n').encode());stream.flush()
        snapshot=json.loads(stream.readline())
        stream.write((json.dumps({'method':method,'seq':1,'args':{}})+'\n').encode());stream.flush()
        result=json.loads(stream.readline())
        if method=='status':
            return {k:result[k] for k in ('conversation','state','locked','provider','model','sandbox','calls','session_verified')}
        return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['run','stop','quit','status','hide','summon'],nargs='?',default='run')
    parser.add_argument('--assets',type=Path)
    parser.add_argument('--screen',default='')
    parser.add_argument('--evidence-stage',action='store_true',help='Neutral native recording stage; testing only')
    args=parser.parse_args()
    if args.command!='run':
        result=control(args.command)
        if args.command=='quit':
            fd=os.open(RUNTIME/'service.lock',os.O_WRONLY|os.O_NOFOLLOW)
            try:
                for _ in range(100):
                    try:
                        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        fcntl.flock(fd,fcntl.LOCK_UN)
                        break
                    except BlockingIOError:
                        time.sleep(0.05)
                else:raise SystemExit('Core shutdown timed out; do not start a duplicate.')
            finally:os.close(fd)
        print(json.dumps(result,indent=2));return
    if not os.environ.get('WAYLAND_DISPLAY'):
        raise SystemExit('A real Wayland session is required. No X11/browser fallback.')
    data=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'capri'
    assets=args.assets or data/'assets'
    if not (assets/'actor/RIG.json').is_file() or not (assets/'input-regions.json').is_file():
        raise SystemExit('Import the pinned local assets first; see companion/README.md.')
    state=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'capri'
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'capri'
    state.mkdir(parents=True,exist_ok=True,mode=0o700);config.mkdir(parents=True,exist_ok=True,mode=0o700)
    logpath=state/'runtime.log'
    if logpath.exists() and logpath.stat().st_size>2*1024*1024:
        logpath.replace(state/'runtime.previous.log')
    os.umask(0o077)
    log=open(logpath,'a')
    python=Path(os.environ.get('CAPRI_PYTHON',str(data/'venv/bin/python')))
    if not python.is_file():
        raise SystemExit('Create the isolated Python environment first; see companion/README.md.')
    env=os.environ.copy()
    env.update(CAPRI_ASSETS=str(assets.resolve()),CAPRI_SOCKET=str(RUNTIME/'core.sock'),
               CAPRI_SETTINGS=(config/'preferences.ini').as_uri(),CAPRI_SCREEN=args.screen,
               CAPRI_EVIDENCE_STAGE='1' if args.evidence_stage else '0')
    core=subprocess.Popen([str(python),'-B','-m','capri.service'],cwd=BASE,env=env,stdout=log,stderr=log,start_new_session=True)
    shell=None
    try:
        for _ in range(100):
            if core.poll() is not None:
                raise SystemExit('Core failed. Inspect private runtime.log; another Capri instance may own the socket.')
            try:
                control('status');break
            except (OSError,ValueError):time.sleep(0.1)
        else:raise SystemExit('Core readiness timed out')
        env['CAPRI_UI_TOKEN']=(RUNTIME/'ui.token').read_text()
        shell=subprocess.Popen(['/usr/bin/quickshell','-p',str(BASE/'qml/shell.qml'),'--no-duplicate'],env=env,stdout=log,stderr=log)
        # Exit either side together; a disconnected invisible shell must not keep
        # ownership or strand a subsequent launch after core shutdown.
        while shell.poll() is None and core.poll() is None:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if shell and shell.poll() is None:shell.terminate();shell.wait(timeout=5)
        if core.poll() is None:
            core.terminate()
            try:core.wait(timeout=5)
            except subprocess.TimeoutExpired:core.kill();core.wait()
        log.close()


if __name__=='__main__':main()
