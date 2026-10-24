#!/usr/bin/env python3
"""Derive bounded native input geometry from existing alpha; no images are created."""
import argparse
import json
from pathlib import Path
from PIL import Image,ImageChops,ImageFilter
p=argparse.ArgumentParser();p.add_argument('assets',type=Path);a=p.parse_args()
mask=Image.new('L',(1856,1440))
for pose in ('plan','build','review'):
    alpha=Image.open(a.assets/'actor'/(pose+'-rgba.png')).getchannel('A')
    frame=Image.new('L',mask.size);frame.paste(alpha,(160,160));mask=ImageChops.lighter(mask,frame)
mask=mask.resize((116,90)).filter(ImageFilter.MaxFilter(3))
rects=[]
for y in range(mask.height):
    x=0
    while x<mask.width:
        while x<mask.width and mask.getpixel((x,y))<24:x+=1
        start=x
        while x<mask.width and mask.getpixel((x,y))>=24:x+=1
        if x>start:rects.append([start/116,y/90,(x-start)/116,1/90])
(a.assets/'input-regions.json').write_text(json.dumps(rects))
print(len(rects),'alpha-derived strips')
