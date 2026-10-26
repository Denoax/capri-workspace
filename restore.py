"""Verify and recover the private Capri artifact snapshot into a fresh directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Unsafe snapshot path: ' + name)
    return Path(*p.parts)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--source-git', type=Path, default=ROOT / '.git')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--prefix', default='')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not args.verify_only and args.destination is None:
        parser.error('--destination is required unless --verify-only is set')
    if args.destination and args.destination.exists():
        parser.error('Destination must not already exist')
    rows = json.loads((ROOT / 'snapshot/files.json').read_text())
    rows = [v for v in rows if v['path'].startswith(args.prefix)]
    if not rows:
        parser.error('Prefix matched no paths')
    for row in rows:
        relative(row['path'])
    index = json.loads((ROOT / 'snapshot/pack-index.json').read_text())
    packs = json.loads((ROOT / 'snapshot/packs.json').read_text())
    needed = {v['sha256'] for v in rows if v.get('provider', {}).get('kind') == 'archive-object'}
    needed_packs = {index[v]['pack'] for v in needed}
    cache = args.assets / 'verified-objects'
    if not args.verify_only:
        cache.mkdir(parents=True, exist_ok=True)
    checked = 0
    for pack in packs:
        if pack['name'] not in needed_packs:
            continue
        path = args.assets / pack['name']
        if path.stat().st_size != pack['bytes'] or digest(path) != pack['sha256']:
            raise ValueError('Compressed checksum mismatch: ' + pack['name'])
        process = subprocess.Popen(['zstd', '-q', '-d', '-c', '--', str(path)], stdout=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for member in archive:
                    parts = PurePosixPath(member.name).parts
                    if not member.isfile() or len(parts) != 2 or parts[0] != 'objects':
                        raise ValueError('Unexpected archive member')
                    key = parts[1]
                    if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                        raise ValueError('Invalid object name')
                    if key not in index or index[key]['pack'] != pack['name'] or member.size != index[key]['bytes']:
                        raise ValueError('Object is not bound to this pack')
                    stream = archive.extractfile(member)
                    h = hashlib.sha256()
                    target = cache / key
                    if key in needed and not args.verify_only and target.exists():
                        if target.is_symlink() or digest(target) != key:
                            raise ValueError('Existing object cache is unsafe or corrupt')
                    output = target.open('xb') if key in needed and not args.verify_only and not target.exists() else None
                    try:
                        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                            h.update(block)
                            if output:
                                output.write(block)
                    finally:
                        if output:
                            output.close()
                    if h.hexdigest() != key:
                        raise ValueError('Expanded object checksum mismatch')
                    checked += 1
            process.stdout.close()
            if process.wait() != 0:
                raise RuntimeError('zstd decoding failed')
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
        print(json.dumps({'verified_pack': pack['name']}), flush=True)
    if args.verify_only:
        print(json.dumps({'status':'PASS', 'verified_objects':checked, 'matched_paths':len(rows)}))
        return
    args.destination.mkdir(parents=True)
    links = []
    for row in rows:
        target = args.destination / relative(row['path'])
        if row['kind'] == 'symlink':
            links.append(row)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if row['provider']['kind'] == 'git-blob':
            raw = subprocess.check_output(['git', '--git-dir', str(args.source_git), 'cat-file', 'blob', row['provider']['sha1']])
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Git blob checksum mismatch')
            with target.open('xb') as output:
                output.write(raw)
        else:
            source = cache / row['sha256']
            with source.open('rb') as stream, target.open('xb') as output:
                shutil.copyfileobj(stream, output)
        if digest(target) != row['sha256']:
            raise ValueError('Restored checksum mismatch')
        target.chmod(row['mode'])
    (args.destination / 'RECORDED_EXTERNAL_LINKS.json').write_text(json.dumps(links, indent=2) + '\n')
    print(json.dumps({'status':'PASS', 'restored_files':len(rows)-len(links), 'recorded_links':len(links)}))

if __name__ == '__main__':
    main()
