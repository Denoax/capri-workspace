"""V11 pure-time framed split compositor: real source right, authored signal left."""
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
        self.config=json.loads((self.scene/'scene.json').read_text());self.size=tuple(self.config['master']);self.width,self.height=self.size
        self.left_width=self.config['left_width'];cfg=self.config['cloud']
        self.cloud_image=Image.open(self.scene/cfg['source']).convert('RGB').resize(tuple(cfg['scaled_size']),Image.Resampling.LANCZOS).crop(tuple(cfg['crop']))
        self.blue=np.asarray(self.cloud_image).astype('float32');gray=np.asarray(self.cloud_image.convert('L')).astype('float32')/255
        stops=np.array([0,.10,.27,.52,.78,1]);ramp=np.array([[10,5,20],[31,7,30],[91,6,39],[208,12,68],[255,35,104],[255,136,178]],dtype='float32')
        hacked=np.stack([np.interp(gray,stops,ramp[:,i]) for i in range(3)],axis=2)
        form=np.asarray(self.cloud_image.convert('L').filter(ImageFilter.GaussianBlur(8))).astype('float32')/255;dy,dx=np.gradient(form);edge=np.clip(np.hypot(dx,dy)*30,0,.72)
        self.hacked=hacked*(1-edge[:,:,None])+np.array([40,251,134])*edge[:,:,None]
        self.brand=Image.open(self.scene/'brand.png').convert('RGBA');self.word_mask=Image.open(self.scene/'wordmark-mask.png').getchannel('A')
        self.mask=Image.new('L',self.size);ImageDraw.Draw(self.mask).polygon(self.config['left_polygon'],fill=255)
        yy,xx=np.mgrid[0:self.height,0:self.width];center=self.config['seam']['centerline_x0']+self.config['seam']['slope']*(yy+.5)
        half=self.config['seam']['transition_width']/2
        self.blend_mask=Image.fromarray(np.rint(smooth((center+half-(xx+.5))/(2*half))*255).astype('uint8'))
        self.frame=Image.open(self.scene/'frame.png').convert('RGBA')
        self.terminal_masks=self.make_terminal_masks()
        rng=np.random.default_rng(self.config['seed']);self.fragments=[(float(rng.uniform(0,self.left_width)),float(rng.uniform(0,480)),int(rng.integers(5,32)),int(rng.integers(3,17)),float(rng.uniform(0,2*math.pi))) for _ in range(self.config['terminal']['fragments'])]
        self.source_frames=[];self.durations=[];self.timestamps=[];total=0
        with Image.open(self.scene/self.config['right']['source']) as clip:
            self.source_size=clip.size
            for i in range(clip.n_frames):
                clip.seek(i);self.timestamps.append(total);self.source_frames.append(clip.convert('RGB'));delay=clip.info['duration'];self.durations.append(delay);total+=delay
        assert total==self.config['duration_ms']
        x,y,w,h=self.config['right']['box'];scale=min(w/self.source_size[0],h/self.source_size[1]);scaled=(round(self.source_size[0]*scale),round(self.source_size[1]*scale))
        self.right_placement=(x+(w-scaled[0])//2,y+(h-scaled[1])//2,*scaled)
        self.right_frames=[]
        for image in self.source_frames:
            frame=Image.new('RGB',self.size,'#100a19');frame.paste(image.resize(scaled,Image.Resampling.LANCZOS),self.right_placement[:2]);self.right_frames.append(frame)

    def make_terminal_masks(self):
        cfg=self.config['terminal'];font=ImageFont.truetype(str(self.scene/cfg['font']),cfg['font_size']);lines=[line.lstrip() for line in (self.scene/cfg['source']).read_text().splitlines() if line.strip()]
        result=[]
        for li,layout in enumerate(json.loads((self.scene/cfg['layouts']).read_text())['keyframes']):
            image=Image.new('L',tuple(cfg['source_canvas']));draw=ImageDraw.Draw(image)
            for ri,row in enumerate(layout['rows']):
                for si,(left,right) in enumerate(row['segments']):
                    text=lines[(ri+li*5+si*11)%len(lines)][:max(1,int((right-left)/7.1))];draw.text((left,row['y']),text,font=font,fill=225)
            result.append(image.resize(tuple(cfg['scaled_size']),Image.Resampling.LANCZOS).crop(tuple(cfg['crop'])))
        return result

    def state(self,time_ms):
        t=float(time_ms)%self.config['duration_ms'];source=max(0,bisect.bisect_right(self.timestamps,t)-1)
        phase='blue' if t<1000 else 'rupture' if t<1100 else 'red' if t<3500 else 'recovery'
        red=float(smooth((t-1000)/70)) if t<3500 else 1-float(smooth((t-3500)/470))
        return {'time_ms':t,'phase':phase,'source_frame':source,'red_fraction':red,'rupture':1000<=t<1100,'sheen':1600<=t<2400}

    def terminal(self,t):
        angle=2*math.pi*t/4;position=t/4*len(self.terminal_masks);i=int(position)%len(self.terminal_masks);blend=float(smooth((position%1-.72)/.28))
        mask=Image.blend(self.terminal_masks[i],self.terminal_masks[(i+1)%len(self.terminal_masks)],blend)
        scale=1+.012*math.sin(angle);ox=4*math.sin(angle);oy=8*math.sin(angle)
        return mask.transform((self.left_width,480),Image.Transform.AFFINE,(1/scale,0,-ox,0,1/scale,-oy),resample=Image.Resampling.BICUBIC)

    def left_environment(self,state):
        t=state['time_ms']/1000;red=state['red_fraction'];array=np.rint(self.blue*(1-red)+self.hacked*red).astype('uint8');cloud=Image.fromarray(array).convert('RGBA');glyph=self.terminal(t)
        shadow=Image.new('RGBA',cloud.size,(10,9,20));shadow.putalpha(glyph.filter(ImageFilter.MaxFilter(3)).point(lambda a:round(a*.45)));cloud=Image.alpha_composite(cloud,shadow)
        color=tuple(int(v) for v in np.rint(np.array([216,225,228])*(1-red)+np.array([40,251,134])*red));signal=Image.new('RGBA',cloud.size,color);signal.putalpha(glyph.point(lambda a:round(a*.65)));cloud=Image.alpha_composite(cloud,signal)
        bits=Image.new('RGBA',cloud.size);draw=ImageDraw.Draw(bits);density=.25+.75*math.sin(math.pi*t/4)**2
        for x,y,w,h,phase in self.fragments:
            a=round((6+65*density)*(.65+.35*math.sin(2*math.pi*t/4+phase)));x+=2*math.sin(2*math.pi*t/4+phase)
            if state['rupture']:x+=24*math.sin(phase+state['source_frame'])
            draw.rectangle((x,y,x+w,y+h),fill=(round(30+10*red),round(36+75*red),round(60+15*red),a))
        cloud=Image.alpha_composite(cloud,bits)
        # A restrained ink grade preserves visible clouds, unlike the former almost-opaque title field.
        cloud=Image.alpha_composite(cloud,Image.new('RGBA',cloud.size,(16,10,25,round(self.config['cloud']['ink_grade']*255))))
        if state['rupture']:
            data=np.asarray(cloud).copy()
            for n,(y,h,offset) in enumerate([(38,12,32),(128,9,-24),(244,18,38),(362,11,-30)]):data[y:y+h]=np.roll(data[y:y+h],offset*(1 if state['source_frame']%2 else -1),axis=1)
            cloud=Image.fromarray(data)
        return cloud

    def brand_at(self,state):
        image=self.brand.copy()
        if state['sheen']:
            progress=(state['time_ms']-1600)/800;yy,xx=np.mgrid[0:480,0:1400];center=-100+progress*900;amount=np.exp(-((xx+.35*yy-center)/23)**2)*.52
            mask=np.asarray(self.word_mask)/255;data=np.asarray(image).copy();rgb=data[:,:,:3].astype(float);rgb=rgb+(np.array([255,245,250])-rgb)*amount[:,:,None]*mask[:,:,None];data[:,:,:3]=np.rint(rgb).astype('uint8');image=Image.fromarray(data)
        if state['rupture']:
            edge=Image.new('RGBA',self.size,(40,251,134));offset=10 if state['source_frame']%2 else -10;alpha=Image.new('L',self.size);alpha.paste(self.word_mask,(offset,0));edge.putalpha(alpha.point(lambda a:round(a*.85)));image=Image.alpha_composite(edge,image)
        return image

    def render(self,time_ms,delivery=False,layers=False):
        state=self.state(time_ms);right=self.right_frames[state['source_frame']];environment=Image.new('RGBA',self.size);local=self.left_environment(state);environment.paste(local,(0,0))
        # Continue the edge sample only through the declared blend band, without squeezing the cloud.
        extension=round(self.config['seam']['transition_width']/2)+2
        environment.paste(local.crop((self.left_width-1,0,self.left_width,480)).resize((extension,480)),(self.left_width,0))
        left=Image.alpha_composite(environment,self.brand_at(state))
        result=Image.composite(left.convert('RGB'),right,self.blend_mask)
        result=Image.alpha_composite(result.convert('RGBA'),self.frame).convert('RGB')
        if delivery:result=result.resize(tuple(self.config['delivery']),Image.Resampling.LANCZOS)
        if layers:return result,{'right':right,'left':left,'environment':environment,'mask':self.blend_mask,'frame':self.frame,'state':state}
        return result
