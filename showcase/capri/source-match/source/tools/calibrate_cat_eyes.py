from pathlib import Path
from PIL import Image,ImageDraw
from scipy.ndimage import uniform_filter
import subprocess,json
import numpy as np
P=Path(__file__).resolve().parents[1]/'build/reference-plates'
manual=np.array([[.3,.114,.510,.346,.496],[1.3,.134,.455,.406,.449],[2.3,.218,.507,.483,.507],[3.3,.161,.290,.413,.282],[4.3,.024,.526,.282,.510],[5.3,.262,.460,.544,.455],[6.3,.339,.416,.715,.403],[7.3,.369,.447,.705,.436],[8.3,.134,.389,.352,.381]])
manual[:,[1,3]]=(manual[:,[1,3]]*620+148)/768
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height','-of','json',str(P/'cat.mp4')]))['streams'][0];w,h=probe['width'],probe['height']
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(P/'cat.mp4'),'-vf','fps=15','-f','rawvideo','-pix_fmt','rgb24','-'])
frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,h,w,3);tracks=[]
for n,rgb in enumerate(frames):
 t=n/15;prediction=[np.interp(t,manual[:,0],manual[:,i]) for i in range(1,5)];dark=np.max(rgb,axis=2)<85;den=uniform_filter(dark.astype(float),size=11);points=[]
 for i in [0,2]:
  px,py=prediction[i]*w,prediction[i+1]*h
  xa,xb=max(0,round(px-20)),min(w,round(px+20));ya,yb=max(0,round(py-25)),min(h,round(py+25))
  yy,xx=np.mgrid[ya:yb,xa:xb];score=den[ya:yb,xa:xb]-.0006*((xx-px)**2+(yy-py)**2)
  iy,ix=np.unravel_index(score.argmax(),score.shape);points.append([(xa+ix)/w,(ya+iy)/h])
 tracks.append({'time':t,'eyes':points})
(P/'CAT_EYES.json').write_text(json.dumps(tracks,separators=(',',':')))
proof=Image.new('RGB',(w*3,(h+20)*3),'#181818');draw=ImageDraw.Draw(proof)
for i,t in enumerate(np.arange(.3,8.4,1.0)):
 idx=round(t*15);im=Image.fromarray(frames[idx]);d=ImageDraw.Draw(im)
 for x,y in tracks[idx]['eyes']:d.ellipse((x*w-4,y*h-4,x*w+4,y*h+4),outline='#28fb86',width=2)
 ox,oy=i%3*w,i//3*(h+20);proof.paste(im,(ox,oy+20));draw.text((ox+5,oy+4),f'{t:.1f}s',fill='white')
proof.save(P/'CAT_EYE_CALIBRATED.jpg',quality=90)
print('Cat eye anchors',len(tracks),'frames',w,h)
