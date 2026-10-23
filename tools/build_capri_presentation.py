#!/usr/bin/env python3
"""Rebuild the supplied V3 composition from real source 19 and outlined SVGs."""
from pathlib import Path
import argparse
import bisect
import json
import subprocess
import tempfile
from PIL import Image, ImageOps, __version__ as PILLOW_VERSION


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'showcase/capri')
    parser.add_argument('--width',type=int,default=1000)
    args=parser.parse_args();root=args.root
    if args.width<390 or args.width>1400:parser.error('Delivery width must be 390..1400')
    # Existing SVG display letters are outlined Barlow glyphs; no runtime font loading.
    for name in ['hero','hero-overlay','workflow','social']:
        subprocess.run(['rsvg-convert',str(root/(name+'.svg')),'-o',str(root/(name+'.png'))],check=True)
    frames=[];ends=[];total=0
    with Image.open(root/'sources/capri-19.gif') as source:
        for i in range(source.n_frames):
            source.seek(i);frames.append(source.convert('RGB').copy());total+=source.info['duration'];ends.append(total)
    width=args.width;height=round(width*480/1400)
    with tempfile.TemporaryDirectory(prefix='capri-overlay-') as temp:
        overlay_path=Path(temp)/'overlay.png'
        subprocess.run(['rsvg-convert',str(root/'hero-overlay.svg'),'--width',str(width),'--height',str(height),'-o',str(overlay_path)],check=True)
        overlay=Image.open(overlay_path).convert('RGBA');output=[];durations=[]
        count=round(total*12/1000)
        for i in range(count):
            timestamp=i*1000/12;index=min(bisect.bisect_right(ends,timestamp),len(frames)-1)
            canvas=Image.new('RGBA',(width,height),'#100A19')
            # Same complete source-image box and diagonal as the editable 1400px master.
            target_w=round(850*width/1400);target_h=height
            shot=ImageOps.contain(frames[index],(target_w,target_h),Image.Resampling.LANCZOS)
            x=round(550*width/1400)+(target_w-shot.width)//2;y=(height-shot.height)//2
            canvas.paste(shot,(x,y));canvas=Image.alpha_composite(canvas,overlay).convert('RGB')
            output.append(canvas)
            end=min(total,round((i+1)*1000/12/10)*10);start=round(i*1000/12/10)*10;durations.append(end-start)
        # One palette across the sequence reduces payload and avoids palette shifts.
        samples=Image.new('RGB',(1000,258))
        for j,index in enumerate(range(0,len(output),4)):
            sample=output[index].resize((250,86),Image.Resampling.LANCZOS)
            samples.paste(sample,((j%4)*250,(j//4)*86))
        palette=samples.quantize(colors=96,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        encoded=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in output]
        encoded[0].save(root/'hero.gif',save_all=True,append_images=encoded[1:],duration=durations,loop=0,optimize=True,disposal=1)
    metadata={'composition':'Supplied V3: diagonal ink field, outlined Barlow title, actual Capri source 19; source 12 workflow edge',
      'renderer':'rsvg-convert; Pillow '+PILLOW_VERSION,'font':'Barlow Condensed ExtraBold Italic; OFL-1.1 notice bundled; vector letters outlined',
      'delivery':[width,height],'master':[1400,480],'duration_ms':sum(durations),'sampling_fps':12,'palette_colors':96,'palette_strategy':'One shared palette sampled across the full loop',
      'source_processing':'Source sequence resampled at original overall pace; enlarged from 498x281 into the specified composition, not an HD master; no generated/interpolated frames or face tearing',
      'static_poster':'Supplied 45%-source-frame pose in hero.svg; distinct from animation frame zero',
      'rights':'PRIVATE_REVIEW_ONLY; character-art redistribution unverified','human_visual_approval':'PENDING'}
    (root/'BUILD.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps(metadata,indent=2))


if __name__=='__main__':main()
