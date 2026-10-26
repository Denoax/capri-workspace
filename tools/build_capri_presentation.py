#!/usr/bin/env python3
"""Build the V10 hero only, preserving all downstream presentation exports."""
from pathlib import Path
import argparse,base64,hashlib,json,subprocess
from io import BytesIO
from PIL import Image,__version__ as PILLOW_VERSION
from capri_hero_scene import HeroScene
from capri_hero_type import build as build_brand
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def uri(image):
    output=BytesIO();image.save(output,format='PNG');return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
def palette_for(scene,colors):
    times=[0,300,700,1030,1070,1200,1600,2000,2500,3000,3500,3900];atlas=Image.new('RGB',(500*len(times),172))
    for i,t in enumerate(times):atlas.paste(scene.render(t,delivery=True).resize((500,172),Image.Resampling.LANCZOS),(i*500,0))
    palette=atlas.quantize(colors=colors,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    # Reserve lettering colors: an anime-weighted atlas otherwise leaves visibly coarse title bands.
    extra=[]
    for stops,count in [(scene.config['wordmark']['gradient'],12),(scene.config['descriptor']['gradient'],8)]:
        rgb=[tuple(int(c[i:i+2],16) for i in (1,3,5)) for c in stops]
        for i in range(count):
            position=i/(count-1)*(len(rgb)-1);segment=min(int(position),len(rgb)-2);fraction=position-segment
            extra.extend(round(a+(b-a)*fraction) for a,b in zip(rgb[segment],rgb[segment+1]))
    entries=palette.getpalette()[:colors*3]+extra;palette.putpalette(entries+[0]*(768-len(entries)))
    return palette
def encode(path,frames,delays,palette):
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=delays,loop=0,optimize=True,transparency=255,palette=palette.getpalette(),disposal=1)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=MEDIA);parser.add_argument('--proof',type=Path);args=parser.parse_args()
    build_brand(args.root);scene=HeroScene(args.root);cfg=scene.config;colors=cfg.get('palette_colors',192);palette=palette_for(scene,colors)
    if args.proof:
        out=args.proof;out.mkdir(exist_ok=False);indices=list(range(12))+list(range(28,41))+list(range(60,73));frames=[scene.render(scene.timestamps[i],delivery=True).quantize(palette=palette,dither=Image.Dither.NONE) for i in indices]
        encode(out/'proof.gif',frames,[scene.durations[i] for i in indices],palette)
        for t in [0,1000,1030,1070,1100,2000,2500,3970]:scene.render(t).save(out/f'{t:04}.png')
        record={'status':'PROOF_ONLY','frames':len(indices),'indices':indices,'bytes':(out/'proof.gif').stat().st_size,'palette_colors':colors+20,'scope':'Cut blue/attack/red excerpts; not a full continuous loop or final file-size result'};(out/'proof.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));return
    frames=[];states=[];hashes=[];video=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1400x480','-r','30','-i','pipe:0','-an','-c:v','libx264','-threads','1','-crf','20','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-map_metadata','-1','-movflags','+faststart',str(scene.scene/'master.mp4')],stdin=subprocess.PIPE)
    try:
        for t in scene.timestamps:
            master=scene.render(t);video.stdin.write(master.tobytes());frame=master.resize(tuple(cfg['delivery']),Image.Resampling.LANCZOS).quantize(palette=palette,dither=Image.Dither.NONE);frames.append(frame);hashes.append(hashlib.sha256(frame.convert('RGB').tobytes()).hexdigest());states.append(scene.state(t))
    finally:video.stdin.close();code=video.wait()
    assert code==0
    encode(args.root/'hero.gif',frames,scene.durations,palette)
    poster,layers=scene.render(cfg['poster_ms'],layers=True);poster.save(args.root/'hero.png')
    brand=(scene.scene/'brand.svg').read_text();body=brand[brand.index('>')+1:brand.rindex('</svg>')];clip='<defs><clipPath id="left-cut"><path d="M0 0H690L582 480H0Z"/></clipPath></defs>'
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="480" viewBox="0 0 1400 480" role="img"><title>CAPRI — Agentic Loop Prompting; original anime right, signal takeover left</title>'+clip+'<rect width="1400" height="480" fill="#100a19"/>'
    x,y,w,h=cfg['right']['box'];source=scene.source_frames[layers['state']['source_frame']];svg+=f'<g id="original-right"><image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet" href="{uri(source)}"/></g>'
    svg+='<g id="left-environment" clip-path="url(#left-cut)"><image width="690" height="480" href="'+uri(scene.left_environment(layers['state']))+'"/></g><g id="brand" clip-path="url(#left-cut)">'+body+'</g></svg>\n';(args.root/'hero.svg').write_text(svg)
    (args.root/'hero-overlay.svg').write_text(brand);subprocess.run(['rsvg-convert',str(args.root/'hero-overlay.svg'),'-o',str(args.root/'hero-overlay.png')],check=True)
    timing_error=max(abs(t-i*1000/30) for i,t in enumerate(scene.timestamps))
    record={'version':10,'composition':'Original Capri/city footage right; V9 clouds/source-derived code left; gradient Barlow and two-line Chakra descriptor','master':cfg['master'],'delivery':cfg['delivery'],'frames':len(frames),'duration_ms':sum(scene.durations),'delays_ms':scene.durations,'sampling':'All120 actual source samples at cumulative encoded source timestamps; no interpolated poses','source_gif_sha256':sha(scene.scene/cfg['right']['source']),'original_gif_sha256':'e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517','palette_colors':colors+20,'palette_base_colors':colors,'palette_strategy':'Fixed global blue/red/anime palette plus20 reserved type-gradient colors; no dithering, unchanged-pixel transparent deltas','renderer':'Pillow '+PILLOW_VERSION,'poster_ms':cfg['poster_ms'],'scene_sha256':sha(scene.scene/'scene.json'),'brand_svg_sha256':sha(scene.scene/'brand.svg'),'brand_png_sha256':sha(scene.scene/'brand.png'),'source_record':'hero-scene/SOURCE_RECORD.json','active_generated_portrait':False,'native_video':{'fps':30,'frames':120,'duration_ms':4000,'audio':False,'source_sample_pts_offset_max_ms':timing_error,'scope':'Same120 renderer samples; nominal30fps video transport. GIF retains exact source30/40ms timing.'},'rights':'Private review; existing original source and font notices retained','human_visual_approval':'PENDING','derived':{n:sha(args.root/n) for n in ['hero.svg','hero-overlay.svg','hero-overlay.png','hero.png','hero.gif','hero-scene/master.mp4']}}
    (args.root/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n');(scene.scene/'timeline.json').write_text(json.dumps({'configuration':cfg,'frames':states,'source_timestamps_ms':scene.timestamps,'delays_ms':scene.durations,'quantized_rgb_sha256':hashes,'gif_sha256':sha(args.root/'hero.gif')},indent=2)+'\n');print(json.dumps({'frames':len(frames),'duration_ms':sum(scene.durations),'bytes':(args.root/'hero.gif').stat().st_size,'palette_colors':colors+20}))
if __name__=='__main__':main()
