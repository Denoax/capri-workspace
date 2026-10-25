#!/usr/bin/env python3
"""Verify compact publication roles, canonical arithmetic and actual exported evidence."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,re,sys,xml.etree.ElementTree as ET
from PIL import Image
from capri_context_budget import story_model
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class Markup(HTMLParser):
    def __init__(self):super().__init__();self.media=[]
    def handle_starttag(self,tag,attrs):
        if tag in ['img','source']:self.media.append((tag,dict(attrs)))
def check():
    config=json.loads((STORY/'story.json').read_text());formats=json.loads((STORY/config['format']).read_text());model=story_model(json.loads((STORY/config['canonical_inputs']).read_text()),config)
    require(json.loads((STORY/'model-results.json').read_text())==model,'Stale model projection')
    require(model['total_assumed_input_tokens']=={'growing':180000,'curated':90000,'scoped':60000},'Input totals changed')
    require(model['scoped_vs_growing_percent_lower']=='66.7' and model['scoped_vs_curated_percent_lower']=='33.3','Input arithmetic changed')
    samples={row['additional_input']:row for row in model['sensitivity']};require(samples[30000]['scoped_total']==90000 and samples[30000]['relation']=='equal' and samples[45000]['scoped_total']==105000,'Additional-input equality changed')
    require(model['measured_capri_savings'] is None and model['quality_equivalence']=='untested' and model['exact_active_occupancy']=='UNKNOWN','Invented outcome/occupancy evidence')
    page=(ROOT/'showcase/capri/source-match/companion/index.html').read_text();live=json.loads(re.search(r'<script type="application/json" id="story-data">(.*?)</script>',page,re.S)[1]);require(live['model']==model and live['config']==config and live['formats']==formats,'Live source differs from canonical inputs/roles')
    require('id="story-request"' in page and 'id="story-overhead"' in page,'Missing actual local controls')
    graph=(STORY/'input-portrait.svg').read_text();ET.fromstring(graph)
    for term in ['illustrative inputs','not a capri benchmark','thousand tokens','request number',*[p['label'].lower() for p in model['policies']],*[str(p['total']//1000)+'k total' for p in model['policies']]]:require(term in graph.lower(),'Missing graph label: '+term)
    expected={'illustration':(480,640,280),'graph':(480,540,320),'support':(480,320,240),'divider':(1200,48,900),'panel':(700,600,'49.5%'),'graph-wide':(1200,540,'100%'),'support-wide':(960,400,'49.5%')}
    require({name:tuple(item[k] for k in ['width','height','display_width']) for name,item in formats['families'].items()}==expected,'Compact family contract changed without reconciliation')
    for filename,layout in [('input-portrait.svg','portrait'),('input-panel.svg','wide')]:
        svg=ET.fromstring((STORY/filename).read_text());geometry=live['graphs'][layout];require(len(geometry['x'])==6 and len(set(geometry['x']))==6,'Graph X positions lost')
        require(all(abs(geometry['x'][i+1]-geometry['x'][i]-(geometry['x'][1]-geometry['x'][0]))<.01 for i in range(5)),'Graph request spacing differs')
        for policy in model['policies']:
            for i,v in enumerate(policy['values']):
                expected_y=geometry['bottom']-(geometry['bottom']-geometry['top'])*v/55000
                require(abs(geometry['points'][policy['id']][i][1]-expected_y)<.001,'Graph per-request Y scale or inputs changed')
            require(policy['label'] in ''.join(svg.itertext()) and str(policy['total']//1000)+'k total' in ''.join(svg.itertext()),'Wide graph label/total missing')
    root=(ROOT/'README.md').read_text();static=(ROOT/'docs/README_STATIC.md').read_text();markup=Markup();markup.feed(root)
    require(all('height' not in attrs for _,attrs in markup.media),'Forced image/source height can distort production sizing')
    require(all(attrs.get('width','').isdigit() or attrs.get('width') in ['49.5%','100%'] for tag,attrs in markup.media if tag=='img'),'Main image cap must be numeric')
    require(all('width' not in attrs or (attrs['width'].isdigit() and '(max-width:767px)' in attrs.get('media','')) for tag,attrs in markup.media if tag=='source'),'Only numeric mobile source width overrides are allowed')
    require(root.count('separator.gif')==2 and root.count('/identity.svg')==0 and '<!-- portrait-pair:' not in root and '<table>' not in root,'Custom/legacy media table remains')
    require(not re.search(r'(?:src|srcset)="[^"]+\.gif',static),'Static edition embeds animation')
    for row in model['requests']:require(f"| {row['request']} | {row['values']['growing']:,} | {row['values']['curated']:,} | {row['values']['scoped']:,} |" in root,'Missing native exact input table')
    for term in ['label.py','Untitled','TypeError','MiX  Case','66.7','33.3','60k + H','H = 30k','UNKNOWN','not a CAPRI benchmark','Prefix caching'] :require(term in root,'Essential native meaning missing: '+term)
    require(root.index('CAPRI is an experimental')<root.index('/workflow-panel')<root.index('/graph-graph-wide')<root.index('/horizon-panel')<root.index('/handoff-portrait'),'Reading order drifted')
    require(root.count('/separator.gif')==2 and len(re.findall(r'<img[^>]+src="[^"]*/separator.png"',static))==2,'Separator normal/static selection lost')
    for name in ['requirements','closing']:
        lesson=config['lessons'][name]
        require(not lesson.get('static_only') and not lesson.get('static_layouts'),'Support animation still gated off')
        require(lesson['fps']==lesson['source_fps']==30 and lesson['duration_ms']==lesson['source_duration_ms'],'Source support pace changed')
        for layout in ['support','support-wide']:require(name+'-'+layout+'.gif' in root,'Mobile/desktop normal support must animate')
    require('Agentic Loop Prompting' in root and root.count('/identity.svg')==0,'Requested identity missing')
    companion=(ROOT/'showcase/capri/source-match/companion/index.html').read_text()
    for text in [root,static,companion]:
        require(not re.search(r'(?:identity(?:-mobile)?\.svg|story-identity)',text),'Detached identity strip remains')
    for name in ['hero.svg','hero-overlay.svg']:
        text=(ROOT/'showcase/capri'/name).read_text()
        require(text.count('id="hero-subtitle"')==1 and 'AGENTIC LOOP PROMPTING' in text,'In-art subtitle missing')
    families={f for lesson in config['lessons'].values() for f in lesson['families']};require(families=={'sharks','horizon','hands','rain','dots','cat','stack'},'Source family lost')
    records=[];alpha_samples=0;selected=[]
    for name,lesson in config['lessons'].items():
        role=formats['layouts'][lesson['root_layout']];cap=formats['families'][role]['display_width'];root_static=lesson.get('static_only') or lesson['root_layout'] in lesson.get('static_layouts',[]);selected_path=f"exports/{name}-{lesson['root_layout']}.{'png' if root_static else 'gif'}"
        require('/'+selected_path in root,'Root mapping omitted: '+name)
        node=next((attrs for tag,attrs in markup.media if tag=='img' and attrs.get('src','').endswith('/'+selected_path)),None);require(node and node['width']==str(cap),'Display cap mismatch: '+name);selected.append(STORY/selected_path)
        for layout in lesson['layouts']:
            d=formats['families'][formats['layouts'][layout]];size=[d['width'],d['height']];base=STORY/'exports'/f'{name}-{layout}';poster=base.with_suffix('.png');require(list(Image.open(poster).size)==size,'Actual still bounds differ: '+str(base))
            if lesson.get('static_only') or layout in lesson.get('static_layouts',[]):continue
            gif=base.with_suffix('.gif');record=json.loads(base.with_name(base.name+'-timeline.json').read_text());require(sha(gif)==record['gif_sha256'] and sha(poster)==record['poster_sha256'],'Stale export identities: '+name)
            delay=1000//lesson['fps'];durations=[];states=set()
            with Image.open(gif) as im:
                require(list(im.size)==size and im.info.get('loop')==0,'Actual GIF bounds/loop differ: '+name)
                for i in range(im.n_frames):im.seek(i);durations.append(im.info.get('duration',0));states.add(hashlib.sha256(im.convert('RGB').tobytes()).hexdigest())
            require(sum(durations)==lesson['duration_ms'] and all(t>0 and t%10==0 for t in durations),'Encoded cadence differs: '+name)
            require(len(states)>1 and len(record['frames'])==round(lesson['duration_ms']*lesson['fps']/1000),'Frozen/incomplete source progression: '+name)
            for i,frame in enumerate(record['frames']):
                t=i*1000/lesson['fps'];require(frame['time_ms']==t and abs(frame['state']['time']-t)<.001,'Shared source clock differs')
                for member,state in frame['state']['scenes'].items():
                    if state['sourceTime'] is not None:require(abs(state['sourceTime']-(t%500 if member=='rain' else t)/1000)<.021,'Source footage clock differs: '+member)
                    if member in ['horizon','sharks']:require(state['native'],'Fallback used in primary native export')
                bounds=frame['actor_bounds'];alpha_samples+=len(bounds)
                require(all(min(item['margins'])>=0 and item['uniform_surface'] for item in bounds),'Clipped/nonuniform body: '+name)
                if name in ['workflow','brief','horizon','handoff']:require(bool(bounds),'Missing meaningful full-body figure: '+name)
            require(gif.stat().st_size<=8000000,'Media exceeds unchanged source snapshot bound')
            records.append({'lesson':name,'layout':layout,'size':size,'bytes':gif.stat().st_size,'duration_ms':sum(durations),'distinct_states':len(states),'sample_fps':lesson['fps']})
    manifest=json.loads((STORY/'BUILD_MANIFEST.json').read_text())
    for item in manifest['files']:require(sha(STORY/item['path'])==item['sha256'],'Story manifest mismatch: '+item['path'])
    hero=ROOT/'showcase/capri/hero.gif';unique={p.resolve() for p in [hero,*selected,STORY/'separator.gif']};counted=[hero,*selected,STORY/'separator.gif',STORY/'separator.gif']
    return {'status':'PASS','evidence_class':'ILLUSTRATIVE_INPUTS_NOT_MODEL_RUN','main_reference_families':sorted(families),'root_media_unique_bytes':sum(p.stat().st_size for p in unique),'root_media_occurrence_bytes':sum(p.stat().st_size for p in counted),'root_selections':[str(p.relative_to(ROOT)) for p in selected],'actor_alpha_samples':alpha_samples,'assets':records,'scope':'Actual output dimensions/caps, math, preserved source clocks, decoded cadence and full-cycle alpha bounds. Not physical display, native qualification or human/perceptual acceptance.'}
if __name__=='__main__':
    try:result=check()
    except Exception as error:result={'status':'FAIL','error':str(error)}
    print(json.dumps(result,indent=2));sys.exit(result['status']!='PASS')
