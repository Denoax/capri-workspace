"""Independently inspect the delivered GIF's finite color ramp, geometry, cadence and wrap."""
from pathlib import Path
import hashlib,json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def check():
    c=json.loads((STORY/'format.json').read_text())['separator'];s=c['delivery_scale'];w=c['width'];h=c['height'];y=c['track_y']*s
    pink=tuple(bytes.fromhex(c['pink'][1:]));green=tuple(bytes.fromhex(c['green'][1:]))
    frames=[];delays=[];profiles=[];ramp_colors=set();green_positions=[]
    with Image.open(STORY/'separator.gif') as gif:
        assert gif.info.get('loop')==0 and gif.size==(w*s,h*s)
        assert gif.n_frames==200 and c['wake_px']==288
        for i in range(gif.n_frames):
            gif.seek(i);im=gif.convert('RGBA');assert gif.disposal_method==2
            delays.append(gif.info['duration']);head=i*w/gif.n_frames;pixels=im.load()
            def color(distance):return pixels[round(((head-distance)%w)*s)%(w*s),y]
            assert color(-40)==(*pink,255) and color(320)==(*pink,255),'Ahead/older track changed'
            assert color(48)==(*green,255),'Near wake not green'
            samples=[color(d) for d in [96,120,144,168,192,216,240,264,280,300]]
            weights=[(x[1]-pink[1])/(green[1]-pink[1]) for x in samples]
            assert all(a>=b for a,b in zip(weights,weights[1:])),'Fade is not monotone'
            assert len(set(samples))>=9 and .03<weights[-3]<.08 and .003<weights[-2]<.02 and weights[-1]==0,'Fade not broad/gradual'
            # Every intermediate stays on the red-green color segment; never fades toward black.
            colored=0
            for x in range(w*s):
                rgba=pixels[x,y];assert rgba[3]==255
                if rgba[:3]!=pink:colored+=1
                ramp_colors.add(rgba[:3]);t=(rgba[1]-pink[1])/(green[1]-pink[1])
                assert 0<=t<=1
                assert all(abs(rgba[k]-(pink[k]+(green[k]-pink[k])*t))<=1.1 for k in [0,2])
            assert 278*s<=colored<=290*s,(i,colored)
            # Binary alpha with a tight transparent envelope prohibits matte and disposal ghosts.
            a=im.getchannel('A');assert a.crop((0,0,w*s,(c['track_y']-12)*s)).getbbox() is None
            assert a.crop((0,(c['track_y']+12)*s,w*s,h*s)).getbbox() is None
            offtrack=im.crop((0,(c['track_y']-9)*s,w*s,(c['track_y']-3)*s))
            assert offtrack.getbbox() is not None,'Arrow head missing'
            positions=[x for x in range(w*s) if pixels[x,(c['track_y']-5)*s]==(*green,255)]
            assert positions and all(0<=((head-x/s)%w)<=27 for x in positions),'Head/edge wrap discontinuity'
            frames.append(hashlib.sha256(im.tobytes()).hexdigest())
            if i in [0,1,50,100,199]:profiles.append(dict(frame=i,head_logical=head,distances=[96,120,144,168,192,216,240,264,280,300],colors=samples))
        assert len(set(frames))==200 and set(delays)=={20} and sum(delays)==4000
        assert len(ramp_colors)>=100,'Insufficient smooth multi-tone palette'
        gif.seek(c['poster_frame']);assert Image.open(STORY/'separator.png').convert('RGBA').tobytes()==gif.convert('RGBA').tobytes()
    return dict(status='PASS',logical_size=[w,h],encoded_size=[w*s,h*s],frames=200,unique_decoded_frames=len(set(frames)),duration_ms=sum(delays),delays_ms=sorted(set(delays)),old_wake_px=192,wake_px=288,wake_ratio=1.5,fade_px=192,center_row_colors=len(ramp_colors),pixels_per_sample=6,loop=0,profiles=profiles,transparency='No matte/ghost outside track and arrow; binary GIF alpha at2x delivery',scope='Actual decoded behavior including wrap; browser/playback and human perceptual approval separate.')
if __name__=='__main__':print(json.dumps(check(),indent=2))
