"""Original source playback with fill-only type over a transparent left field."""
from pathlib import Path
import bisect,json
import numpy as np
from PIL import Image,ImageDraw,ImageOps

class HeroScene:
    def __init__(self,root):
        self.root=Path(root);self.scene=self.root/'hero-scene'
        self.config=json.loads((self.scene/'scene.json').read_text());self.size=tuple(self.config['master'])
        self.brand=Image.open(self.scene/'brand.png').convert('RGBA');self.word_mask=Image.open(self.scene/'wordmark-mask.png').getchannel('A')
        self.mask=Image.new('L',self.size);ImageDraw.Draw(self.mask).polygon(self.config['left_polygon'],fill=255)
        self.right_alpha=ImageOps.invert(self.mask)
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
            frame=Image.new('RGBA',self.size);frame.paste(image.resize(scaled,Image.Resampling.LANCZOS),self.right_placement[:2]);frame.putalpha(self.right_alpha);self.right_frames.append(frame)

    def state(self,time_ms):
        t=float(time_ms)%self.config['duration_ms'];source=max(0,bisect.bisect_right(self.timestamps,t)-1)
        rupture=self.config['timeline']['type_rupture'];sheen=self.config['timeline']['sheen']
        return {'time_ms':t,'source_frame':source,'rupture':rupture[0]<=t<rupture[1],'sheen':sheen[0]<=t<sheen[1]}

    def brand_at(self,state):
        image=self.brand.copy()
        if state['sheen']:
            progress=(state['time_ms']-1600)/800;yy,xx=np.mgrid[0:480,0:1400];center=-100+progress*900;amount=np.exp(-((xx+.35*yy-center)/23)**2)*.52
            mask=np.asarray(self.word_mask)/255;data=np.asarray(image).copy();rgb=data[:,:,:3].astype(float);rgb=rgb+(np.array([255,245,250])-rgb)*amount[:,:,None]*mask[:,:,None];data[:,:,:3]=np.rint(rgb).astype('uint8');image=Image.fromarray(data)
        if state['rupture']:
            edge=Image.new('RGBA',self.size,(40,251,134));offset=10 if state['source_frame']%2 else -10;alpha=Image.new('L',self.size);alpha.paste(self.word_mask,(offset,0));edge.putalpha(alpha.point(lambda a:round(a*.85)));image=Image.alpha_composite(edge,image)
        return image

    def render(self,time_ms,delivery=False,layers=False):
        state=self.state(time_ms);right=self.right_frames[state['source_frame']]
        brand=self.brand_at(state);brand=Image.composite(brand,Image.new('RGBA',self.size),self.mask)
        result=Image.alpha_composite(right,brand)
        if delivery:result=result.resize(tuple(self.config['delivery']),Image.Resampling.LANCZOS)
        if layers:return result,{'right':right,'brand':brand,'state':state}
        return result
