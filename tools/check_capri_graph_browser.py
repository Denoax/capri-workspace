#!/usr/bin/env python3
"""Check public request inspection without replaying native art; no timing claim."""
from pathlib import Path
import argparse,asyncio,json,os,subprocess,tempfile,time,urllib.request
import websockets
from capri_media_cdp import CDP
ROOT=Path(__file__).resolve().parents[1]
async def check(port):
    target=next(x for x in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list')) if x['type']=='page')
    async with websockets.connect(target['webSocketDebuggerUrl'],max_size=64_000_000) as ws:
        c=CDP(ws);pump=asyncio.create_task(c.pump());await c.call('Page.enable');await c.call('Runtime.enable')
        try:
            await c.call('Emulation.setDeviceMetricsOverride',{'width':1200,'height':900,'deviceScaleFactor':1,'mobile':False})
            await c.call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            await c.call('Page.navigate',{'url':(ROOT/'showcase/capri/source-match/companion/index.html').as_uri()})
            for _ in range(200):
                await asyncio.sleep(.1)
                state=await c.evaluate("({ready:window.storyApp?.ready,failed:document.body.dataset.failed})")
                if state.get('failed'):raise ValueError(state['failed'])
                if state.get('ready'):break
            else:raise TimeoutError('Companion did not become ready')
            result=await c.evaluate("""(async()=>{
              const app=sceneApp,h=app.scenes.horizon;app.pauseAll();await h.initialize();
              const before={engine:h.engine,time:h.time,nativeTime:h.nativeTime};
              const counts={seek:0,reset:0,step:0},seek=h.renderAt.bind(h),reset=h.resetNative.bind(h),step=h.engine.step.bind(h.engine);
              h.renderAt=(...a)=>{counts.seek++;return seek(...a)};h.resetNative=(...a)=>{counts.reset++;return reset(...a)};h.engine.step=(...a)=>{counts.step++;return step(...a)};
              const select=n=>{const i=document.getElementById('story-request');i.value=n;i.dispatchEvent(new Event('change'))};
              const hidden=document.querySelector('.portrait-chart'),observer=new MutationObserver(()=>{});observer.observe(hidden,{subtree:true,attributes:true,characterData:true,childList:true});
              for(const n of [1,6,1,6,2])select(n);
              const hiddenMutations=observer.takeRecords().length;observer.disconnect();
              const paused={request:storyApp.request,engine:h.engine===before.engine,time:h.time===before.time,nativeTime:h.nativeTime===before.nativeTime,running:h.running,...counts};
              await h.play();select(6);const running=h.running;h.pause();
              const math=document.querySelector('.story-math'),watch=new MutationObserver(()=>{});watch.observe(math,{subtree:true,attributes:true,characterData:true,childList:true});
              for(let i=0;i<30;i++)capriStory.paint(h,i*40);const paintMutations=watch.takeRecords().length;watch.disconnect();
              const input=document.getElementById('story-overhead');input.value=45000;input.dispatchEvent(new Event('input'));
              return {paused,running,paintMutations,hiddenMutations,scopedTotal:app.scenes.dots.storyBudget?.scoped_total,readout:document.getElementById('story-values').textContent};
            })()""")
            p=result['paused']
            if not (p.get('request')==2 and p['engine'] and p['time'] and p['nativeTime'] and not p['running'] and p['seek']==p['reset']==p['step']==0):raise ValueError(result)
            if not (result['running'] and result['paintMutations']==result['hiddenMutations']==0 and result['scopedTotal']==105000 and 'Request 6:' in result['readout']):raise ValueError(result)
            if c.exceptions:raise ValueError(c.exceptions)
            return {'status':'PASS','checks':result,'scope':'Public control state, native identity/time/play-state isolation, hidden-chart/live-paint DOM stability and canonical input row. Not a performance or human visual approval test.'}
        finally:pump.cancel()
def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);args=p.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
    chrome=Path(os.environ.get('CAPRI_CHROMIUM',str(Path.home()/'.cache/ms-playwright/chromium-1243/chrome-linux64/chrome')))
    with tempfile.TemporaryDirectory(prefix='capri-graph-') as directory,(args.evidence/'chromium.log').open('w') as log:
        profile=Path(directory);process=subprocess.Popen([str(chrome),'--headless=new','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-extensions','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank'],stdout=log,stderr=log)
        try:
            for _ in range(150):
                if (profile/'DevToolsActivePort').exists():break
                if process.poll() is not None:raise RuntimeError('Owned browser exited')
                time.sleep(.1)
            result=asyncio.run(check(int((profile/'DevToolsActivePort').read_text().splitlines()[0])));(args.evidence/'graph-isolation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=='__main__':main()
