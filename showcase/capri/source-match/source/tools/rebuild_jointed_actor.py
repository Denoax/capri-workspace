from pathlib import Path
import math, json
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation

ROOT=Path(__file__).resolve().parents[1]
KEYS=np.array(json.loads((ROOT/'assets/characters/motion/KEYFRAMES.json').read_text())['keyframes'],dtype=float)
OUT=ROOT/'build/rig';OUT.mkdir(parents=True,exist_ok=True)
src=Image.open(ROOT/'assets/characters/masters/plan.png').convert('RGBA').resize((768,512),Image.Resampling.LANCZOS)
raw=np.asarray(src).copy(); yy,xx=np.mgrid[0:512,0:768]; x=xx*2;y=yy*2
labels=np.full((512,768),2,dtype=np.uint8)
labels[(y<355)|((x<630)&(y<600))|((x<1110)&(y<400))]=1
labels[(x>900)&(y>600)]=10
labels[(x>760)&(y>540)&(y<675)]=9
def region(tag,points):
 m=Image.new('1',(768,512));ImageDraw.Draw(m).polygon([(a/2,b/2) for a,b in points],fill=1)
 labels[np.array(m,dtype=bool)]=tag
region(7,[(782,547),(850,503),(1036,466),(1095,510),(1050,545),(905,569),(829,626),(765,658)])
region(8,[(1035,467),(1094,505),(1253,667),(1269,591),(1290,543),(1322,531),(1355,470),(1337,621),(1339,670),(1306,628),(1304,735),(1334,846),(1270,805),(1225,722),(1238,688),(1130,584)])
region(3,[(800,366),(835,375),(962,455),(958,500),(918,476),(794,425)])
region(4,[(916,461),(958,500),(1163,395),(1179,410),(1220,446),(1237,449),(1200,407),(1260,427),(1315,408),(1250,389),(1265,382),(1197,372),(1233,353),(1216,344),(1161,358),(1120,383)])
region(5,[(635,359),(669,382),(590,492),(559,477),(574,446),(625,384)])
region(6,[(559,477),(591,476),(541,347),(629,318),(625,307),(566,319),(606,292),(586,287),(548,310),(570,275),(554,274),(516,304),(491,324)])

layers={}
for tag in range(1,11):
 mask=binary_dilation(labels==tag,iterations=2)
 part=raw.copy();part[:,:,3]=np.where(mask,part[:,:,3],0)
 layers[tag]=Image.fromarray(part,'RGBA')
# The lifted hand covers hair in the master. Restore a small pink underpaint
# under the hand, keeping the original hand as its own layer above it.
head=np.array(layers[1]);fill=(labels==6)&(y<348)&(raw[:,:,3]>80)
head[fill]=[255,0,81,254];layers[1]=Image.fromarray(head,'RGBA')

HIP=np.array([803.,600.]);NECK=np.array([737.,357.])
RS=np.array([817.,408.]);RE=np.array([943.,481.])
LS=np.array([652.,380.]);LE=np.array([575.,470.])
GH=np.array([836.,554.]);GK=np.array([1050.,493.])
PH=np.array([806.,621.]);PK=np.array([1006.,637.])
SIZE=240; VIEW=1850.; OFFSET=np.array([-150.,-300.]);SCALE=SIZE/VIEW
def rot(a):
 a=math.radians(a);return np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
def values(t):
 j=min(len(KEYS)-2,max(0,np.searchsorted(KEYS[:,0],t,side='right')-1));u=max(0,min(1,(t-KEYS[j,0])/(KEYS[j+1,0]-KEYS[j,0])));u=u*u*(3-2*u)
 return KEYS[j]*(1-u)+KEYS[j+1]*u
def transforms(t):
 _,body,head,ru,rl,lu,ll,gu,gl,pu,pl,rx,ry=values(t)
 root=HIP+[rx,ry];R=rot(body);B=root-R@HIP
 def pt(p):return R@p+B
 def upper(p,a):q=rot(body+a);return q,pt(p)-q@p
 def lower(p,k,a,b):A,C=upper(p,a);q=rot(body+a+b);return q,A@k+C-q@k
 rh=rot(body+head)
 return {1:(rh,pt(NECK)-rh@NECK),2:(R,B),3:upper(RS,ru),4:lower(RS,RE,ru,rl),5:upper(LS,lu),6:lower(LS,LE,lu,ll),7:upper(GH,gu),8:lower(GH,GK,gu,gl),9:upper(PH,pu),10:lower(PH,PK,pu,pl)}
def frame(t):
 tr=transforms(t);out=Image.new('RGBA',(SIZE,SIZE))
 # Angular joint patches sit behind their corresponding cutouts.
 for tag in [1,9,10,7,8,2,5,6,3,4]:
  R,B=tr[tag];inv=R.T;A=.5*inv/SCALE;C=.5*inv@(OFFSET-B)
  coeff=(A[0,0],A[0,1],C[0],A[1,0],A[1,1],C[1])
  im=layers[tag].transform((SIZE,SIZE),Image.Transform.AFFINE,coeff,Image.Resampling.BICUBIC)
  out.alpha_composite(im)
 return out

if __name__=='__main__':
 times=[0,440,660,840,1260,1460,1680,2180]
 proof=Image.new('RGB',(960,520),'#100a19');d=ImageDraw.Draw(proof)
 for i,t in enumerate(times):
  im=frame(t);proof.paste(im,((i%4)*240,(i//4)*260),im);d.text(((i%4)*240+8,(i//4)*260+242),str(t)+'ms',fill='#f4f1ee')
 proof.save(OUT/'POSE_PROOF.jpg',quality=93)
 frames=[frame(i*1000/30) for i in range(84)]
 boxes=[im.getchannel('A').point(lambda a:255 if a>12 else 0).getbbox() for im in frames]
 box=(max(0,min(b[0] for b in boxes)-8),max(0,min(b[1] for b in boxes)-8),min(SIZE,max(b[2] for b in boxes)+8),min(SIZE,max(b[3] for b in boxes)+8))
 frames=[im.crop(box) for im in frames]
 unique=[];frame_map=[];seen={}
 for im in frames:
  key=im.tobytes()
  if key not in seen:seen[key]=len(unique);unique.append(im)
  frame_map.append(seen[key])
 tw,th=frames[0].size;cols=8;rows=math.ceil(len(unique)/cols)
 atlas=Image.new('RGBA',(tw*cols,th*rows))
 for i,im in enumerate(unique):atlas.paste(im,((i%cols)*tw,(i//cols)*th))
 atlas.save(OUT/'actor-atlas.webp',quality=50,method=6)
 small=atlas.resize((round(atlas.width*.72),round(atlas.height*.72)),Image.Resampling.LANCZOS)
 # Keep integer tiles in the compact atlas.
 sw,sh=round(tw*.72),round(th*.72);small=Image.new('RGBA',(sw*cols,sh*rows))
 for i,im in enumerate(unique):small.paste(im.resize((sw,sh),Image.Resampling.LANCZOS),((i%cols)*sw,(i//cols)*sh))
 small.save(OUT/'actor-atlas-small.webp',quality=42,method=6)
 frames[0].save(OUT/'capri-jointed.webp',save_all=True,append_images=frames[1:],duration=[33,33,34]*28,loop=0,quality=65,method=5)
 (OUT/'KEYFRAMES.json').write_text(json.dumps({'fps':30,'duration_ms':2800,'frame_count':84,'tile':[tw,th],'compact_tile':[sw,sh],'fixed_crop':list(box),'atlas_columns':cols,'frame_map':frame_map,'unique_frames':len(unique),'keyframes':KEYS.tolist(),'source':'Anime source20 pose/timing study. Reconstructed full-body fan-art cutout with independent joint transforms and authored loop closure. Not exact extracted anime acting.','parts':10},indent=2))
 print('Jointed atlas bytes',(OUT/'actor-atlas.webp').stat().st_size,flush=True)
