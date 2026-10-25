"""Pure-time V9 hero compositor: fixed source layers and one deterministic clock."""
from pathlib import Path
import bisect,json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageFont

def smooth(value):
    value=np.clip(value,0,1)
    return value*value*(3-2*value)

class HeroScene:
    def __init__(self,root):
        self.root=Path(root);self.scene=self.root/'hero-scene'
        self.config=json.loads((self.scene/'scene.json').read_text());self.size=tuple(self.config['master'])
        self.width,self.height=self.size
        cloud=Image.open(self.scene/'02-clouds.jpg').convert('RGB').resize((1440,480),Image.Resampling.LANCZOS).crop((20,0,1420,480))
        self.cloud_image=cloud;self.blue=np.asarray(cloud).astype('float32')
        gray=np.asarray(cloud.convert('L')).astype('float32')/255
        # Preserve the supplied shapes and single fixed print grid in both color states.
        stops=np.array([0,.10,.27,.52,.78,1])
        ramp=np.array([[10,5,20],[31,7,30],[91,6,39],[208,12,68],[255,35,104],[255,136,178]],dtype='float32')
        hacked=np.stack([np.interp(gray,stops,ramp[:,i]) for i in range(3)],axis=2)
        form=np.asarray(cloud.convert('L').filter(ImageFilter.GaussianBlur(8))).astype('float32')/255
        dy,dx=np.gradient(form);edge=np.clip(np.hypot(dx,dy)*30,0,.72)
        self.hacked=hacked*(1-edge[:,:,None])+np.array([40,251,134])*edge[:,:,None]
        self.yy,self.xx=np.mgrid[0:self.height,0:self.width].astype('float32')
        self.spark=tuple(self.config['portrait']['spark'])
        self.distance=np.hypot(self.xx-self.spark[0],self.yy-self.spark[1])
        self.distance+=12*np.sin(self.yy/23)+8*np.sin(self.xx/39)
        self.brand=Image.open(self.scene/'brand.png').convert('RGBA')
        field=Image.new('RGBA',self.size);ImageDraw.Draw(field).polygon([(0,0),(690,0),(582,480),(0,480)],fill=(16,10,25,242));self.field=field
        self.portrait=Image.new('RGBA',self.size)
        cfg=self.config['portrait'];portrait=Image.open(self.scene/cfg['source']).convert('RGBA').crop(tuple(cfg['alpha_bbox']))
        scale=cfg['master_height']/portrait.height;portrait=portrait.resize((round(portrait.width*scale),cfg['master_height']),Image.Resampling.LANCZOS)
        self.portrait.alpha_composite(portrait,(round(cfg['right']-portrait.width),cfg['top']))
        self.terminal_masks=self.make_terminal_masks()
        rng=np.random.default_rng(self.config['seed'])
        self.fragments=[(float(rng.uniform(570,1400)),float(rng.uniform(0,480)),int(rng.integers(4,31)),int(rng.integers(3,17)),float(rng.uniform(0,2*math.pi))) for _ in range(self.config['terminal']['fragments'])]

    def make_terminal_masks(self):
        cfg=self.config['terminal'];font=ImageFont.truetype(str(self.scene/cfg['font']),cfg['font_size'])
        lines=[line.lstrip() for line in (self.scene/cfg['source']).read_text().splitlines() if line.strip()]
        layouts=json.loads((self.scene/cfg['layouts']).read_text())['keyframes'];result=[]
        for li,layout in enumerate(layouts):
            im=Image.new('L',(1280,720));draw=ImageDraw.Draw(im)
            for ri,row in enumerate(layout['rows']):
                for si,(left,right) in enumerate(row['segments']):
                    text=lines[(ri+li*5+si*11)%len(lines)]
                    # Source-derived ragged extents, actual repository glyphs and no copied source-video text.
                    maxchars=max(1,int((right-left)/7.1));text=text[:maxchars]
                    draw.text((left,row['y']),text,font=font,fill=225,stroke_width=0)
            result.append(im.resize((853,480),Image.Resampling.LANCZOS))
        return result

    def state(self,time_ms):
        t=(float(time_ms)%self.config['duration_ms'])/1000
        phase='blue' if t<2.2 else 'interference' if t<3.2 else 'spark' if t<3.5 else 'propagation' if t<4.7 else 'hacked' if t<8.5 else 'recovery'
        burst=next((i for i,(a,b) in enumerate(self.config['timeline']['bursts']) if a<=t*1000<b),None)
        return dict(time_ms=t*1000,phase=phase,burst=burst,spark=3.2<=t<3.5,portrait_anchor=self.config['portrait']['eye_anchor'],portrait_scale=1)

    def takeover(self,t):
        if t<3.5:return np.zeros(self.size[::-1],dtype='float32')
        if t<4.7:
            radius=float(smooth((t-3.5)/1.2))*1540
            return smooth((radius-self.distance+35)/70)
        if t<8.5:return np.ones(self.size[::-1],dtype='float32')
        # A downward signal-recovery pass, distinct from reversing the outward story.
        progress=float(smooth((t-8.5)/1.5));front=-100+progress*700
        irregular=10*np.sin(self.xx/90)*math.sin(progress*math.pi)
        return 1-smooth((front-self.yy+irregular)/90)

    def terminal(self,t):
        # Content and transforms join periodically; no independent animation timer or random frame state.
        keys=[0,1.4,2.8,4.2,5.6,7,8.5,10];ids=[0,1,2,3,4,5,6,0]
        i=min(bisect.bisect_right(keys,t)-1,6);u=(t-keys[i])/(keys[i+1]-keys[i]);blend=float(smooth((u-.72)/.28))
        mask=Image.blend(self.terminal_masks[ids[i]],self.terminal_masks[ids[i+1]],blend)
        angle=2*math.pi*t/10;scale=1+.012*math.sin(angle);ox=4*math.sin(angle);oy=8*math.sin(angle)
        mask=mask.transform((853,480),Image.Transform.AFFINE,(1/scale,0,-ox,0,1/scale,-oy),resample=Image.Resampling.BICUBIC)
        out=Image.new('L',self.size);out.paste(mask,(547,0));return out

    def portrait_at(self,t,state):
        image=self.portrait.copy()
        if state['burst'] is not None:
            # Replace a few local samples of the same cutout; do not move/rotate/scale the whole pose.
            frame=round(t*30);data=np.asarray(image).copy();source=np.asarray(self.portrait)
            for n,y in enumerate([178,239,326]):
                offset=(-1 if (frame+n)%2 else 1)*(5+state['burst']*3)
                band=source[y:y+6];data[y:y+6]=0
                if offset>0:data[y:y+6,offset:]=band[:,:-offset]
                else:data[y:y+6,:offset]=band[:,-offset:]
            image=Image.fromarray(data)
            draw=ImageDraw.Draw(image);x=int(self.config['portrait']['eye_anchor'][0])
            for n in range(7):
                y=178+n*3+(frame%3);draw.line((x-55+n*9,y,x-39+n*9,y),fill=(40,251,134,130),width=1)
        return image

    def render(self,time_ms,delivery=False,layers=False):
        state=self.state(time_ms);t=state['time_ms']/1000;change=self.takeover(t)
        cloud=Image.fromarray(np.rint(self.blue*(1-change[:,:,None])+self.hacked*change[:,:,None]).astype('uint8')).convert('RGBA')
        glyph=self.terminal(t)
        shadow=Image.new('RGBA',self.size,(10,9,20));shadow.putalpha(glyph.filter(ImageFilter.MaxFilter(3)).point(lambda a:round(a*.50)))
        cloud=Image.alpha_composite(cloud,shadow)
        normal=np.array([216,225,228]);green=np.array([40,251,134])
        color=np.rint(normal[None,None,:]*(1-change[:,:,None])+green[None,None,:]*change[:,:,None]).astype('uint8')
        signal=Image.fromarray(color).convert('RGBA');signal.putalpha(glyph.point(lambda a:round(a*.77)))
        cloud=Image.alpha_composite(cloud,signal)
        bits=Image.new('RGBA',self.size);draw=ImageDraw.Draw(bits);density=.20+.80*math.sin(math.pi*t/10)**2
        for n,(x,y,w,h,phase) in enumerate(self.fragments):
            a=round((6+65*density)*(0.65+0.35*math.sin(2*math.pi*t/10+phase)))
            x+=2*math.sin(2*math.pi*t/10+phase);shift=float(change[min(479,int(y)),min(1399,int(x))])
            fill=(round(30+shift*10),round(36+shift*75),round(60+shift*15),a)
            draw.rectangle((x,y,x+w,y+h),fill=fill)
        cloud=Image.alpha_composite(cloud,bits)
        environment=cloud.copy();cloud=Image.alpha_composite(cloud,self.field);cloud=Image.alpha_composite(cloud,self.brand)
        portrait=self.portrait_at(t,state);cloud=Image.alpha_composite(cloud,portrait)
        spark=Image.new('RGBA',self.size)
        if state['spark']:
            amount=math.sin((t-3.2)/.3*math.pi);draw=ImageDraw.Draw(spark);x,y=self.spark
            for n in range(8):
                angle=n*math.pi/4;length=(12 if n%2 else 25)*amount
                draw.line((x-math.cos(angle)*3,y-math.sin(angle)*3,x+math.cos(angle)*length,y+math.sin(angle)*length),fill=(40,251,134,round(245*amount)),width=2 if n%2 else 3)
            draw.ellipse((x-3,y-3,x+3,y+3),fill=(255,18,101,round(255*amount)))
            draw.line([(x,y),(x-25,y+8),(x-20,y+17),(x-64,y+30)],fill=(40,251,134,round(180*amount)),width=2)
            cloud=Image.alpha_composite(cloud,spark)
        result=cloud.convert('RGB')
        if delivery:result=result.resize(tuple(self.config['delivery']),Image.Resampling.LANCZOS)
        if layers:return result,dict(environment=environment,portrait=portrait,spark=spark,terminal=signal,fragments=bits,change=change,state=state)
        return result
