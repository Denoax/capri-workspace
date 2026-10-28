#!/usr/bin/env python3
"""High-detail private reference plates from the supplied original recordings."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'showcase/capri/source-match';SOURCE=BASE/'source/research/inspora/original-media';OUT=BASE/'plates'
JOBS=[('hands','2-8',None,5.041667,640),('cat','hero-section','crop=768:760:460:90',8.6,640),('rain','i-will-survive',None,.5,640),('dots','1-40',None,4.67,640),('stack','1-23',None,5.4,768)]
def main():
 OUT.mkdir(exist_ok=True);records=[]
 for name,slug,crop,duration,width in JOBS:
  path=SOURCE/(slug+'.mp4');dest=OUT/(name+'.mp4');args=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(path)]
  if name=='stack':
   chain=f'[0:v]trim=duration=5.4,setpts=PTS-STARTPTS,scale={width}:-2,fps=30,split=2[f][b];[b]reverse,setpts=PTS-STARTPTS[r];[f][r]concat=n=2:v=1:a=0[v]';args+=['-filter_complex',chain,'-map','[v]'];duration=10.8
  else:args+=['-t',str(duration),'-vf',','.join(([crop] if crop else [])+[f'scale={width}:-2','fps=30'])]
  args+=['-an','-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)];subprocess.run(args,check=True)
  probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate,duration','-of','json',str(dest)]))['streams'][0]
  records.append({'name':name,'source_slug':slug,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'crop':crop,'duration':duration,'file':dest.name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'decoded_stream':probe,'method':'Source footage composite; original pace retained, no source-acting interpolation. Forward/reverse branded-ending removal for stack only.'});print(name,probe['width'],probe['height'],dest.stat().st_size,flush=True)
 (OUT/'PLATES.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':
 main()
 from build_capri_cat_eyes import main as measure_eyes
 measure_eyes()
