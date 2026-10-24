#!/usr/bin/env python3
"""Register immutable inputs and all derived source-match media, using relative paths."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri/source-match'
def register(media):
    files=[]
    for path in sorted(media.rglob('*')):
        if path.is_file() and path.name!='BUILD_MANIFEST.json':files.append({'path':path.relative_to(media).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (media/'BUILD_MANIFEST.json').write_text(json.dumps({'schema_version':1,'files':files,'scope':'File identities; export provenance/timing are in each timeline. No perceptual acceptance.'},indent=2)+'\n')
    print('Registered',len(files),str(media.relative_to(ROOT))+' files')
def main():
    register(MEDIA)
    story=ROOT/'showcase/capri/story'
    if story.is_dir():register(story)
if __name__=='__main__':main()
