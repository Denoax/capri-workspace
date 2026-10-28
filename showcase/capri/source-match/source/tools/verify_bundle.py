#!/usr/bin/env python3
"""Read-only packet integrity check. Not runtime, browser or aesthetic acceptance."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,sys,zipfile,tempfile

ROOT=Path(__file__).resolve().parents[1]

def check(root):
    root=root.resolve();manifest=json.loads((root/'MANIFEST.json').read_text());expected={}
    for row in manifest['files']:
        name=row['path'];path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or name in expected:raise ValueError('Unsafe or duplicate manifest path: '+name)
        expected[name]=row
    actual={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and 'build' not in p.relative_to(root).parts and '__pycache__' not in p.relative_to(root).parts}
    actual.pop('MANIFEST.json',None)
    if set(actual)!=set(expected):raise ValueError('File inventory differs: missing='+str(sorted(set(expected)-set(actual)))+' extra='+str(sorted(set(actual)-set(expected))))
    for name,row in expected.items():
        p=actual[name]
        if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Symlink or escaping file: '+name)
        b=p.read_bytes()
        if len(b)!=row['bytes'] or hashlib.sha256(b).hexdigest()!=row['sha256']:raise ValueError('Content mismatch: '+name)
    if (root/'CODEX_PROMPT.md').stat().st_size<1000:raise ValueError('Missing task authority')
    data=json.loads((root/'assets/data/context-budget.json').read_text());totals=[sum(x['values']) for x in data['series']]
    if totals!=[180000,90000,60000] or data['measured_capri_savings'] is not None:raise ValueError('Illustration contract differs')
    rig=json.loads((root/'assets/characters/rig/rig-assets.json').read_text())
    if len(rig['parts'])!=10 or len(rig['keys'])<3:raise ValueError('Rig source is incomplete')
    print(json.dumps({'status':'PASS','files':len(expected),'payload_bytes':sum(x['bytes'] for x in expected.values()),'scope':'Packet inventory/hashes, editable assumptions and rig presence; not runtime or visual acceptance'},indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--zip',type=Path);args=p.parse_args()
    if args.zip:
        with tempfile.TemporaryDirectory(prefix='capri-packet-') as folder:
            dest=Path(folder)
            with zipfile.ZipFile(args.zip) as z:
                for member in z.infolist():
                    path=PurePosixPath(member.filename)
                    if path.is_absolute() or '..' in path.parts or '\\' in member.filename:raise ValueError('Unsafe archive path')
                    if (member.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive contains a symlink')
                bad=z.testzip()
                if bad:raise ValueError('ZIP CRC error: '+bad)
                z.extractall(dest)
            roots=[x for x in dest.iterdir() if x.is_dir()]
            if len(roots)!=1:raise ValueError('Expected one packet root')
            check(roots[0])
    else:check(args.root)
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as e:print('FAIL:',e,file=sys.stderr);raise SystemExit(1)
