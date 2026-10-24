#!/usr/bin/env python3
"""Source, timing and delivery contracts for the source-match presentation.

These checks do not grade aesthetics, qualify the native runtime or claim a
human watched continuous motion. Run through check_capri_presentation.py.
"""
from pathlib import Path
import base64,hashlib,json,re,subprocess,sys
from PIL import Image
from capri_source_storage import read_source
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri/source-match'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def timed_frames(path,mode):
    with Image.open(path) as image:
        for i in range(image.n_frames):
            image.seek(i);yield image.convert(mode).copy(),image.info.get('duration',0),getattr(image,'disposal_method',None)
def expanded(path,mode,delay=40):
    for image,duration,_ in timed_frames(path,mode):
        require(duration>0 and duration%delay==0,f'Invalid master cadence: {path.name}')
        for _ in range(round(duration/delay)):yield image

def check():
    source=MEDIA/'source';manifest=json.loads((source/'MANIFEST.json').read_text());total=0
    for item in manifest['files']:
        data=read_source(item['path']);require(len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],'Immutable source changed: '+item['path']);total+=item['bytes']
    rig=json.loads((MEDIA/'actor/RIG.json').read_text());require(set(rig['poses'])=={'plan','build','review'},'Three distinct masters required')
    for name,pose in rig['poses'].items():
        require(len(pose['parts'])==10 and len(pose['keys'])>=6,'Incomplete editable articulation: '+name)
        for anchor in ['eye','eyes','mouth','neck','hip','rs','re','ls','le','gh','gk','ph','pk','tip']:require(anchor in pose,'Missing anchor: '+anchor)
        for part in pose['parts']:
            path=MEDIA/'companion'/part['src'];require(sha(path)==part['sha256'],'Changed rig part: '+part['src'])
            with Image.open(path) as image:require(image.mode=='RGBA' and image.size==tuple(part['size']),'Rig part loses alpha/size')
        with Image.open(MEDIA/'actor'/f'{name}-rgba.png') as image:require(image.mode=='RGBA' and image.getchannel('A').getextrema()==(0,255),'Invalid alpha master: '+name)
    plates=json.loads((MEDIA/'plates/PLATES.json').read_text())
    for item in plates:require(sha(MEDIA/'plates'/item['file'])==item['sha256'],'Plate hash mismatch')
    eyes=json.loads((MEDIA/'plates/CAT_EYES.json').read_text());require(len(eyes)==258 and all(abs(x['time']-i/30)<1e-9 for i,x in enumerate(eyes)),'Eye source-clock mismatch')
    data=json.loads((MEDIA/'context-budget-results.json').read_text())
    actual=json.loads(subprocess.check_output([sys.executable,str(ROOT/'tools/capri_context_budget.py')]))
    require(data==actual and data['total_assumed_input_tokens']=={'growing':180000,'curated':90000,'scoped':60000},'Assumption calculator mismatch')
    require(data['measured_capri_savings'] is None and data['quality_equivalence']=='untested','Invented benchmark claim')
    records=[]
    for path in sorted((MEDIA/'exports').glob('*-timeline.json')):
        record=json.loads(path.read_text());name=path.name.removesuffix('-timeline.json');gif=path.with_name(name+'.gif');poster=path.with_name(name+'.png');delay=1000//record['fps']
        require(sha(gif)==record['gif_sha256'] and sha(poster)==record['poster_sha256'],'Stale exported hash: '+name)
        require(record['fps'] in [25,50] and len(record['timeline'])==record['sample_count'],'Invalid sampling contract: '+name)
        durations=[];distinct=set();disposals=set();opaque=True
        with Image.open(gif) as im:
            require(im.size==tuple(record['size']) and im.info.get('loop')==0,'GIF delivery mismatch: '+name)
            for i in range(im.n_frames):
                im.seek(i);frame=im.convert('RGBA');duration=im.info.get('duration',0);durations.append(duration);disposals.add(im.disposal_method);distinct.add(hashlib.sha256(frame.tobytes()).hexdigest());opaque &= frame.getchannel('A').getextrema()==(255,255)
            frames=im.n_frames
        require(sum(durations)==record['planned_duration_ms'] and all(d>0 and d%delay==0 for d in durations),'Decoded timing mismatch: '+name)
        require(len(distinct)>1,'Frozen animation: '+name)
        require(opaque if name!='actor-wide' else disposals=={2},'Alpha/disposal mismatch: '+name)
        for i,sample in enumerate(record['timeline']):require(abs(sample['time_ms']-i*delay)<1e-6,'Nonuniform scene clock: '+name)
        records.append({'asset':name,'bytes':gif.stat().st_size,'size':record['size'],'encoded_frames':frames,'distinct_complete_states':len(distinct),'decoded_duration_ms':sum(durations),'delays_ms':sorted(set(durations)),'disposal':sorted(disposals),'export_sampling_fps':record['fps'],'source':record['source']})
    require(len(records)==16,'Expected15panel exports plus transparent actor')
    rgba=expanded(MEDIA/'exports/actor-rgba.png','RGBA');rgb=expanded(MEDIA/'exports/actor-rgb.png','RGB');alpha=expanded(MEDIA/'exports/actor-alpha.png','L');gif=expanded(MEDIA/'exports/actor-wide.gif','RGBA')
    count=0
    import itertools
    for a,b,c,d in itertools.zip_longest(rgba,rgb,alpha,gif):
        require(all(x is not None for x in [a,b,c,d]),'Alpha/RGB timeline lengths differ');b.putalpha(c);require(a.tobytes()==b.tobytes(),'RGB plus alpha does not reconstruct master')
        box=a.getbbox()
        require(not box or (box[0]>0 and box[1]>0 and box[2]<a.width and box[3]<a.height),'Clipped animated actor')
        require(d.getchannel('A').tobytes()==c.point(lambda v:255 if v>=128 else 0).tobytes(),'Transparent GIF leaves alpha trails');count+=1
    require(count==240,'Actor timeline incomplete')
    html=(MEDIA/'companion/index.html').read_text()
    require(len(re.findall('data:video/mp4;base64,',html))==5,'Required footage is not embedded')
    require('data:font/ttf;base64,' in html and 'data:image/png;base64,' in (MEDIA/'companion/actor-data.js').read_text(),'Required fonts/rig are not embedded')
    scripts=re.findall(r'<script[^>]+src="([^"]+)"',html);require(scripts==['actor-data.js'] and not re.search(r'@import\s+url',html),'Unexpected companion script/font dependency')
    actor_data=(MEDIA/'companion/actor-data.js').read_text();require(actor_data.startswith('window.CAPRI_RIG='),'Missing local actor data')
    embedded=json.loads(actor_data[len('window.CAPRI_RIG='):].strip().removesuffix(';'))
    for name,pose in rig['poses'].items():
        for original,part in zip(pose['parts'],embedded['poses'][name]['parts']):require(hashlib.sha256(base64.b64decode(part['src'].split(',',1)[1])).hexdigest()==original['sha256'],'Embedded actor part changed')
    oversize=[str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts and '__pycache__' not in p.relative_to(ROOT).parts and p.stat().st_size>8_000_000]
    require(not oversize,'Runtime source snapshot limit exceeded: '+str(oversize))
    for font in ['Manrope','Inter','MartianMono']:require((source/f'assets/fonts/{font}/OFL.md').is_file(),'Missing font notice')
    root=(ROOT/'README.md').read_text();static=(ROOT/'docs/README_STATIC.md').read_text()
    require('python -m pip install --require-hashes -r requirements.lock' in root and 'unittest discover -s controller/tests -v' in root,'Quickstart missing')
    require(not re.search(r'(?:src|srcset)="[^"]+\.gif',static),'Animated media in static edition')
    if (ROOT/'showcase/capri/story/story.json').exists():
        configuration=json.loads((ROOT/'showcase/capri/story/story.json').read_text())
        require(all(f'/{name}-wide.' in root for name in configuration['lessons']),'Missing root V3 lesson')
        require({family for lesson in configuration['lessons'].values() for family in lesson['families']}=={'sharks','horizon','hands','rain','dots','cat','stack'},'Missing root source family')
    else:require(all(f'/{name}-wide.gif' in root for name in ['comic','hands','sharks','rain','horizon','cat','dots']),'Missing root source scene')
    require(sha(ROOT/'showcase/capri/hero.gif')=='e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517','Approved hero changed')
    build=json.loads((MEDIA/'BUILD_MANIFEST.json').read_text())
    for item in build['files']:require(sha(MEDIA/item['path'])==item['sha256'],'Build manifest mismatch: '+item['path'])
    return {'status':'PASS','immutable_files':len(manifest['files']),'immutable_payload_bytes':total,'actor_samples_checked':count,'assets':records,'scope':'Hashes, links, decoded cadence/disposal and alpha composition. Not continuous perceptual review, human visual acceptance, physical-device or native qualification.'}
if __name__=='__main__':
    try:result=check()
    except Exception as error:result={'status':'FAIL','error':str(error)}
    print(json.dumps(result,indent=2));sys.exit(result['status']!='PASS')
