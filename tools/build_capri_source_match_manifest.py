#!/usr/bin/env python3
"""Register immutable inputs and all derived source-match media, using relative paths."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri/source-match'
def register(media):
    files=[]
    for path in sorted(media.rglob('*')):
        if path.is_file() and path.name!='BUILD_MANIFEST.json':files.append({'path':path.relative_to(media).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    record={'schema_version':1,'files':files,'scope':'File identities; export provenance/timing are in each timeline. No perceptual acceptance.'}
    if (media/'story.json').exists():
        configuration=json.loads((media/'story.json').read_text());active=[]
        for name,lesson in configuration['lessons'].items():
            for layout in lesson['layouts']:
                active.append(f'exports/{name}-{layout}.png')
                if not lesson.get('static_only') and layout not in lesson.get('static_layouts',[]):active.extend([f'exports/{name}-{layout}.gif',f'exports/{name}-{layout}-timeline.json'])
        record['active_exports']=active
        record['root_exports']=[f"exports/{name}-{lesson['root_layout']}.{'png' if lesson.get('static_only') or lesson['root_layout'] in lesson.get('static_layouts',[]) else 'gif'}" for name,lesson in configuration['lessons'].items()]
        record['historical_exports']=[item['path'] for item in files if item['path'].startswith('exports/') and item['path'] not in active]
    (media/'BUILD_MANIFEST.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Registered',len(files),str(media.relative_to(ROOT))+' files')
def main():
    register(MEDIA)
    story=ROOT/'showcase/capri/story'
    if story.is_dir():register(story)
if __name__=='__main__':main()
