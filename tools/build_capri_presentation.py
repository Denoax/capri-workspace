#!/usr/bin/env python3
"""Add one outlined Barlow subtitle to the pinned original hero, without re-encoding lesson art."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
import numpy as np
from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen

TEXT='AGENTIC LOOP PROMPTING'
FONT='fonts/BarlowCondensed-ExtraBoldItalic.ttf'
PINK='#ff1265'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def subtitle(root):
    font=TTFont(root/FONT);glyphs=font.getGlyphSet();cmap=font.getBestCmap()
    scale=55/font['head'].unitsPerEm;baseline=415;left=52.83
    position=0;paths=[];boxes=[]
    for char in TEXT:
        glyph=glyphs[cmap[ord(char)]];pen=SVGPathPen(glyphs);glyph.draw(pen)
        paths.append(f'<path transform="translate({position},0)" d="{pen.getCommands()}"/>')
        bounds=BoundsPen(glyphs);glyph.draw(bounds)
        if bounds.bounds:
            x0,y0,x1,y1=bounds.bounds;boxes.append((position+x0,y0,position+x1,y1))
        position+=glyph.width
    bounds=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
    x=left-bounds[0]*scale
    box=[left,baseline-bounds[3]*scale,x+bounds[2]*scale,baseline-bounds[1]*scale]
    clearance=690-(108/480)*box[3]-box[2]
    assert clearance>=30 and box[1]>345 and box[3]<480
    group=f'<g id="hero-subtitle" aria-label="{TEXT}" fill="{PINK}" transform="translate({x},{baseline}) scale({scale},-{scale})"><title>{TEXT}</title>'+''.join(paths)+'</g>'
    return group,dict(text=TEXT,font=FONT,font_size=55,baseline=baseline,ink_box=box,diagonal_clearance=clearance,uniform_scale=scale,visible_left=left)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'showcase/capri');a=p.parse_args();root=a.root;original=root/'sources/hero-v7'
    group,geometry=subtitle(root)
    for name in ['hero','hero-overlay']:
        text=(original/(name+'.svg')).read_text()
        assert 'hero-subtitle' not in text
        (root/(name+'.svg')).write_text(text.replace('</svg>',group+'</svg>'))
        subprocess.run(['rsvg-convert',str(root/(name+'.svg')),'-o',str(root/(name+'.png'))],check=True)
    output=[];delays=[]
    with tempfile.TemporaryDirectory(prefix='capri-hero-subtitle-') as tmp:
        svg=Path(tmp)/'subtitle.svg';png=Path(tmp)/'subtitle.png'
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="480" viewBox="0 0 1400 480">'+group+'</svg>')
        subprocess.run(['rsvg-convert',str(svg),'--width','1000','--height','343','-o',str(png)],check=True)
        overlay=Image.open(png).convert('RGBA')
        with Image.open(original/'hero.gif') as base:
            palette=Image.new('P',(1,1));colors=base.getpalette();palette.putpalette(colors)
            exact=np.zeros(1<<24,dtype='uint8')
            for n in range(len(colors)//3):
                r,g,b=colors[n*3:n*3+3];exact[(r<<16)|(g<<8)|b]=n
            changed=np.asarray(overlay.getchannel('A'))>0
            for i in range(base.n_frames):
                base.seek(i);delays.append(base.info['duration'])
                # The pinned, already approved frames preserve every original color outside the glyphs.
                rgb=Image.alpha_composite(base.convert('RGBA'),overlay).convert('RGB')
                quantized=np.asarray(rgb.quantize(palette=palette,dither=Image.Dither.NONE))
                original_rgb=np.asarray(base.convert('RGB')).astype('uint32')
                packed=(original_rgb[:,:,0]<<16)|(original_rgb[:,:,1]<<8)|original_rgb[:,:,2]
                indices=exact[packed];indices[changed]=quantized[changed]
                frame=Image.fromarray(indices);frame.putpalette(colors);output.append(frame)
        output[0].save(root/'hero.gif',save_all=True,append_images=output[1:],duration=delays,loop=0,disposal=1,optimize=False)
    record=dict(composition='V8: one original-Barlow in-art subtitle; original V7 composition and footage preserved',font='Barlow Condensed ExtraBold Italic; outlined from bundled OFL font',delivery=[1000,343],master=[1400,480],frames=len(output),duration_ms=sum(delays),delays_ms=delays,subtitle=geometry,method='Pinned V7 decoded GIF frames plus deterministic outlined-glyph overlay; original shared palette reused, no dithering. Editable SVG/overlay derived from pinned masters. Unrelated workflow/social and all lessons untouched.',original={n:sha(original/n) for n in ['hero.svg','hero-overlay.svg','hero.png','hero.gif']},derived={n:sha(root/n) for n in ['hero.svg','hero-overlay.svg','hero.png','hero.gif']},rights='PRIVATE_REVIEW_ONLY; original notices and qualification unchanged',human_visual_approval='PENDING')
    (root/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(subtitle=geometry,frames=len(output),duration_ms=sum(delays),gif_bytes=(root/'hero.gif').stat().st_size)))
if __name__=='__main__':main()
