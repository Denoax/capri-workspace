#!/usr/bin/env python3
"""Export approved fragments with embedded fonts; no network or repo mutation."""
from pathlib import Path
import base64,importlib.util,re,sys

ROOT=Path(__file__).resolve().parents[1]

def font_css():
    styles=[]
    for family,path,weight in [
        ('Manrope','Manrope/Manrope-Variable.ttf','200 800'),
        ('Inter','Inter/Inter-Variable.ttf','100 900'),
        ('Martian Mono','MartianMono/MartianMono-Variable.ttf','100 800'),
    ]:
        data=base64.b64encode((ROOT/'assets/fonts'/path).read_bytes()).decode()
        styles.append("@font-face{font-family:'"+family+"';font-style:normal;font-weight:"+weight+";font-display:swap;src:url(data:font/ttf;base64,"+data+") format('truetype');}")
    return '\n'.join(styles)

def main():
    source=ROOT/'tools/vendor/visualize/scripts/render.py'
    spec=importlib.util.spec_from_file_location('capri_frozen_exporter',source)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    output=ROOT/'preview';output.mkdir(exist_ok=True)
    faces=font_css()
    for name,title in [
        ('handoff-comic-full-sprites','CAPRI — approved first Handoff comic'),
        ('capri-source-scenes','CAPRI — original shark and black-hole source'),
        ('capri-reference-composites','CAPRI — five reference-footage composites'),
    ]:
        text=(ROOT/'design/approved'/(name+'.fragment.html')).read_text()
        text=re.sub(r'@import\s+url\([^)]*\)\s*;',lambda m:faces,text,count=1)
        if 'fonts.googleapis.com/css2' in text:raise ValueError('Unembedded product font import')
        document=module._render_document(text,title)
        (output/(name+'.html')).write_text(document)
        print(name+'.html',len(document.encode()),'bytes')

if __name__=='__main__':main()
