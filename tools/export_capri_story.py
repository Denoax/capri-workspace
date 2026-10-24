#!/usr/bin/env python3
"""Capture V4 canonical artboards using the actual companion scene clocks."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
import argparse,asyncio,base64,hashlib,json,os,subprocess,tempfile,time,urllib.request
import websockets
from capri_media_cdp import CDP
from export_capri_source_match import Quiet,sha
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'showcase/capri/story/exports'
CONFIG=json.loads((ROOT/'showcase/capri/story/story.json').read_text())
FORMATS=json.loads((ROOT/'showcase/capri/story'/CONFIG['format']).read_text())
LESSONS={name:(item['duration_ms'],item['fps'],item['export_scene']) for name,item in CONFIG['lessons'].items()}
async def export(port,url,evidence,names,layouts,stills_only):
    target=next(x for x in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list')) if x['type']=='page');records=[]
    async with websockets.connect(target['webSocketDebuggerUrl'],max_size=64_000_000) as ws:
        c=CDP(ws);pump=asyncio.create_task(c.pump());await c.call('Page.enable');await c.call('Runtime.enable');browser=await c.call('Browser.getVersion')
        try:
            for name in names:
                duration,fps,scene=LESSONS[name]
                for layout in layouts:
                    if layout not in CONFIG['lessons'][name]['layouts']:continue
                    size=FORMATS['families'][FORMATS['layouts'][layout]];width=size['width']
                    await c.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':size['height'],'deviceScaleFactor':1,'mobile':False});await c.call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
                    await c.call('Page.navigate',{'url':url+f'?export={scene}&lesson={name}&layout={layout}'})
                    for _ in range(200):
                        await asyncio.sleep(.1);ready=await c.evaluate("({ready:document.body?.dataset.storyReady,failed:document.body?.dataset.failed})")
                        if ready.get('failed'):raise RuntimeError(ready['failed'])
                        if ready.get('ready')=='true':break
                    else:raise RuntimeError('Story readiness timeout: '+name)
                    await c.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    box=await c.evaluate(f"(()=>{{const r=document.querySelector('main [data-lesson=\"{name}\"] .story-frame').getBoundingClientRect();return {{x:r.x,y:r.y,width:Math.round(r.width),height:Math.round(r.height)}}}})()")
                    if not box['width']:
                        raise ValueError(await c.evaluate("[...document.querySelectorAll('[data-lesson],#capri-source-scenes,#capri-reference-composites')].map(e=>({tag:e.tagName,lesson:e.dataset.lesson,id:e.id,hidden:e.hidden,display:getComputedStyle(e).display,width:e.getBoundingClientRect().width,html:e.outerHTML.slice(0,220)}))"))
                    if [box['width'],box['height']] != [size['width'],size['height']]:
                        raise ValueError({'lesson':name,'actual':box,'expected':size,'document':await c.evaluate("({width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollHeight,visible:[...document.querySelectorAll('body *')].filter(e=>e.getClientRects().length&&e.getBoundingClientRect().bottom>innerHeight+1).slice(0,16).map(e=>({tag:e.tagName,cls:e.className,id:e.id,bottom:e.getBoundingClientRect().bottom}))})")})
                    async def capture(path):
                        await c.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                        raw=await c.call('Page.captureScreenshot',{'format':'png','clip':{**box,'scale':1},'captureBeyondViewport':True});path.write_bytes(base64.b64decode(raw['data']))
                    await c.evaluate((ROOT/'tools/capri_actor_bounds.js').read_text())
                    poster=OUT/f'{name}-{layout}.png';await capture(poster)
                    if stills_only or CONFIG['lessons'][name].get('static_only') or layout in CONFIG['lessons'][name].get('static_layouts',[]):
                        records.append({'lesson':name,'layout':layout,'static':True,'size':[box['width'],box['height']],'poster_sha256':sha(poster)});print('Still',name,layout,box,flush=True);continue
                    folder=evidence/layout/name;folder.mkdir(parents=True,exist_ok=True);frames=[];count=round(duration*fps/1000)
                    for i in range(count):
                        ms=i*1000/fps;await c.evaluate('window.capriActorBounds=[]');state=await c.evaluate(f'storyApp.renderLesson({json.dumps(name)},{ms})');path=folder/f'{i:04d}.png';await capture(path);bounds=await c.evaluate('capriActorBounds');
                        if any(min(item['margins'])<0 or not item['uniform_surface'] for item in bounds):raise ValueError({'lesson':name,'layout':layout,'time_ms':ms,'actor_bounds':bounds})
                        frames.append({'time_ms':ms,'sha256':sha(path),'state':state,'actor_bounds':bounds})
                    palette=folder/'palette.png';gif=OUT/f'{name}-{layout}.gif';colors=128 if name in ['horizon','checking','brief'] else 256
                    subprocess.run(['ffmpeg','-v','error','-y','-framerate',str(fps),'-i',str(folder/'%04d.png'),'-vf',f'palettegen=stats_mode=diff:max_colors={colors}',str(palette)],check=True)
                    subprocess.run(['ffmpeg','-v','error','-y','-framerate',str(fps),'-i',str(folder/'%04d.png'),'-i',str(palette),'-lavfi','paletteuse=dither=none:diff_mode=rectangle','-loop','0',str(gif)],check=True)
                    record={'lesson':name,'layout':layout,'duration_ms':duration,'sample_fps':fps,'sample_count':count,'size':[box['width'],box['height']],'bytes':gif.stat().st_size,'gif_sha256':sha(gif),'poster_sha256':sha(poster),'palette_colors':colors,'frames':frames,'scope':'Shared companion scene clocks; native sources and recorded footage remain distinct. Sample FPS is not source acting or perceived smoothness.'}
                    (OUT/f'{name}-{layout}-timeline.json').write_text(json.dumps(record,indent=2)+'\n');records.append({k:v for k,v in record.items() if k!='frames'});print(name,layout,count,'samples',gif.stat().st_size,'bytes',flush=True)
                    if gif.stat().st_size>8_000_000:raise ValueError('Presentation export exceeds unchanged8MB checkout bound: '+gif.name)
            if c.exceptions:raise ValueError('Runtime exceptions: '+str(c.exceptions))
        finally:pump.cancel()
    return {'status':'PASS','records':records,'browser':browser,'scope':'Actual browser exports, not perceptual/human/native qualification'}
def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True,type=Path);p.add_argument('--lessons',nargs='+',choices=LESSONS,default=list(LESSONS));p.add_argument('--layouts',nargs='+',choices=['portrait','graph','support'],default=['portrait','graph','support']);p.add_argument('--stills-only',action='store_true');args=p.parse_args();OUT.mkdir(exist_ok=True);args.evidence.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT)));Thread(target=server.serve_forever,daemon=True).start();profile=Path(tempfile.mkdtemp(prefix='owned-story-',dir=args.evidence));chrome=Path(os.environ.get('CAPRI_CHROMIUM',str(Path.home()/'.cache/ms-playwright/chromium-1243/chrome-linux64/chrome')))
    with (args.evidence/'chromium.log').open('w') as log:
        process=subprocess.Popen([str(chrome),'--headless=new','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-extensions','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank'],stdout=log,stderr=log)
        try:
            for _ in range(150):
                if (profile/'DevToolsActivePort').exists():break
                if process.poll() is not None:raise RuntimeError('Owned browser exited')
                time.sleep(.1)
            port=int((profile/'DevToolsActivePort').read_text().splitlines()[0]);url=f'http://127.0.0.1:{server.server_port}/showcase/capri/source-match/companion/index.html';receipt=asyncio.run(export(port,url,args.evidence,args.lessons,args.layouts,args.stills_only));(args.evidence/'export-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            server.shutdown();server.server_close()
if __name__=='__main__':main()
