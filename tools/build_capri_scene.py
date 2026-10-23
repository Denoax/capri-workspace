#!/usr/bin/env python3
"""One sampled scene for V8 stills, 60 Hz masters, 25 Hz GIFs and the local player.

System Pango/Cairo shape bundled Barlow into paths; Pillow composites owned poses.
No runtime/controller work, network calls, generated diagrams or inferred anatomy.
"""
from pathlib import Path
from io import BytesIO
from functools import lru_cache
import argparse,base64,ctypes,hashlib,html,json,math,subprocess,xml.etree.ElementTree as ET
import cairo,gi
for name in ('Pango','PangoCairo'): gi.require_version(name,'1.0')
from gi.repository import Pango,PangoCairo
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'showcase/capri'; OUT=MEDIA/'scene'; POSES=MEDIA/'poses'
INK,PAPER,PINK,GREEN,MUTED='#100a19','#f4f1ee','#ff1265','#28fb86','#bcb7c6'
DURATION=18000
# Source-pixel landmarks measured on the selected, unmodified study canvases.
LANDMARKS={
 'explain':{'eyes':[[711,323],[846,378]],'mouth':[742,433],'chest':[748,651],'tip':[1362,848]},
 'point':{'eyes':[[764,414],[910,407]],'mouth':[832,497],'chest':[831,660],'tip':[1490,426]},
 'inspect':{'eyes':[[643,417],[749,380]],'mouth':[720,465],'chest':[755,701],'tip':[678,517]},
}
BEATS=[
 {'id':'plan','role':'Thinker','pose':'explain','title':'Make the brief useful.','caption':['Give each role','what it needs.'],'body':['Select the request, source','and acceptance checks.'],'packet':['Request + latest corrections','Relevant source + edit scope','Acceptance checks + questions']},
 {'id':'build','role':'Doer','pose':'point','title':'Carry the correction.','caption':['Keep the correction','with the task.'],'body':['Build a scoped candidate.','Keep compatible rules intact.'],'packet':['label.py only','blank → Untitled','Case, spacing, type rules retained']},
 {'id':'review','role':'Reviewer','pose':'inspect','title':'Check request and patch.','caption':['Check the request','against the patch.'],'body':['Review the candidate with','its source and evidence.'],'packet':['Request + correction + patch','Checks + known limits','Uncertain effects? Hold.']},
 {'id':'decide','role':'Thinker → human','pose':'explain','title':'You decide what ships.','caption':['You decide','what ships.'],'body':['The report brings findings,','checks and limits back to you.'],'packet':['Findings + check evidence','Limits + open questions','Human decision; no auto-approval']},
]
LAYOUTS={'wide':{'size':[1200,600],'eye':[256,224],'content':[600,120],'packet':[600,328,568,160],'caption':[32,464,496,88]},
         'portrait':{'size':[600,1000],'eye':[256,224],'content':[32,608],'packet':[32,784,536,160],'caption':[32,464,536,88]}}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def smooth(x):return x*x*(3-2*x)
def clamp(x):return max(0,min(1,x))
def mid(eyes):return [(eyes[0][i]+eyes[1][i])/2 for i in range(2)]
def scale_for(pose):
 a,b=LANDMARKS[pose]['eyes'];return 44/math.dist(a,b)

def sample_scene(time_ms,layout='wide',reduced_motion=False):
 """Seekable pure state: pose/caption/phase/packet switch only while hidden."""
 t=0 if reduced_motion else time_ms%DURATION
 old=int(t//4500);local=t%4500;beat=old;alpha=1.;dx=0.;part='read'
 if local>=4000 and old!=3:
  q=local-4000;part='exit' if q<160 else 'hidden' if q<200 else 'enter' if q<400 else 'settle'
  if q<160:alpha=1-smooth(q/160);dx=-8*smooth(q/160)
  elif q<200:alpha=0.;dx=-8
  else:beat=(old+1)%4;u=smooth(clamp((q-200)/200));alpha=u;dx=8*(1-u)
 elif old==3 and local>=4000:
  # Same explain pose through the replay seam; no artificial return journey.
  part='replay';beat=0 if local>=4200 else 3
 gesture=0 if local>=1200 else math.sin(math.pi*local/1200)**2
 if part=='replay':gesture=0
 pose=BEATS[beat]['pose'];eye=LAYOUTS[layout]['eye'];w=LAYOUTS[layout]['size'][0];angle=(.65 if beat in (0,3) else -.65)*gesture
 root=[eye[0]+dx+4*gesture,eye[1]-2*gesture]
 rad=math.radians(angle);c,s=math.cos(rad),math.sin(rad);origin=mid(LANDMARKS[pose]['eyes']);scale=scale_for(pose)
 matrix=[scale*c,-scale*s,scale*s,scale*c]
 def point(p):
  x,y=p[0]-origin[0],p[1]-origin[1]
  return [root[0]+matrix[0]*x+matrix[1]*y,root[1]+matrix[2]*x+matrix[3]*y]
 anchors={n:point(v) for n,v in LANDMARKS[pose].items() if n!='eyes'}
 anchors['eye']=root;px,py,pw,ph=LAYOUTS[layout]['packet']
 # A local 16-unit packet reveal is tied to the same phase clock.
 reveal=16*(1-smooth(clamp((local-4200)/200))) if part in ('enter','settle') else 0
 end=[px+pw,py+68+reveal] if layout=='portrait' else [px+16,py+68+reveal]
 leader=[anchors['tip'],[w-16,anchors['tip'][1]],[w-16,end[1]],end] if layout=='portrait' else [anchors['tip'],end]
 return {'time_ms':round(t,5),'beat':beat,'id':BEATS[beat]['id'],'pose':pose,'phase':part,'alpha':round(alpha,6),'angle':angle,'origin':origin,'root':root,'scale':scale,'matrix':matrix,'anchors':anchors,'packet_offset':reveal,'leader_end':end,'leader_points':leader}

@lru_cache(None)
def shaped(text,size,color=PAPER,display=False):
 """Pango performs shaping/kerning; Cairo emits filled outline paths."""
 stream=BytesIO();surface=cairo.SVGSurface(stream,1400,200);ctx=cairo.Context(surface)
 layout=PangoCairo.create_layout(ctx);desc=Pango.FontDescription('Barlow Condensed ExtraBold Italic' if display else 'Barlow Regular')
 desc.set_absolute_size(size*Pango.SCALE);layout.set_font_description(desc);layout.set_text(text,-1)
 ink,logical=layout.get_pixel_extents();ctx.move_to(-ink.x,-ink.y)
 rgb=tuple(int(color[i:i+2],16)/255 for i in (1,3,5));ctx.set_source_rgb(*rgb);PangoCairo.layout_path(ctx,layout);ctx.fill();surface.finish()
 node=ET.fromstring(stream.getvalue());paths=[]
 for child in node:
  for element in child.iter():element.attrib.pop('id',None)
  paths.append(ET.tostring(child,encoding='unicode'))
 return ''.join(paths),[ink.width,ink.height],layout.get_baseline()/Pango.SCALE

TEXT_BOUNDS=[]
def text(label,x,y,size=30,color=PAPER,display=False,max_width=None):
 body,bounds,_=shaped(label,size,color,display)
 if max_width is not None and bounds[0]>max_width:raise ValueError(f'Text too wide: {label}: {bounds[0]} > {max_width}')
 TEXT_BOUNDS.append({'text':label,'x':x,'y':y,'size':size,'bounds':bounds,'max_width':max_width})
 return f'<g transform="translate({x},{y})">{body}</g>'
def lines(items,x,y,size=30,color=PAPER,max_width=None,leading=40):
 return ''.join(text(v,x,y+i*leading,size,color,max_width=max_width) for i,v in enumerate(items))
def image_svg(im,x,y,w,h):
 stream=BytesIO();im.save(stream,'PNG');data=base64.b64encode(stream.getvalue()).decode()
 return f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="data:image/png;base64,{data}"/>'
def save_svg(name,size,body,background=True):
 w,h=size;bg=f'<path fill="{INK}" d="M0 0H{w}V{h}H0Z"/>' if background else ''
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{html.escape(name)}</title>{bg}{body}</svg>\n'
 path=OUT/f'{name}.svg';path.write_text(svg)
 subprocess.run(['rsvg-convert',str(path),'-o',str(OUT/f'{name}.png')],check=True)
 return svg

def layer_body(index,layout,caption_only=False):
 b=BEATS[index];g=LAYOUTS[layout];w,h=g['size'];x,y=g['content'];px,py,pw,ph=g['packet'];cx,cy,cw,ch=g['caption']
 if caption_only:
  # A tail-free caption avoids crossing hair/hands in these upper-body studies.
  cw=[328,384,384,288][index]
  shape=f'<path fill="{PAPER}" d="M{cx} {cy}h{cw-16}l16 16v{ch-16}H{cx}Z"/>'
  return shape+lines(b['caption'],cx+24,cy+16,27,INK,max_width=cw-48,leading=34)
 body=''
 for i,label in enumerate(['Plan','Build','Review','Decide']):
  sx=(32+i*144) if layout=='portrait' else (600+i*144)
  body+=text(label,sx,32,27,GREEN if i==index else MUTED)
 body+=text(b['role'],x,y-40,26,GREEN)
 titles=[b['title']] if layout=='wide' else {'plan':['Make the brief useful.'],'build':['Carry the correction.'],'review':['Check request + patch.'],'decide':['You decide what ships.']}[b['id']]
 title_size=52 if layout=='wide' else 48
 for j,label in enumerate(titles):body+=text(label,x,y+j*56,title_size,PAPER,True,max_width=w-x-32)
 by=y+(72 if len(titles)==1 else 128)
 # Review's portrait headline needs two lines; position text/packet as one layout.
 if layout=='portrait' and len(titles)>1:by=y+112
 body+=lines(b['body'],x,by,30,max_width=w-x-32)
 body+=f'<path stroke="{MUTED}" stroke-width="1" d="M32 {h-40}H{w-32}"/>'
 body+=text('One write owner. Ordered stages.' if layout=='portrait' else 'One write owner. Ordered stages. Uncertain effects hold for reconciliation.',32,h-28,23,MUTED,max_width=w-64)
 return body

def packet_body(index,layout):
 px,py,pw,ph=LAYOUTS[layout]['packet'];b=BEATS[index]
 body=f'<path fill="#1b1525" d="M{px} {py}h{pw}v{ph}H{px}Z"/><path stroke="{GREEN}" stroke-width="3" d="M{px} {py}v{ph}"/>'
 return body+lines(b['packet'],px+24,py+24,30,GREEN if index==1 else PAPER,max_width=pw-48,leading=44)

@lru_cache(None)
def actor(pose):return Image.open(POSES/f'{pose}.png').convert('RGBA')
def actor_layer(state,layout):
 w,h=LAYOUTS[layout]['size'];src=actor(state['pose']);a,b,c,d=state['matrix'];det=a*d-b*c
 ia,ib,ic,id=d/det,-b/det,-c/det,a/det;rx,ry=state['root'];ox,oy=state['origin']
 im=src.transform((w,h),Image.Transform.AFFINE,(ia,ib,ox-ia*rx-ib*ry,ic,id,oy-ic*rx-id*ry),Image.Resampling.BICUBIC)
 if state['alpha']<1:im.putalpha(im.getchannel('A').point(lambda v:round(v*state['alpha'])))
 return im

def prepare():
 OUT.mkdir(exist_ok=True);fc=ctypes.CDLL('libfontconfig.so.1');fc.FcConfigGetCurrent.restype=ctypes.c_void_p;fc.FcConfigAppFontAddFile.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
 for p in (MEDIA/'fonts').glob('*.ttf'):assert fc.FcConfigAppFontAddFile(fc.FcConfigGetCurrent(),str(p).encode())
 PangoCairo.FontMap.get_default().changed()
 for pose in LANDMARKS:
  im=Image.open(POSES/f'references/capri-{pose}.png').convert('RGBA');alpha=im.getchannel('A')
  # Supplied studies cap opacity at 254 and contain faint transparent RGB speckles.
  # Keep true alpha edges and every opaque black region; only normalize near-opaque.
  im.putalpha(alpha.point(lambda v:255 if v>=249 else v));im.save(POSES/f'{pose}.png',optimize=True)
 manifest={'schema_version':1,'method':'Supplied AI-assisted upper-body poses; original pixel canvases preserved, near-opaque alpha normalized. No new generation, keying, anatomy or warp.','landmarks_source_pixels':LANDMARKS,'alignment':'Eye midpoint and 44-logical-unit inter-eye span, measured on original canvases. Perspective differs; inspect human visual fit.','poses':{p:{'source_sha256':digest(POSES/f'references/capri-{p}.png'),'master_sha256':digest(POSES/f'{p}.png'),'dimensions':list(actor(p).size),'scale':scale_for(p)} for p in LANDMARKS}}
 (POSES/'ANCHORS.json').write_text(json.dumps(manifest,indent=2)+'\n')
 proof=Image.new('RGB',(1200,1080));draw=ImageDraw.Draw(proof)
 for row,bg in enumerate([INK,PAPER,'checker']):
  for col,name in enumerate(LANDMARKS):
   tile=Image.new('RGBA',(400,360),'#d4d0d8' if bg=='checker' else bg)
   if bg=='checker':
    td=ImageDraw.Draw(tile)
    for y in range(0,360,20):
     for x in range(0,400,20):
      if (x//20+y//20)%2:td.rectangle((x,y,x+19,y+19),fill='#b0aabb')
   im=actor(name).copy();im.thumbnail((376,304));tile.alpha_composite(im,((400-im.width)//2,16));proof.paste(tile.convert('RGB'),(col*400,row*360));draw.text((col*400+24,row*360+328),name,fill=PAPER if bg==INK else INK)
 proof.save(POSES/'alpha-proof.png')


BASES={};CAPTIONS={};PACKETS={}
def compose(state,layout):
 k=(layout,state['beat']);frame=BASES[k].copy();frame.alpha_composite(actor_layer(state,layout))
 caption=CAPTIONS[k].copy()
 if state['alpha']<1:caption.putalpha(caption.getchannel('A').point(lambda v:round(v*state['alpha'])))
 frame.alpha_composite(caption)
 frame.alpha_composite(PACKETS[k],(0,round(state['packet_offset'])))
 if state['beat']==1 and state['alpha']>0:
  draw=ImageDraw.Draw(frame);tip=state['anchors']['tip'];end=state['leader_end'];draw.line([tuple(p) for p in state['leader_points']],fill=PINK,width=2);draw.ellipse((end[0]-4,end[1]-4,end[0]+4,end[1]+4),fill=GREEN)
 return frame

def build(static_only=False):
 prepare()
 for layout,g in LAYOUTS.items():
  for i in range(4):
   key=(layout,i)
   for suffix,body,bg,target in [('base',layer_body(i,layout),True,BASES),('caption',layer_body(i,layout,True),False,CAPTIONS),('packet',packet_body(i,layout),False,PACKETS)]:
    name=f'{layout}-{i+1}-{suffix}';save_svg(name,g['size'],body,bg);target[key]=Image.open(OUT/f'{name}.png').convert('RGBA')
   s=sample_scene(i*4500+1600,layout);frame=compose(s,layout)
   body=layer_body(i,layout)+image_svg(actor_layer(s,layout),0,0,*g['size'])+layer_body(i,layout,True)+packet_body(i,layout)
   if i==1:
    route=' '.join(('M' if j==0 else 'L')+f'{p[0]} {p[1]}' for j,p in enumerate(s['leader_points']));body+=f'<path d="{route}" stroke="{PINK}" stroke-width="2" fill="none"/>'
   save_svg(f'{layout}-beat-{i+1}',g['size'],body)
   # Visible, labelled diagnostics are separate from the teaching artwork.
   diag=frame.copy();d=ImageDraw.Draw(diag)
   for label,p in s['anchors'].items():d.ellipse((p[0]-5,p[1]-5,p[0]+5,p[1]+5),outline='white',width=2);d.text((p[0]+8,p[1]-8),label,fill='white')
   diag.save(OUT/f'{layout}-anchors-{i+1}.png')
  w,h=g['size'];comic=''
  for i in range(4):
   svg=ET.fromstring((OUT/f'{layout}-beat-{i+1}.svg').read_text());children=''.join(ET.tostring(c,encoding='unicode') for c in svg if not c.tag.endswith('title'))
   comic+=f'<g transform="translate(0,{h*i})">{children}</g>'
  save_svg(f'{layout}-static',[w,h*4],comic)
  master=[sample_scene(n*1000/60,layout) for n in range(1080)]
  (OUT/f'{layout}-master.json').write_text(json.dumps(master,separators=(',',':'))+'\n')
  if not static_only:
   # One palette for the loop prevents per-frame color flashing. Holds are merged.
   sheet=Image.new('RGB',(w*2,h*2),INK)
   for i in range(4):sheet.paste(compose(sample_scene(i*4500+1600,layout),layout).convert('RGB'),((i%2)*w,(i//2)*h))
   palette=sheet.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
   frames=[];delays=[];timeline=[];previous=None
   for t in range(0,DURATION,40):
    state=sample_scene(t,layout);im=compose(state,layout).convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE);pixels=im.tobytes()
    timeline.append({'time_ms':t,'beat':state['beat'],'pose':state['pose'],'phase':state['phase'],'alpha':state['alpha'],'root':state['root'],'sha256':hashlib.sha256(pixels).hexdigest(),'rgb_sha256':hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()})
    if pixels==previous:delays[-1]+=40
    else:frames.append(im);delays.append(40);previous=pixels
   frames[0].save(OUT/f'{layout}.gif',save_all=True,append_images=frames[1:],duration=delays,loop=0,disposal=1,optimize=False)
   (OUT/f'{layout}-timeline.json').write_text(json.dumps(timeline,indent=2)+'\n')
   print(layout,len(frames),'samples;', (OUT/f'{layout}.gif').stat().st_size,'bytes',flush=True)
 scene={'schema_version':1,'duration_ms':DURATION,'master_hz':60,'gif_hz':25,'beats':BEATS,'layouts':LAYOUTS,'landmarks':LANDMARKS,'boundary':'160 ms out / 40 ms hidden / 200 ms in / 100 ms settle. Replay retains explain pose.','alpha':'Complete delivery scene is opaque ink. Separate pose masters remain RGBA.','typography':{'renderer':'Pango '+Pango.version_string()+' / Cairo '+cairo.cairo_version_string(),'fonts':'Bundled Barlow, application-only Fontconfig registration','shaping':'PangoCairo.layout_path, actual ink extents, kerning; not glyph advances'},'text_bounds':TEXT_BOUNDS}
 (OUT/'SCENE.json').write_text(json.dumps(scene,indent=2)+'\n')
 outputs={p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='BUILD.json'}
 (OUT/'BUILD.json').write_text(json.dumps({'version':8,'outputs':outputs},indent=2)+'\n')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--static-only',action='store_true');args=parser.parse_args();build(args.static_only)
