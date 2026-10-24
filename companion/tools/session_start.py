#!/usr/bin/env python3
"""Registered plain-Hyprland startup hook; no persistent process or new authority."""
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys

MARKER='CAPRI_DESKTOP_COMPANION_V2_OWNED'
ROOT=Path(__file__).resolve().parent.parent

def ready():
    try:
        runtime=Path(os.environ['XDG_RUNTIME_DIR']);display=os.environ['WAYLAND_DISPLAY']
        path=Path(display) if Path(display).is_absolute() else runtime/display
        if path.parent.resolve()!=runtime.resolve() or path.is_symlink():return False
        info=path.stat()
        if info.st_uid!=os.getuid() or not stat.S_ISSOCK(info.st_mode):return False
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(.3);connection.connect(str(path))
        return True
    except (KeyError,OSError,ValueError):return False

def main():
    action=sys.argv[1] if len(sys.argv)>1 else 'start'
    if action=='--check':raise SystemExit(0 if ready() else 1)
    if action not in ('start','stop'):raise SystemExit('Unsupported Capri session operation')
    try:owned=json.loads((ROOT/'install.json').read_text()).get('marker')==MARKER
    except (OSError,ValueError):owned=False
    if not owned:return
    if action=='start':
        if not ready():raise SystemExit('Current Wayland session is unavailable')
        names=[k for k in ('WAYLAND_DISPLAY','HYPRLAND_INSTANCE_SIGNATURE','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE') if k in os.environ]
        subprocess.run(['systemctl','--user','import-environment',*names],check=True)
        subprocess.run(['systemctl','--user','reset-failed','capri-companion.service'],check=True)
    subprocess.run(['systemctl','--user',action,'capri-companion.service'],check=True)

if __name__=='__main__':main()
