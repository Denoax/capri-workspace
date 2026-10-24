#!/usr/bin/env python3
"""Create-only user launchers; uninstall only unchanged files registered here."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex

MARKER='CAPRI_DESKTOP_COMPANION_V1_OWNED'
p=argparse.ArgumentParser()
p.add_argument('--prefix',type=Path,default=Path.home())
p.add_argument('--uninstall',action='store_true')
p.add_argument('--autostart',action='store_true',help='Explicit opt-in; requires a qualified graphical user-manager environment')
a=p.parse_args()
prefix=a.prefix.resolve()
base=Path(__file__).resolve().parent.parent
launcher=prefix/'.local/bin/capri'
desktop=prefix/'.local/share/applications/capri.desktop'
unit=prefix/'.config/systemd/user/capri-companion.service'
manifest=prefix/'.local/share/capri/install.json'
allowed=(launcher,desktop,unit)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
if a.uninstall:
    record=json.loads(manifest.read_text())
    for path in allowed:
        key=str(path)
        if key not in record['files']:continue
        if path.is_symlink() or (path.exists() and digest(path)!=record['files'][key]):
            raise SystemExit('Preserving changed installation file: '+key)
    if prefix == Path.home().resolve() and str(unit) in record['files']:
        import subprocess
        fragment=subprocess.run(['systemctl','--user','show','-p','FragmentPath','--value','capri-companion.service'],capture_output=True,text=True)
        if fragment.stdout.strip() not in ('',str(unit)):
            raise SystemExit('A different unit owns this name; preserving installation')
        subprocess.run(['systemctl','--user','disable','--now','capri-companion.service'],check=True)
    for path in allowed:
        if str(path) in record['files']:path.unlink(missing_ok=True)
    if prefix == Path.home().resolve():
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    manifest.unlink()
    print('Removed unchanged Capri launcher/desktop/unit. Conversation, credentials, assets and user data retained.')
    raise SystemExit(0)
python=Path(os.environ.get('CAPRI_PYTHON',str(Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'capri/venv/bin/python')))
if not python.exists():raise SystemExit('Create the isolated Python environment first')
if any(path.exists() or path.is_symlink() for path in (*allowed,manifest)):
    raise SystemExit('Existing installation paths preserved; inspect them before replacing anything')
texts={
 launcher:'#!/bin/sh\n# '+MARKER+'\nexec '+shlex.quote(str(python))+' '+shlex.quote(str(base/'launcher.py'))+' "$@"\n',
 desktop:'[Desktop Entry]\n# '+MARKER+'\nType=Application\nName=Capri\nComment=Native local desktop companion\nExec="'+str(launcher)+'" run\nTerminal=false\nCategories=Utility;\n',
 unit:'# '+MARKER+'\n[Unit]\nDescription=Capri native companion\nAfter=graphical-session.target\nPartOf=graphical-session.target\nConditionEnvironment=WAYLAND_DISPLAY\n\n[Service]\nType=simple\nExecStart="'+str(launcher)+'" run\nRestart=on-failure\nRestartSec=3\nUMask=0077\n\n[Install]\nWantedBy=graphical-session.target\n'}
created=[]
try:
    for path,text in texts.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o755 if path==launcher else 0o644)
        with os.fdopen(fd,'w') as stream:stream.write(text)
        created.append(path)
    manifest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with manifest.open('x') as stream:json.dump({'marker':MARKER,'source':str(base),'files':{str(path):digest(path) for path in created}},stream,indent=2)
except BaseException:
    for path in created:path.unlink()
    raise
print('Installed:',launcher,'; optional unit generated, autostart OFF')
if a.autostart:
    import subprocess
    if not os.environ.get('WAYLAND_DISPLAY'):raise SystemExit('Autostart not enabled: Wayland environment unavailable')
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable','capri-companion.service'],check=True)
    print('Autostart enabled by explicit request; graphical-session restart still needs qualification.')
