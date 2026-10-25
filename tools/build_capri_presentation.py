#!/usr/bin/env python3
"""Build the V9 shared-clock hero only; preserve every downstream graphic/export."""
from pathlib import Path
import argparse,base64,hashlib,json,subprocess
from io import BytesIO
from PIL import Image,__version__ as PILLOW_VERSION
from capri_hero_scene import HeroScene
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def uri(image):
    b=BytesIO();image.save(b,format='PNG');return 'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()
def palette_for(scene):
    times=[0,2300,3333,3800,4300,6200,9300]
    atlas=Image.new('RGB',(500*len(times),172))
    for i,t in enumerate(times):atlas.paste(scene.render(t,delivery=True).resize((500,172),Image.Resampling.LANCZOS),(i*500,0))
    return atlas.quantize(colors=192,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=MEDIA);p.add_argument('--proof',type=Path);args=p.parse_args()
    subprocess.run(['rsvg-convert',str(args.root/'hero-scene/brand.svg'),'-o',str(args.root/'hero-scene/brand.png')],check=True)
    scene=HeroScene(args.root);cfg=scene.config;palette=palette_for(scene)
    if args.proof:
        out=args.proof;out.mkdir(exist_ok=False)
        # Explicitly cut proof excerpts: clean blue, spark/propagation, clean hacked. Not a final continuous loop.
        indices=list(range(15))+list(range(99,144))+list(range(186,216))
        frames=[scene.render(i*1000/30,delivery=True).quantize(palette=palette,dither=Image.Dither.NONE) for i in indices]
        frames[0].save(out/'proof.gif',save_all=True,append_images=frames[1:],duration=[cfg['delays_ms'][i%3] for i in indices],loop=0,optimize=True,transparency=255,palette=palette.getpalette(),disposal=1)
        for t in [0,2300,3333,3900,4500,6200,9300]:scene.render(t).save(out/f'{t:04}.png')
        record=dict(status='PROOF_ONLY',frames=len(frames),source_indices=indices,bytes=(out/'proof.gif').stat().st_size,scope='Short explicitly cut encoded proof; full300frame size/timing and continuous playback still required.')
        (out/'proof.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));return
    root=args.root;frames=[];durations=[];states=[];frame_hashes=[]
    video=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1400x480','-r','30','-i','pipe:0','-an','-c:v','libx264','-threads','1','-crf','20','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-map_metadata','-1','-movflags','+faststart',str(scene.scene/'master.mp4')],stdin=subprocess.PIPE)
    try:
        for i in range(cfg['frames']):
            t=i*1000/cfg['fps'];master=scene.render(t);video.stdin.write(master.tobytes())
            frame=master.resize(tuple(cfg['delivery']),Image.Resampling.LANCZOS).quantize(palette=palette,dither=Image.Dither.NONE)
            frames.append(frame);frame_hashes.append(hashlib.sha256(frame.convert('RGB').tobytes()).hexdigest());durations.append(cfg['delays_ms'][i%3]);states.append(scene.state(t))
    finally:
        video.stdin.close()
        code=video.wait()
    assert code==0
    frames[0].save(root/'hero.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True,transparency=255,palette=palette.getpalette(),disposal=1)
    poster,layers=scene.render(cfg['poster_ms'],layers=True);poster.save(root/'hero.png')
    # Matching editable master layers; no generated banner or generated motion footage.
    brand=(scene.scene/'brand.svg').read_text();brand_body=brand[brand.index('>')+1:brand.rindex('</svg>')]
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="480" viewBox="0 0 1400 480" role="img"><title>CAPRI cloud/terminal takeover — Agentic Loop Prompting</title>'
    for name in ['environment','portrait']:
        image=layers[name];svg+='<g id="'+name+'"><image width="1400" height="480" href="'+uri(image)+'"/></g>'
        if name=='environment':svg+='<g id="title-field"><path d="M0 0H690L582 480H0Z" fill="#100a19" fill-opacity=".9490196078"/></g>'+brand_body
    (root/'hero.svg').write_text(svg+'</svg>\n')
    (root/'hero-overlay.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="480" viewBox="0 0 1400 480"><path d="M0 0H690L582 480H0Z" fill="#100a19" fill-opacity=".9490196078"/>'+brand_body+'</svg>\n')
    subprocess.run(['rsvg-convert',str(root/'hero-overlay.svg'),'-o',str(root/'hero-overlay.png')],check=True)
    # The fixed portrait input and pure-time renderer are the rebuild source, never a fresh generation call.
    record=dict(composition='V9: supplied fixed halftone clouds, original source-derived terminal texture and generated close portrait; original diagonal Barlow branding preserved',delivery=cfg['delivery'],master=cfg['master'],frames=len(frames),duration_ms=sum(durations),delays_ms=durations,sampling_fps=cfg['fps'],palette_colors=192,palette_strategy='One fixed representative blue/transition/hacked palette; no dithering; unchanged-pixel transparent deltas, fixed global color table',renderer='Pillow '+PILLOW_VERSION,poster_ms=cfg['poster_ms'],original_gif_sha256='e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517',portrait_sha256=sha(scene.scene/'portrait-master.png'),scene_sha256=sha(scene.scene/'scene.json'),brand_svg_sha256=sha(scene.scene/'brand.svg'),brand_png_sha256=sha(scene.scene/'brand.png'),source_record='hero-scene/SOURCE_RECORD.json',rights='Private review only; generated fan-art portrait, not official source; original notices unchanged',human_visual_approval='PENDING',derived={n:sha(root/n) for n in ['hero.svg','hero-overlay.svg','hero-overlay.png','hero.png','hero.gif']})
    (root/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n');(scene.scene/'timeline.json').write_text(json.dumps(dict(configuration=cfg,frames=states,quantized_rgb_sha256=frame_hashes,gif_sha256=sha(root/'hero.gif')),indent=2)+'\n')
    print(json.dumps(dict(frames=len(frames),duration_ms=sum(durations),bytes=(root/'hero.gif').stat().st_size,max_bytes=8000000)))
if __name__=='__main__':main()
