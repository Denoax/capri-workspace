from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,io,math,sys
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import label,binary_closing
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'research/inspora/original-media';OUT=ROOT/'build/reference-plates';OUT.mkdir(parents=True,exist_ok=True)
jobs=[('hands','2-8',None,5.041667,320),('cat','hero-section','crop=768:760:460:90',8.6,320),('rain','i-will-survive',None,.5,320),('dots','1-40',None,4.67,320),('stack','1-23',None,5.4,384)]
def convert(job):
 name,slug,crop,duration,width=job
 vf=(','.join(([crop] if crop else [])+[f'scale={width}:-2','fps=30']))
 dest=OUT/(name+'.mp4')
 if name=='stack':
  chain='[0:v]trim=duration=5.4,setpts=PTS-STARTPTS,scale=384:-2,fps=30,split=2[f][b];[b]reverse,setpts=PTS-STARTPTS[r];[f][r]concat=n=2:v=1:a=0[v]'
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(SOURCE/(slug+'.mp4')),'-filter_complex',chain,'-map','[v]','-an','-c:v','libx264','-preset','medium','-crf','29','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True)
  duration=10.8
 else:
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(SOURCE/(slug+'.mp4')),'-t',str(duration),'-vf',vf,'-an','-c:v','libx264','-preset','medium','-crf','29','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True)
 return {'name':name,'source_slug':slug,'crop':crop,'duration':duration,'width':width,'file':dest.name,'bytes':dest.stat().st_size}
with ThreadPoolExecutor(max_workers=3) as ex:
 results=[f.result() for f in as_completed([ex.submit(convert,j) for j in jobs])]
(OUT/'PLATES.json').write_text(json.dumps(results,indent=2));print('Plates',[(r['name'],r['bytes']) for r in results],flush=True)


subprocess.run([sys.executable,str(ROOT/'tools/calibrate_cat_eyes.py')],check=True)
