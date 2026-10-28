#!/usr/bin/env python3
"""Render a finite periodic color wake and crisp geometry at 2x logical delivery size."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def rgb(value):return np.array(tuple(bytes.fromhex(value.lstrip('#'))),dtype=float)
def frame(index,c):
    scale=c['delivery_scale'];ss=c['supersample'];w,h=c['width'],c['height'];pw,ph=w*scale,h*scale
    count=c['period_ms']*c['fps']//1000;head=index*w/count;y=c['track_y']
    # The palette is identical for every phase. Index zero alone is transparent.
    pink,green=rgb(c['pink']),rgb(c['green']);ramp=[tuple(np.rint(pink+(green-pink)*i/127).astype(int)) for i in range(128)]
    palette=[0,0,0]+[v for color in ramp for v in color];palette += [0]*(768-len(palette))
    distance=(head-(np.arange(pw)+.5)/scale)%w
    transition=c['wake_px']*c['fade_fraction']
    strength=np.clip((c['wake_px']-distance)/transition,0,1)
    strength=strength*strength*(3-2*strength)
    indices=1+np.rint(strength*127).astype('uint8')
    values=np.repeat(indices[None,:],ph,axis=0)
    # Supersample the geometry; GIF alpha is binary, with no backdrop baked into edge colors.
    mask=Image.new('L',(pw*ss,ph*ss));draw=ImageDraw.Draw(mask);q=scale*ss
    draw.line([(0,y*q),((w-1/q)*q,y*q)],fill=255,width=round(c['track_width']*q))
    arrow=Image.new('L',mask.size);ad=ImageDraw.Draw(arrow);length=c['arrow_length'];half=c['arrow_half_height']
    for shift in [-w,0,w]:
        x=head+shift
        points=[((x-length)*q,(y-half)*q),(x*q,y*q),((x-length)*q,(y+half)*q),((x-length*.73)*q,y*q),((x-length)*q,(y-half)*q)]
        ad.line(points,fill=255,width=round(1.25*q),joint='curve')
    mask=np.asarray(mask.resize((pw,ph),Image.Resampling.LANCZOS))>=128
    arrow=np.asarray(arrow.resize((pw,ph),Image.Resampling.LANCZOS))>=128
    values[arrow]=128;values[~(mask|arrow)]=0
    im=Image.fromarray(values);im.putpalette(palette);im.info['transparency']=0
    return im
def main():
    c=json.loads((STORY/'format.json').read_text())['separator'];count=c['period_ms']*c['fps']//1000
    frames=[frame(i,c) for i in range(count)];out=STORY/'separator.gif'
    frames[0].save(out,save_all=True,append_images=frames[1:],duration=1000//c['fps'],loop=0,transparency=0,background=0,disposal=2,optimize=False)
    frames[c['poster_frame']].convert('RGBA').save(STORY/'separator.png')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    record=dict(authoring=c,logical_size=[c['width'],c['height']],encoded_size=[c['width']*c['delivery_scale'],c['height']*c['delivery_scale']],sample_count=count,sample_fps=c['fps'],duration_ms=c['period_ms'],gif_sha256=sha(out),poster_sha256=sha(STORY/'separator.png'),head_positions=[i*c['width']/count for i in range(count)],color_profile='128 fixed red-to-green tones; smoothstep over trailing two-thirds; no dithering; binary transparent index0, disposal2',scope='Original deterministic geometry/color animation; actual GIF/browser checks separately required.')
    (STORY/'separator-timeline.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Separator:',count,'positions,',record['encoded_size'],out.stat().st_size,'bytes')
if __name__=='__main__':main()
