"""Verify V9 encoded delivery, shared scene, fixed inputs, source/pose records and loop contracts."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
import numpy as np
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri';SCENE=MEDIA/'hero-scene'
ORIGINAL_GIF='e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check():
    from capri_hero_scene import HeroScene
    assert sha(MEDIA/'sources/hero-v7/hero.gif')==ORIGINAL_GIF,'Pinned original hero changed'
    assert sha(SCENE/'01-terminal.mp4')=='41e16e3fbf294f65a2310e9cf43f437b04e84df8f63927e91b09cbf027a97865'
    assert sha(SCENE/'02-clouds.jpg')=='6f9783c5eb8be26f2a8a799a6638f5b1c94550c75114d657e54fbc8bc11511de'
    assert sha(SCENE/'03-pose.jpg')=='97b5fd5e68db030dee4becf3af48eca38619ea98443442989149cc22620c0d6f'
    pose=json.loads((SCENE/'POSE_GENERATION.json').read_text());record=json.loads((MEDIA/'BUILD.json').read_text());config=json.loads((SCENE/'scene.json').read_text());timeline=json.loads((SCENE/'timeline.json').read_text())
    assert pose['mode']=='built-in imagegen' and sha(SCENE/'portrait-master.png')==pose['selected_sha256']==record['portrait_sha256']
    assert sha(SCENE/'scene.json')==record['scene_sha256']
    assert sha(SCENE/'brand.svg')==record['brand_svg_sha256'] and sha(SCENE/'brand.png')==record['brand_png_sha256']
    im=Image.open(SCENE/'portrait-master.png');assert im.mode=='RGBA'
    alpha=np.asarray(im.getchannel('A'));assert alpha.min()==0 and alpha.max()>=254 and (alpha==0).mean()>.4
    box=Image.fromarray(np.where(alpha>32,255,0).astype('uint8')).getbbox()
    assert list(box)==config['portrait']['alpha_bbox'] and min(box[0],box[1],im.width-box[2],im.height-box[3])>=30
    assert max(int(x.max()) for x in [alpha[0],alpha[-1],alpha[:,0],alpha[:,-1]])<=1,'Visible silhouette reaches master edge'
    brand=ET.parse(SCENE/'brand.svg').getroot();original=ET.parse(MEDIA/'sources/hero-v7/hero-overlay.svg').getroot()
    group=next(g for g in brand if g.get('transform')=='translate(45,345) scale(0.27,-0.27)')
    prior=next(g for g in original if g.get('transform')=='translate(45,345) scale(0.27,-0.27)')
    assert ET.tostring(group)==ET.tostring(prior),'Original CAPRI glyphs/placement altered'
    subtitle=next(g for g in brand if g.get('id')=='hero-subtitle')
    assert subtitle.get('aria-label')=='AGENTIC LOOP PROMPTING' and subtitle.get('fill')=='#ff1265' and 'scale(0.055,-0.055)' in subtitle.get('transform')
    assert len(brand)==2
    for n in ['hero.svg','hero-overlay.svg']:
        s=(MEDIA/n).read_text();assert s.count('id="hero-subtitle"')==1 and '1400' in s and '480' in s and '<text' not in s
    snippets=(SCENE/'terminal-snippets.txt').read_text()
    assert snippets=='\n'.join((ROOT/'tools/capri_context_budget.py').read_text().splitlines()[19:76])+'\n','Decorative glyphs are no longer the declared actual source excerpt'
    source=json.loads((SCENE/'SOURCE_RECORD.json').read_text());assert source['terminal_substitution']['snippet_sha256']==sha(SCENE/'terminal-snippets.txt')
    delays=[];identities=[];colors=[];eye=config['portrait']['eye_anchor'];ex,ey=round(eye[0]*1000/1400),round(eye[1]*343/480)
    with Image.open(MEDIA/'hero.gif') as gif:
        assert gif.size==(1000,343) and gif.n_frames==300 and gif.info.get('loop')==0
        for i in range(300):
            gif.seek(i);rgb=gif.convert('RGB');delays.append(gif.info.get('duration'));assert gif.disposal_method==1
            identities.append(hashlib.sha256(rgb.tobytes()).hexdigest())
            assert identities[-1]==timeline['quantized_rgb_sha256'][i],'Delta encoding ghost/color drift'
            pixel=np.asarray(rgb)[ey-12:ey+12,ex-12:ex+12].astype(int);blue=(pixel[:,:,2]>150)&(pixel[:,:,2]>pixel[:,:,0]*1.5)&(pixel[:,:,1]>40)
            assert blue.sum()>25,('Characteristic blue eye lost',i)
            if i in [0,100,117,141,186,255,299]:colors.append(dict(frame=i,phase=timeline['frames'][i]['phase'],rgb_sha256=identities[-1]))
    assert len(set(identities))==300,'Duplicated frames do not establish increased cadence'
    assert delays==[30,30,40]*100 and sum(delays)==10000
    assert record['frames']==300 and record['sampling_fps']==30 and record['duration_ms']==10000
    assert timeline['gif_sha256']==sha(MEDIA/'hero.gif')
    assert (MEDIA/'hero.gif').stat().st_size<=8000000
    scene=HeroScene(MEDIA)
    assert ImageChops.difference(scene.render(0),scene.render(10000)).getbbox() is None,'Shared scene is not periodic'
    assert ImageChops.difference(scene.render(6200),Image.open(MEDIA/'hero.png').convert('RGB')).getbbox() is None,'Still poster differs from clean hacked hold'
    assert scene.state(0)['phase']=='blue' and scene.state(2300)['burst']==0 and scene.state(2900)['burst']==1 and scene.state(3333)['spark']
    assert not scene.state(3100)['spark'] and float(scene.takeover(3.4).max())==0
    assert 0<float(scene.takeover(3.9).mean())<1 and float(scene.takeover(6.2).min())==1 and float(scene.takeover(9.999).max())==0
    assert scene.state(6200)['burst'] is None and scene.state(6200)['portrait_scale']==1
    assert ImageChops.difference(scene.portrait,scene.portrait_at(6.2,scene.state(6200))).getbbox() is None
    expected=Image.open(SCENE/'02-clouds.jpg').convert('RGB').resize((1440,480),Image.Resampling.LANCZOS).crop((20,0,1420,480))
    assert ImageChops.difference(scene.cloud_image,expected).getbbox() is None,'Source cloud crop/grid phase replaced'
    for name,h in record['derived'].items():assert sha(MEDIA/name)==h,('Stale derivative',name)
    return dict(status='PASS',delivery=[1000,343],frames=300,distinct_decoded_frames=300,duration_ms=10000,delays_ms=[30,30,40],loop=0,bytes=(MEDIA/'hero.gif').stat().st_size,delta_decode_matches_all_quantized_frames=True,portrait_alpha_bbox=box,visible_master_padding=True,raw_border_alpha_max=1,character_eye_blue_in_all_frames=True,causal_phase_samples=colors,shared_scene_loop_exact=True,cloud_source_crop_exact=True,scope='Actual encoded/source/model checks. Generated pose fidelity, continuous perceptual/physical/hosted review and human acceptance remain separate.')
if __name__=='__main__':print(json.dumps(check(),indent=2))
