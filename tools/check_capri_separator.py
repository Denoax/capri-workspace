#!/usr/bin/env python3
"""Decode the actual GIF and verify finite wake, wrap, transparency and cadence."""
from pathlib import Path
import hashlib,json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def check():
 c=json.loads((STORY/'format.json').read_text())['separator'];rgb=lambda s:tuple(bytes.fromhex(s[1:]));pink,green=rgb(c['pink']),rgb(c['green']);frames=[];delays=[];heads=[];colors=[];outside=[]
 with Image.open(STORY/'separator.gif') as gif:
  assert gif.info.get('loop')==0 and list(gif.size)==[c['width'],c['height']]
  assert gif.n_frames==c['period_ms']*c['fps']//1000
  for i in range(gif.n_frames):
   gif.seek(i);im=gif.convert('RGBA');delays.append(gif.info['duration']);assert gif.disposal_method==2
   pixels=im.load();head=i*c['width']/gif.n_frames;y=c['track_y'];count=0;offtrack=0
   for x in range(c['width']):
    rgba=pixels[x,y];assert rgba[3]==255 and rgba[:3] in [pink,green]
    if rgba[:3]==green:count+=1
    for yy in range(c['height']):
     rgba=pixels[x,yy]
     if yy<y-c['arrow_half_height']-2 or yy>y+c['arrow_half_height']+2:assert rgba[3]==0,'Opaque matte/ghost outside track/arrow'
     if rgba[3]:assert rgba[:3] in [pink,green] and rgba[3]==255
     if yy not in [y,y+1] and rgba[:3]==green and rgba[3]:offtrack+=1
   assert offtrack>=40 and c['wake_px']-2<=count<=c['wake_px']+4,(i,count,offtrack)
   for offset,color in [(40,pink),(-c['wake_px']/2,green),(-c['wake_px']-40,pink)]:assert pixels[round((head+offset)%c['width']),y][:3]==color,('Wake/ahead/old-track mismatch',i,offset)
   frames.append(hashlib.sha256(im.tobytes()).hexdigest());heads.append(head);colors.append(pixels[600,y][:3])
  assert len(set(frames))==gif.n_frames and set(delays)=={20} and sum(delays)==c['period_ms']
  assert green in colors and pink in colors
  gif.seek(c['poster_frame']);assert Image.open(STORY/'separator.png').convert('RGBA').tobytes()==gif.convert('RGBA').tobytes()
 return {'status':'PASS','size':[c['width'],c['height']],'frames':len(frames),'unique_decoded_frames':len(set(frames)),'duration_ms':sum(delays),'delays_ms':sorted(set(delays)),'wake_px':c['wake_px'],'pixels_per_sample':c['width']/len(frames),'loop':0,'transparency':'No matte/ghost outside the actual track/arrow','wake':'Green immediately behind; red ahead and older track, every decoded phase including wrap','scope':'Decoded objective pixel/cadence checks; not perceptual or physical-display approval.'}
if __name__=='__main__':print(json.dumps(check(),indent=2))
