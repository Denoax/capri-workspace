#!/usr/bin/env python3
"""Focused documentation/media checks; no controller launch or aesthetic score."""
from pathlib import Path
from urllib.parse import unquote,urlsplit
import json,re,sys
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'showcase/capri'


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
                if url.fragment not in slugs:errors.append(f'Broken heading: {path.name} -> {target}')
            links+=1
    static=(ROOT/'docs/README_STATIC.md').read_text()
    if re.search(r'(?:src|srcset)="[^"]+\.gif"',static):errors.append('Static README embeds animated media')
    selected=json.loads((MEDIA/'SOURCES.json').read_text())['selected']
    if {x['candidate_path'] for x in selected}!={'sources/capri-12.gif','sources/capri-19.gif'}:errors.append('Unexpected branding sources')
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
    result={'status':'FAIL' if errors else 'PASS','local_links':links,'assets':assets,'errors':errors,'scope':'Documentation targets and delivery formats/timing; not runtime qualification or visual acceptance'}
    print(json.dumps(result,indent=2));return bool(errors)


if __name__=='__main__':sys.exit(main())
