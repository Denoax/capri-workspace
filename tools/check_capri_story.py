#!/usr/bin/env python3
"""V3 math, publication and shared-clock media contracts; no aesthetic score."""
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET
from PIL import Image
from capri_context_budget import story_model
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check():
    config=json.loads((STORY/'story.json').read_text());inputs=json.loads((STORY/config['canonical_inputs']).read_text());model=story_model(inputs,config);actual=json.loads((STORY/'model-results.json').read_text());require(actual==model,'Stale generated story model')
    require(model['total_assumed_input_tokens']=={'growing':180000,'curated':90000,'scoped':60000},'Canonical total mismatch')
    require(model['scoped_vs_growing_percent_lower']=='66.7' and model['scoped_vs_curated_percent_lower']=='33.3','Reduction arithmetic mismatch')
    samples={x['additional_input']:x for x in model['sensitivity']};require(samples[30000]['scoped_total']==90000 and samples[30000]['relation']=='equal' and samples[45000]['scoped_total']==105000 and samples[45000]['percent']=='16.7' and samples[45000]['relation']=='higher','Additional-input break-even mismatch')
    require(model['measured_capri_savings'] is None and model['quality_equivalence']=='untested' and model['exact_active_occupancy']=='UNKNOWN','Invented model evidence')
    html=(ROOT/'showcase/capri/source-match/companion/index.html').read_text();data=json.loads(re.search(r'<script type="application/json" id="story-data">(.*?)</script>',html,re.S)[1]);require(data['model']==model and data['config']==config,'Live model differs from generated data')
    require('id="story-request"' in html and 'id="story-overhead"' in html,'Missing actual story controls')
    for layout in ['wide','portrait']:
        svg=(STORY/f'input-{layout}.svg').read_text();ET.fromstring(svg)
        for term in ['Illustrative inputs','not a CAPRI benchmark','thousand tokens','Request number',*[p['label'] for p in model['policies']],*[str(p['total']//1000)+'k total' for p in model['policies']]]:require(term in svg,'Missing authored graph label: '+term)
    root=(ROOT/'README.md').read_text();static=(ROOT/'docs/README_STATIC.md').read_text()
    for row in model['requests']:require(f"| {row['request']} | {row['values']['growing']:,} | {row['values']['curated']:,} | {row['values']['scoped']:,} |" in root,'Missing accessible input row')
    require(root.index('CAPRI gives planning')<root.index('/workflow-wide')<root.index('/contexts-wide')<root.index('/handoff-wide'),'Incorrect product/flow/math reading order')
    require(not re.search(r'(?:src|srcset)="[^"]+\.gif',static),'Incomplete static route')
    families={f for lesson in config['lessons'].values() for f in lesson['families']};require(families=={'sharks','horizon','hands','rain','dots','cat','stack'},'Reference family lost')
    records=[]
    for name,lesson in config['lessons'].items():
        for layout in ['wide','portrait']:
            base=STORY/'exports'/f'{name}-{layout}';poster=base.with_suffix('.png');require(poster.is_file(),'Missing static lesson: '+name)
            extension='png' if lesson.get('static_only') else 'gif';require(f'/{name}-{layout}.{extension}' in root,'Main presentation omitted lesson: '+name)
            if lesson.get('static_only'):continue
            path=base.with_suffix('.gif');record=json.loads(base.with_name(base.name+'-timeline.json').read_text());require(sha(path)==record['gif_sha256'] and sha(poster)==record['poster_sha256'],'Stale story media identity: '+name)
            delay=1000//lesson['fps'];durations=[];distinct=set()
            with Image.open(path) as im:
                require(im.info.get('loop')==0,'GIF does not loop')
                for i in range(im.n_frames):im.seek(i);durations.append(im.info.get('duration',0));distinct.add(hashlib.sha256(im.convert('RGB').tobytes()).hexdigest())
                size=list(im.size)
            require(sum(durations)==lesson['duration_ms'] and all(d>0 and d%delay==0 for d in durations),'Decoded story cadence mismatch: '+name)
            require(len(distinct)>1 and len(record['frames'])==lesson['duration_ms']//delay,'Frozen/incomplete story: '+name)
            for i,frame in enumerate(record['frames']):
                t=i*delay;require(frame['time_ms']==t and abs(frame['state']['time']-t)<.001,'Lesson clock mismatch')
                for scene,state in frame['state']['scenes'].items():
                    if state['sourceTime'] is not None:
                        expected=(t%500 if scene=='rain' else t)/1000;require(abs(state['sourceTime']-expected)<.021,'Source-video clock mismatch: '+scene)
                if name=='contexts':
                    require(frame['state']['request']==min(6,int(t/lesson['duration_ms']*6)+1),'Graph request and lesson clock differ')
                    require(all(frame['state']['scenes'][member]['native'] for member in ['horizon','sharks']),'Primary source export used fallback instead of native execution')
            require(path.stat().st_size<=8_000_000,'Story media exceeds unchanged snapshot bound')
            records.append({'lesson':name,'layout':layout,'bytes':path.stat().st_size,'size':size,'duration_ms':sum(durations),'distinct_complete_states':len(distinct),'export_fps':lesson['fps']})
    manifest=json.loads((STORY/'BUILD_MANIFEST.json').read_text())
    for item in manifest['files']:require(sha(STORY/item['path'])==item['sha256'],'Story build manifest mismatch: '+item['path'])
    bytes_by_layout={}
    for layout in ['wide','portrait']:
        total=(ROOT/'showcase/capri/hero.gif').stat().st_size
        for name,lesson in config['lessons'].items():total+=(STORY/'exports'/f"{name}-{layout}.{'png' if lesson.get('static_only') else 'gif'}").stat().st_size
        bytes_by_layout[layout]=total
    return {'status':'PASS','arithmetic':'ILLUSTRATIVE_NOT_MODEL_RUN','extra_input_samples':model['overhead_samples'],'main_reference_families':sorted(families),'selected_readme_image_bytes':bytes_by_layout,'assets':records,'scope':'Arithmetic, source/shared clocks, decoded cadence and publication targets; not native qualification/perceptual or human approval'}
if __name__=='__main__':
    try:r=check()
    except Exception as error:r={'status':'FAIL','error':str(error)}
    print(json.dumps(r,indent=2));sys.exit(r['status']!='PASS')
