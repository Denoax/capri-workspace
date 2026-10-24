#!/usr/bin/env python3
"""Maintainer-only deterministic packet archive build; does not implement CAPRI."""
from pathlib import Path
import hashlib,json,zipfile,shutil

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent

def files():
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if p.is_file() and not any(x in rel.parts for x in ['build','__pycache__']) and rel.as_posix()!='MANIFEST.json':
            if p.is_symlink():raise ValueError('Packet may not contain symlinks')
            yield p

def main():
    entries=[]
    for p in files():
        b=p.read_bytes();entries.append({'path':p.relative_to(ROOT).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    manifest={'schema_version':1,'packet':'CAPRI_SOURCE_MATCH_V1','client_date':'2026-10-23','purpose':'Approved Codex presentation implementation handoff; not a repository patch','observed_main':'521598688be57fdc56a26ff15a4b4eddb65d6433','manifest_self_excluded':True,'files':entries}
    (ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    target=DEST/'CAPRI_SOURCE_MATCH_CODEX_HANDOFF_V1.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
        for p in sorted([*files(),ROOT/'MANIFEST.json']):
            item=zipfile.ZipInfo(ROOT.name+'/'+p.relative_to(ROOT).as_posix(),date_time=(2026,10,23,0,0,0));item.create_system=3;item.external_attr=0o100644<<16;item.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(item,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    prompt=DEST/'CAPRI_SOURCE_MATCH_CODEX_PROMPT_V1.md';shutil.copyfile(ROOT/'CODEX_PROMPT.md',prompt)
    digest=hashlib.sha256(target.read_bytes()).hexdigest();checksum=DEST/(target.name+'.sha256');checksum.write_text(digest+'  '+target.name+'\n')
    print(json.dumps({'archive':str(target),'bytes':target.stat().st_size,'sha256':digest,'payload_files':len(entries),'prompt':str(prompt),'checksum':str(checksum)},indent=2))

if __name__=='__main__':main()
