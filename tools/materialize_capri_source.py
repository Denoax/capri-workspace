#!/usr/bin/env python3
"""Materialize the original verified kit outside the bounded runtime checkout."""
from pathlib import Path
import argparse,hashlib,json
from capri_source_storage import ROOT,SOURCE,read_source

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();out=a.output.resolve()
    if out.is_relative_to(ROOT):raise ValueError('Choose an output outside the runtime checkout (its source snapshot limit is8MB per file).')
    manifest=json.loads((SOURCE/'MANIFEST.json').read_text());out.mkdir(parents=True,exist_ok=True)
    for item in manifest['files']:
        data=read_source(item['path'])
        if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Original hash mismatch: '+item['path'])
        dest=out/item['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes()!=data:raise FileExistsError('Refuse to overwrite changed materialized source: '+str(dest))
        dest.write_bytes(data)
    (out/'MANIFEST.json').write_bytes((SOURCE/'MANIFEST.json').read_bytes())
    print('Materialized157 exact source files plus original manifest:',out)
if __name__=='__main__':main()
