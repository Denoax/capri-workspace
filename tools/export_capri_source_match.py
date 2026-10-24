#!/usr/bin/env python3
"""Export GIF/PNG media from the exact companion render path in isolated Chromium.

Sources are deterministic or recorded. Native worlds use fixed steps and seeds;
video seeks wait for decoded frames. Export frame counts are not source FPS.
"""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
import argparse,asyncio,base64,hashlib,json,os,shutil,subprocess,tempfile,time,urllib.request
import websockets
from PIL import Image, GifImagePlugin
from capri_media_cdp import CDP
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri/source-match';OUT=MEDIA/'exports'
SCENES={'comic':(9600,25,1120),'hands':(5040,50,720),'sharks':(4800,25,900),'rain':(500,50,720),'horizon':(6400,25,960),'cat':(8600,25,640),'dots':(4680,25,720),'stack':(10800,25,768),'actor':(9600,25,400)}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
def encode_actor(folder,destination,count,fps):
    frames=[Image.open(folder/f'{i:04d}.png').convert('RGBA') for i in range(count)]
    delay=round(1000/fps)
    for frame in frames:
        box=frame.getbbox()
        if box:assert box[0]>0 and box[1]>0 and box[2]<frame.width and box[3]<frame.height,'Actor alpha clipped'
    for name,items in [('actor-rgba',frames),('actor-rgb',[im.convert('RGB') for im in frames]),('actor-alpha',[im.getchannel('A') for im in frames])]:
        items[0].save(OUT/(name+'.png'),save_all=True,append_images=items[1:],duration=delay,loop=0,disposal=0,blend=0,optimize=False)
    sheet=Image.new('RGB',(1200,360))
    for col,i in enumerate([20,100,180]):sheet.paste(frames[i].convert('RGB'),(col*400,0))
    palette=sheet.quantize(colors=255,method=Image.Quantize.MEDIANCUT);colors=palette.getpalette()[:765]+[0,0,0];encoded=[]
    for frame in frames:
        image=frame.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE);image.putpalette(colors)
        image.paste(255,mask=frame.getchannel('A').point(lambda a:255 if a<128 else 0));encoded.append(image)
    # Write complete frames explicitly: Pillow's delta optimizer can emit a new
    # global header for an entirely transparent disposal-2 transition frame.
    # Keeping authored empty holds is more important than delta compression.
    with destination.open('wb') as stream:
        header,_=GifImagePlugin.getheader(encoded[0],info={'loop':0,'transparency':255,'background':255})
        for block in header:stream.write(block)
        for frame in encoded:
            for block in GifImagePlugin.getdata(frame,duration=delay,transparency=255,disposal=2):stream.write(block)
        stream.write(b';')
    # Compare every actual sample's decoded alpha, expanding legitimate holds.
    with Image.open(destination) as decoded:
        timeline=[]
        for i in range(decoded.n_frames):
            decoded.seek(i);assert decoded.disposal_method==2;timeline.extend([decoded.convert('RGBA').getchannel('A').tobytes()]*(decoded.info['duration']//delay))
    assert len(timeline)==len(frames)
    for actual,expected in zip(timeline,frames):assert actual==expected.getchannel('A').point(lambda a:255 if a>=128 else 0).tobytes(),'Actor disposal/alpha mismatch'

async def export(port,url,evidence,names,layouts,stills_only):
    targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'));target=next(t for t in targets if t['type']=='page')
    records=[]
    async with websockets.connect(target['webSocketDebuggerUrl'],max_size=64_000_000) as ws:
        c=CDP(ws);pump=asyncio.create_task(c.pump());await c.call('Page.enable');await c.call('Runtime.enable');browser=await c.call('Browser.getVersion')
        try:
            for name in names:
                duration,fps,wide=SCENES[name]
                for layout in layouts:
                    if name in ['stack','actor'] and layout=='portrait':continue
                    width=600 if layout=='portrait' else wide
                    await c.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1200,'deviceScaleFactor':1,'mobile':False})
                    await c.call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'},{'name':'prefers-color-scheme','value':'dark'}]})
                    await c.call('Page.navigate',{'url':url+f'?export={"comic" if name=="actor" else name}&layout={layout}'})
                    for _ in range(180):
                        await asyncio.sleep(.1)
                        ready=await c.evaluate("({ready:document.body?.dataset.ready,failed:document.body?.dataset.failed})")
                        if ready.get('failed'):raise RuntimeError(ready['failed'])
                        if ready.get('ready')=='true':break
                    else:raise RuntimeError('Export readiness timeout: '+name)
                    if name=='actor':
                        await c.evaluate("""(()=>{const canvas=document.createElement('canvas');canvas.width=400;canvas.height=360;window.actorCanvas=canvas;window.renderActor=(time)=>{const ctx=canvas.getContext('2d');ctx.clearRect(0,0,400,360);const t=((time%9600)+9600)%9600,local=t%3200,pose=['plan','build','review'][Math.floor(t/3200)],smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x)};ctx.globalAlpha=smooth(local/160)*(1-smooth((local-2880)/160));sceneApp.actor.draw(ctx,pose,local,200,100,.20);ctx.globalAlpha=1;return {sourceTime:null,pose,alpha:smooth(local/160)*(1-smooth((local-2880)/160))};};renderActor(800);return true;})()""")
                        box={'x':0,'y':0,'width':400,'height':360}
                    else:
                        box=await c.evaluate(f"(()=>{{const b=document.querySelector('[data-panel=\"{name}\"]').getBoundingClientRect();return {{x:b.x,y:b.y,width:b.width,height:b.height}};}})()")
                    clip={**box,'scale':1};clip['height']=round(clip['height']);clip['width']=round(clip['width'])
                    async def capture(path):
                        if name=='actor':
                            encoded=await c.evaluate("actorCanvas.toDataURL('image/png').split(',')[1]");path.write_bytes(base64.b64decode(encoded));return
                        response=await c.call('Page.captureScreenshot',{'format':'png','clip':clip,'captureBeyondViewport':True});path.write_bytes(base64.b64decode(response['data']))
                    poster=OUT/f'{name}-{layout}.png';await capture(poster)
                    if stills_only:
                        state=await c.evaluate('renderActor(800)' if name=='actor' else f'sceneApp.scenes[{json.dumps(name)}].state()');records.append({'scene':name,'layout':layout,'size':[clip['width'],clip['height']],'poster_sha256':sha(poster),'state':state});print('Still',name,layout,clip,state,flush=True);continue
                    frames=evidence/layout/name;frames.mkdir(parents=True,exist_ok=True);timeline=[];count=round(duration*fps/1000)
                    for frame in range(count):
                        ms=frame*1000/fps
                        state=await c.evaluate(f'renderActor({ms})' if name=='actor' else f'sceneApp.renderAt({json.dumps(name)},{ms})')
                        path=frames/f'{frame:04d}.png';await capture(path);timeline.append({'time_ms':ms,'sha256':sha(path),'source_time_seconds':state['sourceTime']})
                    gif=OUT/f'{name}-{layout}.gif';palette=frames/'palette.png'
                    if name=='actor':
                        encode_actor(frames,gif,count,fps)
                    else:
                        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-i',str(frames/'%04d.png'),'-vf',('palettegen=stats_mode=diff:max_colors=128' if name=='cat' else 'palettegen=stats_mode=diff'),str(palette)],check=True)
                        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-i',str(frames/'%04d.png'),'-i',str(palette),'-lavfi',('paletteuse=dither=none:diff_mode=rectangle' if name in ['cat','rain'] else 'paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle'),'-loop','0',str(gif)],check=True)
                    record={'scene':name,'layout':layout,'planned_duration_ms':duration,'fps':fps,'sample_count':count,'size':[clip['width'],clip['height']],'gif_bytes':gif.stat().st_size,'gif_sha256':sha(gif),'poster_sha256':sha(poster),'source':'native seeded factory' if name in ['sharks','horizon'] else 'three-pose cutout scene' if name in ['comic','actor'] else 'reference-footage composite','timeline':timeline}
                    records.append(record);(OUT/f'{name}-{layout}-timeline.json').write_text(json.dumps(record,indent=2)+'\n');print(name,layout,count,'samples;',gif.stat().st_size,'bytes',flush=True)
            if c.exceptions:raise RuntimeError('Browser runtime exceptions: '+str(c.exceptions))
        finally:pump.cancel()
    return records,browser

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',required=True,type=Path);parser.add_argument('--scenes',nargs='+',choices=SCENES,default=list(SCENES));parser.add_argument('--layouts',nargs='+',choices=['wide','portrait'],default=['wide','portrait']);parser.add_argument('--stills-only',action='store_true');args=parser.parse_args()
    OUT.mkdir(exist_ok=True);args.evidence.mkdir(parents=True,exist_ok=True)
    chrome=Path(os.environ.get('CAPRI_CHROMIUM',str(Path.home()/'.cache/ms-playwright/chromium-1243/chrome-linux64/chrome')));assert chrome.is_file(),'Set CAPRI_CHROMIUM to an installed Chromium executable'
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT)));thread=Thread(target=server.serve_forever,daemon=True);thread.start();profile=Path(tempfile.mkdtemp(prefix='capri-export-',dir=args.evidence))
    with (args.evidence/'chromium.log').open('w') as log:
        process=subprocess.Popen([str(chrome),'--headless=new','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-extensions','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+str(profile),'about:blank'],stdout=log,stderr=log)
        try:
            for _ in range(150):
                if (profile/'DevToolsActivePort').exists():break
                if process.poll() is not None:raise RuntimeError('Owned Chromium exited')
                time.sleep(.1)
            port=int((profile/'DevToolsActivePort').read_text().splitlines()[0]);url=f'http://127.0.0.1:{server.server_port}/showcase/capri/source-match/companion/index.html'
            records,browser=asyncio.run(export(port,url,args.evidence,args.scenes,args.layouts,args.stills_only))
            (args.evidence/'export-receipt.json').write_text(json.dumps({'status':'PASS','records':[{k:v for k,v in r.items() if k!='timeline'} for r in records],'browser':browser,'scope':'Deterministic companion-render captures; software WebGL where supported. Not physical GPU/perceptual or human approval.'},indent=2)+'\n')
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            server.shutdown();server.server_close()
if __name__=='__main__':main()
