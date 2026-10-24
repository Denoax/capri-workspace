#!/usr/bin/env python3
"""Adopt only a verified owned V1 install, or create a fresh reversible V2 install."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

BASE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(BASE))
from capri.versions import Versions,atomic

MARKER='CAPRI_DESKTOP_COMPANION_V2_OWNED'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def replace(path,data,mode):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.capri-new')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def install_session_hook(config,bootstrap,python):
    config=Path(config);record=bootstrap/'session-hook.json'
    if config.is_symlink() or not config.is_file() or record.exists():raise SystemExit('Existing or unsupported session hook preserved')
    original=config.read_bytes()
    if len(original)>2*1024*1024:raise SystemExit('Hyprland configuration exceeds startup hook bound')
    begin='-- BEGIN CAPRI_DESKTOP_V2_AUTOSTART'
    if begin.encode() in original:raise SystemExit('Existing Capri startup fragment preserved')
    start=json.dumps(shlex.join([str(python),str(bootstrap/'session_start.py'),'start']))
    stop=json.dumps(shlex.join([str(python),str(bootstrap/'session_start.py'),'stop']))
    block=('\n'+begin+'\nhl.on("hyprland.start", function()\n    hl.exec_cmd('+start+')\nend)\n'
           'hl.on("hyprland.shutdown", function()\n    hl.exec_cmd('+stop+')\nend)\n-- END CAPRI_DESKTOP_V2_AUTOSTART\n')
    replace(config,original+block.encode(),config.stat().st_mode&0o777)
    atomic(record,{'path':str(config),'block':block,'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':digest(config)})
    return str(config)

def remove_session_hook(bootstrap,*,check=False):
    record=bootstrap/'session-hook.json'
    if not record.exists():return
    value=json.loads(record.read_text());path=Path(value['path']);block=value['block'].encode()
    if path.is_symlink() or not path.is_file():raise SystemExit('Changed startup configuration preserved')
    current=path.read_bytes()
    if current.count(block)!=1:raise SystemExit('Changed Capri startup fragment preserved; remove it explicitly before uninstall')
    if not check:
        replace(path,current.replace(block,b'',1),path.stat().st_mode&0o777);record.unlink()

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',type=Path,default=Path.home());p.add_argument('--baseline',type=Path);p.add_argument('--sha',default='local-content-bound');p.add_argument('--baseline-sha',default='');p.add_argument('--uninstall',action='store_true');p.add_argument('--autostart',action='store_true');a=p.parse_args()
    home=a.prefix.resolve();actual=home==Path.home().resolve();data=Path(os.environ.get('XDG_DATA_HOME',str(home/'.local/share')))/'capri' if actual else home/'.local/share/capri'
    launcher=home/'.local/bin/capri';desktop=home/'.local/share/applications/capri.desktop';unit=home/'.config/systemd/user/capri-companion.service';owned=(launcher,desktop,unit)
    manifest=data/'install.json';backup=data/'bootstrap/original-install.json'
    if a.uninstall:
        record=json.loads(manifest.read_text())
        if record.get('marker')!=MARKER:raise SystemExit('This is not an owned V2 installation')
        for path in owned:
            if path.is_symlink() or not path.exists() or digest(path)!=record['files'][str(path)]:raise SystemExit('Changed owner file preserved: '+str(path))
        remove_session_hook(data/'bootstrap',check=True)
        if actual:
            subprocess.run(['systemctl','--user','disable','--now','capri-companion.service'],check=True)
        remove_session_hook(data/'bootstrap')
        original=json.loads(backup.read_text())
        for path in owned:
            if str(path) in original['files']:replace(path,original['files'][str(path)].encode(),0o755 if path==launcher else 0o644)
            else:path.unlink()
        if original['manifest'] is None:manifest.unlink()
        else:atomic(manifest,original['manifest'])
        if actual:subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        print('V2 launch registration removed; prior owned registration restored where present. Private state, account, drafts, assets and version history retained.');return
    if manifest.exists():
        previous=json.loads(manifest.read_text())
        if previous.get('marker')!='CAPRI_DESKTOP_COMPANION_V1_OWNED':raise SystemExit('Existing non-V1 registration preserved; use native version review for V2 updates')
        for path in owned:
            if path.is_symlink() or not path.is_file() or previous['files'].get(str(path))!=digest(path):raise SystemExit('Existing owner file changed; installation preserved: '+str(path))
        if not a.baseline or not a.baseline_sha:raise SystemExit('Adoption requires the verified V1 source and commit identity')
    else:
        previous=None
        if any(p.exists() or p.is_symlink() for p in owned):raise SystemExit('Unregistered launch files preserved')
    manager=Versions(data);bootstrap=data/'bootstrap';bootstrap.mkdir(mode=0o700,exist_ok=True)
    if backup.exists():raise SystemExit('An adoption backup already exists; inspect the previous attempt rather than overwrite it')
    atomic(backup,{'manifest':previous,'files':{str(p):p.read_text() for p in owned if p.exists()}})
    python=Path(os.environ.get('CAPRI_PYTHON',str(data/'venv/bin/python')))
    if not python.is_file():raise SystemExit('Create the isolated Capri Python environment before installing')
    for name,source in [('bootstrap.py',BASE/'tools/bootstrap.py'),('versions.py',BASE/'capri/versions.py'),('parent_exec.py',BASE/'capri/parent_exec.py'),('session_start.py',BASE/'tools/session_start.py')]:
        replace(bootstrap/name,source.read_bytes(),0o500)
    if a.baseline:
        baseline=manager.stage(a.baseline,{'legacy':True,'git_sha':a.baseline_sha,'source':str(a.baseline),'authority':'Imported existing V1 baseline from explicit owner V2 brief'})
        manager.activate(baseline,origin='owner-ui');manager.mark_good(baseline)
    candidate=manager.stage(BASE,{'git_sha':a.sha,'source':str(BASE),'authority':'Initial V2 implementation explicitly requested by owner'})
    texts={launcher:'#!/bin/sh\n# '+MARKER+'\nexec '+shlex.quote(str(python))+' '+shlex.quote(str(bootstrap/'bootstrap.py'))+' "$@"\n',desktop:'[Desktop Entry]\n# '+MARKER+'\nType=Application\nName=Capri\nComment=Native resident companion\nExec="'+str(launcher)+'" run\nTerminal=false\nCategories=Utility;\n',unit:'# '+MARKER+'\n[Unit]\nDescription=Capri native companion\nAfter=graphical-session.target\nPartOf=graphical-session.target\nConditionEnvironment=WAYLAND_DISPLAY\nStartLimitIntervalSec=120\nStartLimitBurst=3\n\n[Service]\nType=simple\nExecCondition="'+str(python)+'" "'+str(bootstrap/'session_start.py')+'" --check\nExecStart="'+str(launcher)+'" run\nRestart=on-failure\nRestartSec=5\nKillMode=control-group\nTimeoutStopSec=15\nUMask=0077\n\n[Install]\nWantedBy=graphical-session.target\n'}
    try:
        for path,text in texts.items():replace(path,text.encode(),0o755 if path==launcher else 0o644)
        atomic(manifest,{'marker':MARKER,'source':str(BASE),'candidate':candidate,'files':{str(p):digest(p) for p in owned},'bootstrap':{str(p):digest(p) for p in bootstrap.iterdir() if p.is_file()},'private_state':'retained'})
        manager.activate(candidate,origin='owner-ui')
    except BaseException:
        original=json.loads(backup.read_text())
        for path in owned:
            if str(path) in original['files']:replace(path,original['files'][str(path)].encode(),0o755 if path==launcher else 0o644)
            else:path.unlink(missing_ok=True)
        if previous:atomic(manifest,previous)
        else:manifest.unlink(missing_ok=True)
        raise
    if a.autostart:
        if not actual or not os.environ.get('WAYLAND_DISPLAY'):raise SystemExit('Enable autostart only in the qualified real graphical session')
        graphical=subprocess.run(['systemctl','--user','is-active','graphical-session.target'],capture_output=True).returncode==0
        if not graphical and os.environ.get('XDG_CURRENT_DESKTOP')=='Hyprland':
            hook=install_session_hook(home/'.config/hypr/hyprland.lua',bootstrap,python)
            registration=json.loads(manifest.read_text());registration['session_hook']=hook
            registration['bootstrap']={str(p):digest(p) for p in bootstrap.iterdir() if p.is_file()};atomic(manifest,registration)
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        subprocess.run(['systemctl','--user','import-environment','WAYLAND_DISPLAY','XDG_CURRENT_DESKTOP','HYPRLAND_INSTANCE_SIGNATURE','XDG_SESSION_TYPE'],check=True)
        subprocess.run(['systemctl','--user','enable','capri-companion.service'],check=True)
    print(json.dumps({'launcher':str(launcher),'current':candidate,'rollback':str(launcher)+' rollback','autostart':a.autostart,'running_source':'Existing process unchanged until explicit qualified restart'}))

if __name__=='__main__':main()
