#!/usr/bin/env python3
"""Author CAPRI's README graphics from its existing character footage and OFL font.
No controller, network, model or live-state operations. Requires Pillow/fontTools.
"""
from pathlib import Path
from io import BytesIO
import base64,json
from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri';OUT=MEDIA/'identity'
FONT=MEDIA/'fonts/BarlowCondensed-ExtraBoldItalic.ttf'
INK='#100a19';PINK='#ff1265';GREEN='#28fb86';WHITE='#f4f1ee'

def main():
    OUT.mkdir(exist_ok=True)
    font=TTFont(FONT);glyphs=font.getGlyphSet();cmap=font.getBestCmap();units=font['head'].unitsPerEm
    def letters(s,x,y,size,color):
        pos=0;parts=[]
        for c in s:
            g=glyphs[cmap[ord(c)]];p=SVGPathPen(glyphs);g.draw(p);parts.append(f'<path transform="translate({pos},0)" d="{p.getCommands()}"/>');pos+=g.width
        return f'<g fill="{color}" transform="translate({x},{y}) scale({size/units},-{size/units})">'+''.join(parts)+'</g>'
    def shot(index,x,y,w,h,source=19):
        with Image.open(MEDIA/'sources'/f'capri-{source}.gif') as im:
            im.seek(min(index,im.n_frames-1));f=im.convert('RGB');f.thumbnail((498,281))
            b=BytesIO();f.save(b,'JPEG',quality=87,subsampling=0);uri=base64.b64encode(b.getvalue()).decode()
        return f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet" href="data:image/jpeg;base64,{uri}"/>'
    def save(name,w,h,parts,title):
        (OUT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{title}</title>'+parts+'</svg>\n')
    # Flat tab graphics, not simulated live controls. HTML anchors provide real actions.
    for name,label,fill,fg in [('start','START',GREEN,INK),('loop','THE LOOP',WHITE,INK),('art','AFTERIMAGE',PINK,WHITE),('docs','FIELD NOTES',INK,WHITE)]:
        s=f'<path d="M0 0H330L310 80H0Z" fill="{fill}"/>'+letters(label,18,56,49,fg)
        s+=f'<path d="M292 32l12 8-12 8" fill="none" stroke="{fg}" stroke-width="3"/>'
        save('nav-'+name+'.svg',330,80,s,label)
    # Individual headings remain high-contrast in GitHub light and dark modes.
    for name,label in [('loop','THREE VOICES'),('start','JACK IN'),('notes','FIELD NOTES'),('art','AFTERIMAGE')]:
        for mode,bg,fg in [('dark','#0d1117',WHITE),('light','#ffffff',INK)]:
            s=f'<rect width="1400" height="160" fill="{bg}"/>'+letters(label,0,126,145,fg)
            # A small actual eye crop is reserved for the art heading; no decorative eyebrow.
            if name=='art':s+=shot(5,1010,0,390,160,12)
            save('chapter-'+name+'-'+mode+'.svg',1400,160,s,label)
    # A proper map includes the human branch and the held path; no decorative fake traces.
    s=f'<rect width="1400" height="470" fill="{INK}"/>'
    for x,name,verb,col in [(42,'THINKER','RESEARCH',GREEN),(500,'DOER','IMPLEMENT',WHITE),(965,'REVIEWER','VERIFY',PINK)]:
        s+=letters(name,x,115,91,col)+letters(verb,x+2,165,35,WHITE)
    s+='<g fill="none" stroke="#f4f1ee" stroke-width="3"><path d="M370 95H455m-14 -10 14 10-14 10M800 95H920m-14 -10 14 10-14 10M1140 205V245H315V265m-10 -14 10 14 10-14M650 305H820m-14 -10 14 10-14 10"/></g>'
    s+=letters('THINKER REPORT',90,325,58,WHITE)+letters('HUMAN DECISION',850,325,58,GREEN)
    s+=f'<path d="M44 375H1350" stroke="#49334f" stroke-width="2"/>'+letters('UNCERTAIN EXECUTION',46,435,37,PINK)+letters('HOLD FOR RECONCILIATION',750,435,37,WHITE)
    save('loop-map.svg',1400,470,s,'Thinker to Doer to Reviewer to Thinker report to human decision; uncertain execution holds')
    s=f'<rect width="700" height="930" fill="{INK}"/>'
    for y,name,verb,color in [(102,'THINKER','RESEARCH',GREEN),(266,'DOER','IMPLEMENT',WHITE),(430,'REVIEWER','VERIFY',PINK),(594,'THINKER REPORT','',WHITE),(758,'HUMAN DECISION','',GREEN)]:
        s+=letters(name,35,y,75,color)
        if verb:s+=letters(verb,38,y+43,29,WHITE)
        if y<758:s+=f'<path d="M55 {y+65}v35m-9 -12 9 12 9-12" stroke="{WHITE}" fill="none" stroke-width="3"/>'
    s+=f'<path d="M35 815H665" stroke="#49334f" stroke-width="2"/>'+letters('UNCERTAIN EXECUTION',35,863,31,PINK)+letters('HOLD FOR RECONCILIATION',35,906,31,WHITE)
    save('loop-map-mobile.svg',700,930,s,'Mobile handoff map with human decision and held uncertainty')
    # Art interlude. Each entire source box is visible; individual frames are not new scenes.
    s=f'<rect width="1400" height="505" fill="{INK}"/>'
    for n,x,y in [(12,0,110),(54,466,0),(92,932,110)]:s+=shot(n,x,y,468,265)
    s+=letters('AFTER',20,95,110,PINK)+letters('IMAGE',935,485,110,GREEN)
    save('afterimage.svg',1400,505,s,'Afterimage: three moments from Capri source 19, an art interlude')
    # A portrait poster retains the real character rather than inventing anatomy.
    s=f'<rect width="1000" height="1250" fill="{INK}"/>'+letters('CAPRI',48,261,265,PINK)
    s+=shot(54,0,320,1000,565)
    s+=letters('OFF THE',48,1030,155,WHITE)+letters('GRID',45,1205,210,GREEN)
    save('poster.svg',1000,1250,s,'Capri Off the Grid: character poster, an original editorial composition')
    # The branch's art page can play the already-present expression clip directly.
    (OUT/'BUILD.json').write_text(json.dumps({'version':4,'typeface':'Bundled Barlow Condensed ExtraBold Italic; outlined glyphs','source_inputs':['sources/capri-12.gif','sources/capri-19.gif'],'frame_policy':'Entire original-image boxes retained; source19 frames 12,54,92; source12 frame5','source_encoding':'JPEG quality87 for still compositions; original GIFs remain intact','rights':'Anime-image redistribution unverified; private repository','scope':'Original SVG composition and documentation only; not runtime proof'},indent=2)+'\n')
    print('CAPRI identity assets authored:',len(list(OUT.glob('*.svg'))))
if __name__=='__main__':main()
