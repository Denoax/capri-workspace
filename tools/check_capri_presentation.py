#!/usr/bin/env python3
"""Focused documentation/media checks; no controller launch or aesthetic score."""
from pathlib import Path
from urllib.parse import unquote,urlsplit
import hashlib,json,re,sys
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'showcase/capri'


def embedded_images(text):
    return re.findall(r'(?:src|srcset)="([^"]+)"',text)+re.findall(r'!\[[^\]]*\]\(([^\s)]+)\)',text)


def main():
    errors=[];links=0
    for path in [ROOT/'README.md',*sorted((ROOT/'docs').glob('*.md'))]:
        text=path.read_text();targets=re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)',text)+re.findall(r'(?:src|srcset|href)="([^"]+)"',text)
        for target in targets:
            url=urlsplit(target)
            if url.scheme or url.netloc:continue
            dest=(path.parent/unquote(url.path)).resolve() if url.path else path
            if not dest.is_relative_to(ROOT) or not dest.exists():errors.append(f'Broken link: {path.name} -> {target}')
            elif url.fragment and dest.suffix=='.md':
                headings=re.findall(r'^#{1,6}\s+(.+)$',dest.read_text(),re.M)
                slugs={re.sub(r'[^\w\- ]','',h.lower()).replace(' ','-') for h in headings}
                # The editorial README uses documented custom anchors for image headings.
                slugs.update(re.findall(r'<a\s+(?:id|name)="([^"]+)"',dest.read_text()))
                if url.fragment not in slugs:errors.append(f'Broken heading: {path.name} -> {target}')
            links+=1
    for path in [ROOT/'docs/README_STATIC.md',ROOT/'docs/AFTERIMAGE_STATIC.md']:
        if any(urlsplit(x).path.lower().endswith('.gif') for x in embedded_images(path.read_text())):
            errors.append('Static edition embeds animated media: '+path.name)
    root_motion=[x for x in embedded_images((ROOT/'README.md').read_text()) if urlsplit(x).path.endswith('.gif')]
    if root_motion!=['showcase/capri/hero.gif']:errors.append('Root README must retain only the approved hero loop')
    sources=json.loads((MEDIA/'SOURCES.json').read_text());selected=sources['selected']
    recipe=json.loads((MEDIA/'afterimage/COMPOSITION.json').read_text())
    added_ids={x['source'] for x in recipe['stills'].values()}|{recipe['motion']['source']}
    expected={'sources/capri-12.gif','sources/capri-19.gif'}|{f'sources/capri-{n}.gif' for n in added_ids}
    if len(added_ids)<3:errors.append('Art studies need three recorded source selections')
    if len({x['candidate_path'] for x in selected})!=len(selected):errors.append('Duplicate selected source record')
    if {x['candidate_path'] for x in selected}!=expected:errors.append('Branding sources differ from the recorded recipe')
    for source in selected:
        path=MEDIA/source['candidate_path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:errors.append('Source hash mismatch: '+path.name)
        if path.stat().st_size!=source['bytes']:errors.append('Source byte count mismatch: '+path.name)
        with Image.open(path) as im:
            duration=0
            for i in range(im.n_frames):im.seek(i);im.load();duration+=im.info.get('duration',0)
            if list(im.size)!=source['dimensions'] or im.n_frames!=source['frames'] or duration!=source['duration_ms']:
                errors.append('Source dimensions/timing mismatch: '+path.name)
    if hashlib.sha256((MEDIA/'hero.gif').read_bytes()).hexdigest()!=sources['approved_hero_sha256']:
        errors.append('Approved hero changed')
    assets=[]
    for name in ['hero.gif','hero.png','workflow.png','social.png']:
        p=MEDIA/name
        with Image.open(p) as im:
            total=0
            for i in range(im.n_frames):im.seek(i);im.load();total+=im.info.get('duration',0)
            assets.append({'path':name,'size':list(im.size),'bytes':p.stat().st_size,'frames':im.n_frames,'duration_ms':total})
            if name=='hero.gif' and (im.size!=(1000,343) or total!=4000 or im.info.get('loop')!=0):errors.append('Hero delivery/timing mismatch')
            if name=='social.png' and (im.size!=(1280,640) or p.stat().st_size>=1000000):errors.append('Social card target mismatch')
    for name in ['hero.svg','hero-overlay.svg','workflow.svg','social.svg']:
        if '<text' in (MEDIA/name).read_text():errors.append('Unoutlined display text: '+name)
    if not (MEDIA/'fonts/OFL.txt').is_file():errors.append('Missing font notice')
    for name in ['expression.png','gesture.png','movement.png','interlude.png','interlude.gif']:
        path=MEDIA/'afterimage'/name
        with Image.open(path) as im:
            duration=0
            for i in range(im.n_frames):im.seek(i);im.load();duration+=im.info.get('duration',0)
            assets.append({'path':'afterimage/'+name,'size':list(im.size),'bytes':path.stat().st_size,'frames':im.n_frames,'duration_ms':duration})
            if name=='interlude.gif' and (list(im.size)!=recipe['motion']['delivery_size'] or duration!=5300 or im.info.get('loop')!=0):
                errors.append('Interlude delivery/timing mismatch')
            if name=='interlude.png' and list(im.size)!=recipe['motion']['delivery_size']:errors.append('Interlude still size mismatch')
    for path in (MEDIA/'afterimage').glob('*.svg'):
        if re.search(r'<(?:text|script|animate|foreignObject)\b',path.read_text()):errors.append('Unsupported/unoutlined SVG content: '+path.name)
    result={'status':'FAIL' if errors else 'PASS','local_links':links,'assets':assets,'errors':errors,'scope':'Documentation targets and delivery formats/timing; not runtime qualification or visual acceptance'}
    print(json.dumps(result,indent=2));return bool(errors)


if __name__=='__main__':sys.exit(main())
