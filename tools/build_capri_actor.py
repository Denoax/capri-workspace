#!/usr/bin/env python3
"""Build the authorized edited-pose actor, alpha masters and transparent GIF.

Media-only, authored affine articulation of the provided edit. No model/runtime calls.
"""
from pathlib import Path
import hashlib,json,math
from PIL import Image,ImageChops,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'showcase/capri/actor'


def delays(count, fps=24):
    """Round cumulative timestamps, not each delay, to GIF centiseconds."""
    ticks=[round(n*100/fps) for n in range(count+1)]
    return [(b-a)*10 for a,b in zip(ticks,ticks[1:])]


def transparent_gif(frames, durations, path):
    atlas=Image.new('RGB',(140*len(frames),86))
    for i,frame in enumerate(frames):
        atlas.paste(frame.convert('RGB').resize((140,86)),(140*i,0))
    palette=atlas.quantize(colors=255,method=Image.Quantize.MEDIANCUT)
    indexed=[]
    for frame in frames:
        raw=frame.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)
        # Zero is reserved for transparency. Black character pixels remain opaque.
        shifted=raw.point(lambda value:value+1)
        shifted.putpalette([0,0,0]+palette.getpalette()[:765])
        shifted.paste(0,mask=frame.getchannel('A').point(lambda a:255 if a<128 else 0))
        indexed.append(shifted)
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=durations,
                    loop=0,transparency=0,background=0,disposal=2,optimize=False)
    return indexed


def main():
    recipe=json.loads((OUT/'ANIMATION.json').read_text())
    source=OUT/recipe['reference']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==recipe['reference_sha256']
    pose=Image.open(source).convert('RGBA').resize(tuple(recipe['working_source_size']),Image.Resampling.LANCZOS)
    # The supplied edit has near-opaque 249-253 interiors; normalize that opacity.
    pose.putalpha(pose.getchannel('A').point(lambda a:0 if a<8 else min(255,round(a*255/253))))
    pad=recipe['padding'];size=(pose.width+2*pad,pose.height+2*pad)
    original=Image.new('RGBA',size);original.alpha_composite(pose,(pad,pad))
    original.save(OUT/'pose-rgba.png',optimize=True)
    original.getchannel('A').save(OUT/'pose-alpha.png',optimize=True)
    layers={};remove=Image.new('L',size)
    for name in ['left_palm','right_palm']:
        spec=recipe[name];mask=Image.new('L',size)
        ImageDraw.Draw(mask).polygon([(x+pad,y+pad) for x,y in spec['outline']],fill=255)
        layer=original.copy();layer.putalpha(ImageChops.multiply(original.getchannel('A'),mask))
        layer.save(OUT/(name+'.png'),optimize=True);layer.getchannel('A').save(OUT/(name+'-mask.png'),optimize=True);layers[name]=layer
        remove=ImageChops.lighter(remove,mask)
    # A small original-pixel wrist overlap prevents a gap when each hand turns.
    for name in layers:
        x,y=recipe[name]['pivot'];ImageDraw.Draw(remove).ellipse((x+pad-7,y+pad-7,x+pad+7,y+pad+7),fill=0)
    body=original.copy();body.putalpha(ImageChops.subtract(original.getchannel('A'),remove))
    body.save(OUT/'body.png',optimize=True)
    body.getchannel('A').save(OUT/'body-mask.png',optimize=True)
    count=round(recipe['samples_per_second']*recipe['duration_ms']/1000)
    frames=[];transforms=[]
    for n in range(count):
        frame=body.copy();angles={}
        for name,layer in layers.items():
            spec=recipe[name]
            angle=spec['amplitude_degrees']*math.sin(2*math.pi*n/count+spec['phase_radians'])
            pivot=tuple(v+pad for v in spec['pivot'])
            frame.alpha_composite(layer.rotate(angle,resample=Image.Resampling.BICUBIC,center=pivot))
            angles[name]=round(angle,6)
        frames.append(frame);transforms.append(angles)
    timing=delays(count,recipe['samples_per_second'])
    frames[0].save(OUT/'actor.png',optimize=True)
    frames[0].save(OUT/'actor-rgba.png',save_all=True,append_images=frames[1:],duration=timing,
                   loop=0,disposal=0,blend=0,optimize=False)
    alphas=[frame.getchannel('A') for frame in frames]
    colors=[]
    for frame in frames:
        rgb=Image.new('RGB',size)
        rgb.paste(frame.convert('RGB'),mask=frame.getchannel('A').point(lambda a:255 if a else 0))
        colors.append(rgb)
    for name,sequence in [('actor-alpha.png',alphas),('actor-rgb.png',colors)]:
        sequence[0].save(OUT/name,save_all=True,append_images=sequence[1:],duration=timing,loop=0,disposal=0,blend=0,optimize=False)
    transparent_gif(frames,timing,OUT/'actor.gif')
    # Validate every decoded alpha frame: transparent pixels cannot retain a prior hand.
    with Image.open(OUT/'actor.gif') as gif:
        decoded=[];duration=0
        assert gif.n_frames==count
        for i,frame in enumerate(frames):
            gif.seek(i);actual=gif.convert('RGBA')
            expected=frame.getchannel('A').point(lambda a:255 if a>=128 else 0)
            assert actual.getchannel('A').tobytes()==expected.tobytes(),('disposal/alpha mismatch',i)
            assert gif.disposal_method==2
            duration+=gif.info['duration'];decoded.append(hashlib.sha256(actual.tobytes()).hexdigest())
        assert duration==recipe['duration_ms']
    # The face is fixed, not independently re-generated or interpolated per frame.
    face=(180+pad,110+pad,250+pad,175+pad)
    assert all(frame.crop(face).tobytes()==frames[0].crop(face).tobytes() for frame in frames)
    proof=Image.new('RGB',(size[0]*3,(size[1]+25)*4),'white');draw=ImageDraw.Draw(proof)
    for row,index in enumerate([0,12,24,36]):
        for col,color in enumerate(['#100a19','#f4f1ee',None]):
            bg=Image.new('RGBA',size,color or '#ccc')
            if color is None:
                d=ImageDraw.Draw(bg)
                for y in range(0,size[1],16):
                    for x in range(0,size[0],16):
                        if (x//16+y//16)%2:d.rectangle((x,y,x+15,y+15),fill='#999')
            bg.alpha_composite(frames[index]);proof.paste(bg.convert('RGB'),(col*size[0],row*(size[1]+25)+25))
            draw.text((col*size[0]+4,row*(size[1]+25)+4),f'frame {index}: {color or "checkerboard"}',fill='black')
    proof.save(OUT/'matte-proof.png',optimize=True)
    record={'version':7,'method':recipe['method'],'reference_sha256':recipe['reference_sha256'],
            'source_reference':{'source':14,'frame':0,'supporting_identity_source':20,'supporting_frame':101},
            'crop_limit':recipe['crop_limit'],'frames':count,'distinct_decoded_frames':len(set(decoded)),
            'duration_ms':duration,'decoded_delays_ms':timing,'sample_rate_hz':count*1000/duration,
            'gif_transparency':'binary index 0, reserved palette entry, disposal 2; all decoded masks compared',
            'face_pixels_unchanged':True,'transforms_degrees':transforms,
            'ai_provenance':'Supplied built-in image edit is the pose source. No new generative frame calls; deterministic palm articulation. Not exact anime pixels or a complete rig.',
            'outputs':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.glob('*.png'))}|{'actor.gif':{'bytes':(OUT/'actor.gif').stat().st_size,'sha256':hashlib.sha256((OUT/'actor.gif').read_bytes()).hexdigest()}}}
    (OUT/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ['frames','distinct_decoded_frames','duration_ms','sample_rate_hz','face_pixels_unchanged']}))


if __name__=='__main__':main()
