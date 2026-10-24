#!/usr/bin/env python3
"""Copy only hash-pinned data assets. Never load hooks, QML, plugins or external code."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('packet',type=Path)
parser.add_argument('destination',type=Path)
args=parser.parse_args()
manifest=json.loads((Path(__file__).parent.parent/'assets-manifest.json').read_text())
for record in manifest['files']:
    relative=Path(record['path'])
    if relative.is_absolute() or '..' in relative.parts or relative.parts[0]!='assets':
        raise SystemExit('Invalid manifest path')
    source=args.packet/relative
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=record['sha256']:
        raise SystemExit('Asset checksum mismatch: '+str(relative))
    target=args.destination/Path(*relative.parts[1:])
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
print('Imported',len(manifest['files']),'pinned data assets; no executable content.')
