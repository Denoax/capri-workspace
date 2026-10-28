"""Outline the existing Barlow wordmark and licensed Chakra descriptor."""
from pathlib import Path
import copy,json,subprocess,xml.etree.ElementTree as ET
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
NS='http://www.w3.org/2000/svg';ET.register_namespace('',NS)
def glyph_line(font,text,size,tracking,left):
    glyphs=font.getGlyphSet();cmap=font.getBestCmap();scale=size/font['head'].unitsPerEm;parts=[];bounds=[];pos=0
    for char in text:
        glyph=glyphs[cmap[ord(char)]];pen=SVGPathPen(glyphs);glyph.draw(pen);box=BoundsPen(glyphs);glyph.draw(box)
        if box.bounds:bounds.append((pos+box.bounds[0],box.bounds[1],pos+box.bounds[2],box.bounds[3]))
        parts.append((pos,pen.getCommands()));pos+=glyph.width+tracking/scale
    x0=min(b[0] for b in bounds);x1=max(b[2] for b in bounds);y0=min(b[1] for b in bounds);y1=max(b[3] for b in bounds)
    origin=left-x0*scale
    paths=''.join(f'<path transform="translate({x:.6f},0)" d="{d}"/>' for x,d in parts if d)
    return paths,origin,[left,y0*scale,left+(x1-x0)*scale,y1*scale],scale

def build(media):
    scene=Path(media)/'hero-scene';cfg=json.loads((scene/'scene.json').read_text());old=ET.parse(Path(media)/'sources/hero-v7/hero-overlay.svg').getroot()
    original=next(g for g in old if g.get('transform')==cfg['wordmark']['original_transform'])
    word=copy.deepcopy(original);word.set('id','hero-wordmark');word.set('aria-label','CAPRI');word.set('fill','url(#word-gradient)');word.set('transform',cfg['wordmark']['display_transform'])
    word_svg=ET.tostring(word,encoding='unicode')
    def gradient(name,colors):
        stops=''.join(f'<stop offset="{i/(len(colors)-1):.3f}" stop-color="{c}"/>' for i,c in enumerate(colors))
        return f'<linearGradient id="{name}" gradientUnits="userSpaceOnUse" x1="0" y1="710" x2="0" y2="0">{stops}</linearGradient>'
    defs='<defs>'+gradient('word-gradient',cfg['wordmark']['gradient'])+gradient('descriptor-gradient',cfg['descriptor']['gradient'])+'</defs>'
    subtitle='<g id="hero-subtitle" aria-label="AGENTIC LOOPING">';measure=[]
    with TTFont(scene/cfg['descriptor']['font']) as font:
        for line in cfg['descriptor']['lines']:
            paths,x,bounds,scale=glyph_line(font,line['text'],cfg['descriptor']['size'],cfg['descriptor']['tracking'],cfg['descriptor']['ink_left'])
            baseline=line['baseline'];box=[bounds[0],baseline-bounds[3],bounds[2],baseline-bounds[1]]
            subtitle+=f'<g data-text="{line["text"]}" transform="translate({x:.6f},{baseline}) scale({scale},-{scale})" fill="url(#descriptor-gradient)">{paths}</g>'
            measure.append({'text':line['text'],'origin_x':x,'baseline':baseline,'size':cfg['descriptor']['size'],'tracking':cfg['descriptor']['tracking'],'ink_box':box,'diagonal_clearance':690-.225*box[3]-box[2]})
    subtitle+='</g>'
    def svg(body):return '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="480" viewBox="0 0 1400 480" role="img" aria-label="CAPRI — AGENTIC LOOPING">'+body+'</svg>\n'
    (scene/'brand.svg').write_text(svg(defs+word_svg+subtitle))
    mask=copy.deepcopy(original);mask.set('fill','#fff');mask.set('transform',cfg['wordmark']['display_transform'])
    (scene/'wordmark-mask.svg').write_text(svg(ET.tostring(mask,encoding='unicode')))
    for stem in ['brand','wordmark-mask']:subprocess.run(['rsvg-convert',str(scene/(stem+'.svg')),'-o',str(scene/(stem+'.png'))],check=True)
    (scene/'type.json').write_text(json.dumps({'source_lookup_transform':cfg['wordmark']['original_transform'],'wordmark_transform':cfg['wordmark']['display_transform'],'persistent_outline':False,'wordmark_gradient':cfg['wordmark']['gradient'],'descriptor_gradient':cfg['descriptor']['gradient'],'gradient_coordinates':'One userSpaceOnUse vertical gradient per entire word/line,710→0 font units; corresponding transformed master coordinates, no per-glyph restart','lines':measure,'font_unchanged':True},indent=2)+'\n')
if __name__=='__main__':build(Path(__file__).resolve().parents[1]/'showcase/capri')
