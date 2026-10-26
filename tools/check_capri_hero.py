"""Verify restored source playback, clipped effects, outlined type and actual GIF delivery."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
from unittest.mock import patch
import numpy as np
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri';SCENE=MEDIA/'hero-scene'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check():
    from capri_hero_scene import HeroScene
    pinned={'sources/hero-v7/hero.gif':'e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517','sources/capri-19.gif':'f40d1e6b1c3fdb1374d988fe07f18b6c3f2a42010aabc72ed5bcb30d79dac17b','hero-scene/01-terminal.mp4':'41e16e3fbf294f65a2310e9cf43f437b04e84df8f63927e91b09cbf027a97865','hero-scene/02-clouds.jpg':'6f9783c5eb8be26f2a8a799a6638f5b1c94550c75114d657e54fbc8bc11511de','hero-scene/portrait-master.png':'b70de4910092b34a710d01d461cd14684e5266e1affeb66c5e8ed3b71b3248ee','fonts/chakra-petch/ChakraPetch-SemiBoldItalic.ttf':'4e11c1bec71511bbea8a3bc3f4cebff479bb9681961d691a36f99e5234d8fe89','fonts/chakra-petch/OFL.txt':'13831d02389d917d22fcfa6c79f98f8acbf61d230add0e73a4d4dc5f3bfb9e56'}
    for name,h in pinned.items():assert sha(MEDIA/name)==h,('Fixed source changed',name)
    record=json.loads((MEDIA/'BUILD.json').read_text());timeline=json.loads((SCENE/'timeline.json').read_text());cfg=json.loads((SCENE/'scene.json').read_text());source=json.loads((SCENE/'SOURCE_RECORD.json').read_text())
    assert cfg['active_generated_portrait'] is False and record['active_generated_portrait'] is False
    original_open=Image.open
    def fixed_open(path,*args,**kwargs):
        assert not isinstance(path,(str,Path)) or Path(path).name!='portrait-master.png','Historical portrait loaded by active scene'
        return original_open(path,*args,**kwargs)
    with patch('PIL.Image.open',side_effect=fixed_open):scene=HeroScene(MEDIA)
    assert scene.right_placement==(550,0,850,480) and cfg['left_polygon']==[[0,0],[690,0],[582,480],[0,480]]
    old=ET.parse(MEDIA/'sources/hero-v7/hero-overlay.svg').getroot();new=ET.parse(SCENE/'brand.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
    prior=next(g for g in old if g.get('transform')=='translate(45,345) scale(0.27,-0.27)');word=new.find('s:g[@id="hero-wordmark"]',ns)
    assert word.get('transform')==prior.get('transform')
    assert [g.get('d') for g in word.iter() if g.tag.endswith('path')]==[g.get('d') for g in prior.iter() if g.tag.endswith('path')],'Barlow shape changed'
    descriptor=new.find('s:g[@id="hero-subtitle"]',ns);assert descriptor.get('aria-label')=='AGENTIC LOOP PROMPTING'
    assert [g.get('data-text') for g in descriptor]==['AGENTIC LOOP','PROMPTING']
    for gradient,expected in [('word-gradient',['#ff76af','#ff1265','#a20a50']),('descriptor-gradient',['#eefff6','#b1ffcf','#28fb86'])]:
        g=new.find(f's:defs/s:linearGradient[@id="{gradient}"]',ns);assert g.get('gradientUnits')=='userSpaceOnUse' and [s.get('stop-color') for s in g]==expected
    type_record=json.loads((SCENE/'type.json').read_text());assert all(abs(line['ink_box'][0]-52.83)<.001 and line['diagonal_clearance']>150 for line in type_record['lines'])
    for n in ['hero.svg','hero-overlay.svg']:
        text=(MEDIA/n).read_text();assert text.count('id="hero-subtitle"')==1 and 'AGENTIC LOOP PROMPTING' in text and '<text' not in text
    snippets=(SCENE/'terminal-snippets.txt').read_text();assert snippets=='\n'.join((ROOT/'tools/capri_context_budget.py').read_text().splitlines()[19:76])+'\n';assert source['terminal_substitution']['snippet_sha256']==sha(SCENE/'terminal-snippets.txt')
    expected_cloud=Image.open(SCENE/'02-clouds.jpg').convert('RGB').resize((1440,480),Image.Resampling.LANCZOS).crop((360,0,1050,480));assert not ImageChops.difference(scene.cloud_image,expected_cloud).getbbox()
    source_delays=[];source_hashes=[];right_checks=[];outside=np.asarray(scene.mask)==0
    with Image.open(MEDIA/'sources/capri-19.gif') as clip:
        for i,t in enumerate(scene.timestamps):
            clip.seek(i);source_delays.append(clip.info['duration']);source_hashes.append(hashlib.sha256(clip.convert('RGB').tobytes()).hexdigest())
            expected=Image.new('RGB',(1400,480),'#100a19');expected.paste(clip.convert('RGB').resize((850,480),Image.Resampling.LANCZOS),(550,0));actual=scene.render(t)
            assert np.array_equal(np.asarray(actual)[outside],np.asarray(expected)[outside]),('Authored effect leaked into original right',i)
            assert scene.state(t)['source_frame']==i and scene.state(t+source_delays[-1]/2)['source_frame']==i
            right_checks.append(i)
    delays=[];hashes=[];red_shares={}
    with Image.open(MEDIA/'hero.gif') as gif:
        assert gif.size==(1000,343) and gif.n_frames==120 and gif.info.get('loop')==0
        left=np.asarray(scene.mask.resize((1000,343),Image.Resampling.NEAREST))>0
        for i in range(gif.n_frames):
            gif.seek(i);rgb=gif.convert('RGB');delays.append(gif.info['duration']);assert gif.disposal_method==1
            h=hashlib.sha256(rgb.tobytes()).hexdigest();hashes.append(h);assert h==timeline['quantized_rgb_sha256'][i],('Delta ghost or palette drift',i)
            if i in [0,30,31,32,33,75,119]:
                pixels=np.asarray(rgb).astype(float);red=(pixels[:,:,0]>pixels[:,:,2]*1.4)&(pixels[:,:,0]>pixels[:,:,1]*1.4)&(pixels[:,:,0]>45);red_shares[i]=float(red[left].mean())
    assert delays==source_delays==timeline['delays_ms'] and len(delays)==120 and sum(delays)==4000
    assert len(set(hashes))==120 and (MEDIA/'hero.gif').stat().st_size<=8000000
    assert record['frames']==120 and record['duration_ms']==4000 and timeline['source_timestamps_ms']==scene.timestamps
    assert red_shares[32]>red_shares[0]+.15,'Actual encoded left sky failed to turn red'
    assert scene.state(1000)['red_fraction']==0 and scene.state(1070)['red_fraction']==1 and scene.state(1100)['rupture'] is False
    state=scene.state(1070);red=scene.left_environment({**state,'red_fraction':1});assert not ImageChops.difference(red,scene.left_environment(state)).getbbox()
    assert scene.state(3500)['red_fraction']==1 and scene.state(3970)['red_fraction']==0
    assert not ImageChops.difference(scene.render(0),scene.render(4000)).getbbox()
    assert not ImageChops.difference(scene.render(cfg['poster_ms']),Image.open(MEDIA/'hero.png').convert('RGB')).getbbox()
    for n,h in record['derived'].items():assert sha(MEDIA/n)==h,('Stale derivative',n)
    assert sha(SCENE/'scene.json')==record['scene_sha256'] and sha(SCENE/'brand.svg')==record['brand_svg_sha256'] and sha(SCENE/'brand.png')==record['brand_png_sha256']
    return {'status':'PASS','delivery':[1000,343],'frames':120,'distinct_decoded_frames':len(set(hashes)),'duration_ms':4000,'delays_match_original_source':True,'source_sample_hashes':source_hashes,'right_region_exact_source_checks':len(right_checks),'effect_leakage_pixels':0,'active_portrait_loaded':False,'wordmark_geometry_preserved':True,'descriptor_font_and_ink_alignment':'PASS','cloud_crop_exact':True,'actual_encoded_left_red_shares':red_shares,'attack_to_red_ms':70,'shared_scene_loop_exact':True,'bytes':(MEDIA/'hero.gif').stat().st_size,'palette_colors':record['palette_colors'],'scope':'Encoded/source/geometry checks; palette quantization changes colors. Continuous human perceptual, device, hosted UI and artistic approval remain separate.'}
if __name__=='__main__':print(json.dumps(check(),indent=2))
