#!/usr/bin/env python3
"""Author the deterministic periodic arrow/wake GIF from the user's specification."""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def rgb(value):return tuple(bytes.fromhex(value.lstrip('#')))
def frame(index,c):
 w,h=c['width'],c['height'];count=c['period_ms']*c['fps']//1000;head=index*w/count;y=c['track_y'];im=Image.new('P',(w,h),0);im.putpalette([0,0,0,*rgb(c['pink']),*rgb(c['green'])]+[0]*(768-9));d=ImageDraw.Draw(im);d.line([(0,y),(w-1,y)],fill=1,width=c['track_width'])
 for shift in [-w,0,w]:
  x=head+shift;d.line([(x-c['wake_px'],y),(x,y)],fill=2,width=c['track_width']);length=c['arrow_length'];half=c['arrow_half_height'];d.line([(x-length,y-half),(x,y),(x-length,y+half),(x-length*.73,y),(x-length,y-half)],fill=2,width=2)
 im.info['transparency']=0;return im

def main():
 c=json.loads((STORY/'format.json').read_text())['separator'];count=c['period_ms']*c['fps']//1000;frames=[frame(i,c) for i in range(count)];out=STORY/'separator.gif';frames[0].save(out,save_all=True,append_images=frames[1:],duration=1000//c['fps'],loop=0,transparency=0,background=0,disposal=2,optimize=False);frames[c['poster_frame']].convert('RGBA').save(STORY/'separator.png');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();(STORY/'separator-timeline.json').write_text(json.dumps({'authoring':c,'sample_count':count,'sample_fps':c['fps'],'duration_ms':c['period_ms'],'gif_sha256':sha(out),'poster_sha256':sha(STORY/'separator.png'),'head_positions':[i*c['width']/count for i in range(count)],'scope':'Original deterministic palette animation; finite periodic wake, not accumulated progress. Decode/browser checks are separate.'},indent=2)+'\n');print('Separator authored',count,'positions',out.stat().st_size,'bytes')
if __name__=='__main__':main()
