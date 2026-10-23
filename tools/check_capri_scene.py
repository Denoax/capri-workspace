#!/usr/bin/env python3
"""V8 delivery regression checks; perceptual motion and approval stay human checks."""
import hashlib,json,math
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri';SCENE=MEDIA/'scene'
def check_scene():
 from build_capri_scene import sample_scene,LANDMARKS,BEATS,LAYOUTS,mid,DURATION
 errors=[];metrics={}
 def require(ok,message):
  if not ok:errors.append(message)
 manifest=json.loads((SCENE/'BUILD.json').read_text())
 for name,entry in manifest['outputs'].items():
  p=SCENE/name;require(p.stat().st_size==entry['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],'V8 output hash: '+name)
 for layout in LAYOUTS:
  master=json.loads((SCENE/f'{layout}-master.json').read_text());timeline=json.loads((SCENE/f'{layout}-timeline.json').read_text())
  require(len(master)==1080,'60 Hz master must span all 18 seconds')
  require(len(timeline)==450 and [f['time_ms'] for f in timeline]==list(range(0,18000,40)),'25 Hz export sample times incomplete')
  for t in [0,600,1200,3999,4000,4160,4199,4200,4400,4499,4500,8700,13200,17500,17999]:
   s=sample_scene(t,layout);require(s==sample_scene(t+DURATION,layout),'Nonperiodic seek: '+str(t))
   require(s['pose']==BEATS[s['beat']]['pose'],'Phase/pose synchronization')
   a,b=LANDMARKS[s['pose']]['eyes'];require(abs(math.dist(a,b)*s['scale']-44)<1e-6,'Head normalization')
   require(math.dist(s['root'],LAYOUTS[layout]['eye'])<=12,'Actor escaped local stage')
  for boundary in [4500,9000,13500,18000]:
   require(abs(sample_scene(boundary-.001,layout)['packet_offset']-sample_scene(boundary,layout)['packet_offset'])<.01,'Packet jumps at beat/replay boundary')
  for t in [4200,8700,13200]:require(sample_scene(t,layout)['alpha']==0,'Pose switch must be fully hidden')
  require(all(sample_scene(t,layout)['alpha']==1 for t in range(17500,18000,20)),'Replay must not blank the retained explain pose')
  for i in range(4):
   s=sample_scene(i*4500+1600,layout);require(s['anchors']['eye']==LAYOUTS[layout]['eye'],'Settled eye-line mismatch')
  decoded=[];duration=0;unique=set();holds=[]
  with Image.open(SCENE/f'{layout}.gif') as gif:
   require(gif.info.get('loop')==0,'GIF must loop')
   for i in range(gif.n_frames):
    gif.seek(i);delay=gif.info['duration'];rgb=gif.convert('RGB');sha=hashlib.sha256(rgb.tobytes()).hexdigest();unique.add(sha)
    require(delay%40==0 and delay>=40,'Invalid moving/hold delay');holds.append(delay)
    decoded.extend([sha]*(delay//40));duration+=delay
   metrics[layout]={'frames':gif.n_frames,'distinct_frames':len(unique),'duration_ms':duration,'moving_delay_ms':40,'long_holds_ms':[v for v in holds if v>40],'bytes':(SCENE/f'{layout}.gif').stat().st_size}
  require(duration==18000,'V8 duration mismatch')
  require(decoded==[f['rgb_sha256'] for f in timeline],'Encoded GIF differs from sampled RGB timeline: '+layout)
  # Every moving segment has distinct adjacent visual samples. Holds are excluded.
  moving=0
  for a,b in zip(timeline,timeline[1:]):
   if a['phase'] not in ('read','replay','settle') and a['alpha']!=b['alpha']:
    require(a['rgb_sha256']!=b['rgb_sha256'],'Duplicated moving frame');moving+=1
  metrics[layout]['boundary_motion_intervals']=moving
 for name in LANDMARKS:
  with Image.open(MEDIA/f'poses/{name}.png') as im:
   require(im.mode=='RGBA' and im.getchannel('A').getextrema()==(0,255),'Pose must retain real alpha: '+name)
 check_scene.metrics=metrics
 return errors
if __name__=='__main__':
 errors=check_scene();print(json.dumps({'status':'FAIL' if errors else 'PASS','metrics':check_scene.metrics,'errors':errors},indent=2));raise SystemExit(bool(errors))
