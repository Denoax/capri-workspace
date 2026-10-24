#!/usr/bin/env python3
"""Recover editable cat-eye anchors from actual decoded plate frames.

The supplied hand-calibrated priors drift through the turn. A vertical opening
removes three-pixel scanlines before measuring the two large dark eye shapes.
No generated media or model inference; the original priors remain immutable.
"""
from collections import deque
from pathlib import Path
import hashlib,json,subprocess
import numpy as np
from PIL import Image,ImageFilter
ROOT=Path(__file__).resolve().parents[1];PLATES=ROOT/'showcase/capri/source-match/plates'
def opening(mask):
    h,w=mask.shape;p=np.pad(mask,((4,4),(1,1)));eroded=np.ones_like(mask)
    for y in range(9):
        for x in range(3):eroded &= p[y:y+h,x:x+w]
    p=np.pad(eroded,((4,4),(1,1)));result=np.zeros_like(mask)
    for y in range(9):
        for x in range(3):result |= p[y:y+h,x:x+w]
    return result

def centers(mask):
    h,w=mask.shape;mask[:int(.08*h)]=False;mask[int(.65*h):]=False;mask[:,:int(.15*w)]=False;mask[:,int(.85*w):]=False
    result=[]
    for index in np.flatnonzero(mask):
        y,x=divmod(int(index),w)
        if not mask[y,x]:continue
        pending=deque([(x,y)]);mask[y,x]=False;xs=[];ys=[]
        while pending:
            a,b=pending.popleft();xs.append(a);ys.append(b)
            for xx,yy in [(a-1,b),(a+1,b),(a,b-1),(a,b+1)]:
                if 0<=xx<w and 0<=yy<h and mask[yy,xx]:mask[yy,xx]=False;pending.append((xx,yy))
        if len(xs)>=180 and 18<=max(ys)-min(ys)+1<=85 and max(xs)-min(xs)<85:
            result.append((len(xs),float(np.mean(xs)),float(np.mean(ys))))
    pairs=[]
    for a in result:
        for b in result:
            if a[1]<b[1] and .12*w<b[1]-a[1]<.34*w and abs(a[2]-b[2])<.065*h:
                pairs.append((min(a[0],b[0]),a,b))
    if not pairs:raise ValueError(f'No unambiguous eye pair: {result}')
    _,a,b=max(pairs,key=lambda p:p[0]);return [[a[1]/w,a[2]/h],[b[1]/w,b[2]/h]]

def main():
    source=PLATES/'cat.mp4';meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(source)]))['streams'][0]
    w,h=meta['width'],meta['height'];fps=30;records=[]
    process=subprocess.Popen(['ffmpeg','-v','error','-i',str(source),'-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
    try:
        while True:
            raw=process.stdout.read(w*h)
            if not raw:break
            if len(raw)!=w*h:raise ValueError('Truncated decoded source frame')
            gray=np.asarray(Image.frombytes('L',(w,h),raw).filter(ImageFilter.MedianFilter(3)))
            visible=True
            try:eyes=centers(opening(gray<=75))
            except ValueError:
                if not records:raise
                eyes=records[-1]['eyes'];visible=False
            records.append({'time':len(records)/fps,'eyes':eyes,'visible':visible})
        if process.wait()!=0:raise RuntimeError('Source decode failed')
    finally:
        process.stdout.close()
        if process.poll() is None:process.terminate();process.wait()
    assert len(records)==258
    (PLATES/'CAT_EYES.json').write_text(json.dumps(records,indent=2)+'\n')
    (PLATES/'CAT_EYE_RECORD.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'samples':len(records),'fps':fps,'method':'Actual per-frame eye centroids: median3, luma<=75, vertical9x3 opening, paired dark regions. Runtime bounded local refinement; original129priors preserved in source/.','limitations':'Source-image anchor extraction, not proof of continuous perceived alignment. Full-size samples and turn inspected separately.'},indent=2)+'\n')
    print('Measured',len(records),'frames; no visible pair at', [i for i,r in enumerate(records) if not r['visible']])
if __name__=='__main__':main()
