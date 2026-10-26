"""Verify transparent-left delivery, unframed source playback and unchanged approved type."""
from pathlib import Path
import hashlib,json,subprocess,tempfile,xml.etree.ElementTree as ET
from unittest.mock import patch
import numpy as np
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri';SCENE=MEDIA/'hero-scene'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check():
    from capri_hero_scene import HeroScene
    pinned={'sources/hero-v7/hero.gif':'e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517','sources/capri-19.gif':'f40d1e6b1c3fdb1374d988fe07f18b6c3f2a42010aabc72ed5bcb30d79dac17b','hero-scene/01-terminal.mp4':'41e16e3fbf294f65a2310e9cf43f437b04e84df8f63927e91b09cbf027a97865','hero-scene/02-clouds.jpg':'6f9783c5eb8be26f2a8a799a6638f5b1c94550c75114d657e54fbc8bc11511de','hero-scene/portrait-master.png':'b70de4910092b34a710d01d461cd14684e5266e1affeb66c5e8ed3b71b3248ee','fonts/chakra-petch/ChakraPetch-SemiBoldItalic.ttf':'4e11c1bec71511bbea8a3bc3f4cebff479bb9681961d691a36f99e5234d8fe89','fonts/chakra-petch/OFL.txt':'13831d02389d917d22fcfa6c79f98f8acbf61d230add0e73a4d4dc5f3bfb9e56'}
    for name,h in pinned.items():assert sha(MEDIA/name)==h,('Fixed source changed',name)
    record=json.loads((MEDIA/'BUILD.json').read_text());timeline=json.loads((SCENE/'timeline.json').read_text());cfg=json.loads((SCENE/'scene.json').read_text())
    assert cfg['active_generated_portrait'] is False and record['active_generated_portrait'] is False
    original_open=Image.open
    def fixed_open(path,*args,**kwargs):
        assert not isinstance(path,(str,Path)) or Path(path).name not in ['portrait-master.png','02-clouds.jpg','frame.png'],'Removed historical background or frame loaded by active scene'
        return original_open(path,*args,**kwargs)
    with patch('PIL.Image.open',side_effect=fixed_open):scene=HeroScene(MEDIA)
    assert scene.right_placement==(550,0,850,480) and cfg['left_polygon']==[[0,0],[690,0],[582,480],[0,480]]
    old=ET.parse(MEDIA/'sources/hero-v7/hero-overlay.svg').getroot();new=ET.parse(SCENE/'brand.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
    prior=next(g for g in old if g.get('transform')=='translate(45,345) scale(0.27,-0.27)');word=new.find('s:g[@id="hero-wordmark"]',ns)
    assert cfg['wordmark']['original_transform']==prior.get('transform')
    assert word.get('transform')==cfg['wordmark']['display_transform']=='translate(45,317) scale(0.27,-0.27)'
    assert [g.get('d') for g in word.iter() if g.tag.endswith('path')]==[g.get('d') for g in prior.iter() if g.tag.endswith('path')],'Barlow shape changed'
    descriptor=new.find('s:g[@id="hero-subtitle"]',ns);assert descriptor.get('aria-label')=='AGENTIC LOOPING'
    assert [g.get('data-text') for g in descriptor]==['AGENTIC LOOPING']
    for gradient,expected in [('word-gradient',['#ff76af','#ff1265','#a20a50']),('descriptor-gradient',['#eefff6','#b1ffcf','#28fb86'])]:
        g=new.find(f's:defs/s:linearGradient[@id="{gradient}"]',ns);assert g.get('gradientUnits')=='userSpaceOnUse' and [s.get('stop-color') for s in g]==expected
    for element in new.iter():
        assert element.get('stroke') in (None,'none') and not any(k in element.attrib for k in ['stroke-width','filter','paint-order']),'Persistent type outline/effect'
    mask_svg=ET.parse(SCENE/'wordmark-mask.svg').getroot();mask_word=next(g for g in mask_svg if g.get('transform'))
    assert mask_word.get('transform')==word.get('transform')
    assert [g.get('d') for g in mask_word.iter() if g.tag.endswith('path')]==[g.get('d') for g in word.iter() if g.tag.endswith('path')]
    word_alpha=np.asarray(Image.open(SCENE/'wordmark-mask.png').getchannel('A'));brand_alpha=np.asarray(Image.open(SCENE/'brand.png').getchannel('A'))
    assert np.array_equal(word_alpha[:333],brand_alpha[:333]),'Brand raster has expanded outline/ghost around wordmark'
    assert not word_alpha[333:].any(),'Mask remained at old display location'
    assert not ImageChops.difference(scene.brand_at(scene.state(0)).convert('RGB'),scene.brand_at(scene.state(2500)).convert('RGB')).getbbox(),'Persistent type copy/effect outside brief rupture/sheen'
    assert ImageChops.difference(scene.brand.convert('RGB'),scene.brand_at(scene.state(1800)).convert('RGB')).getbbox(),'Sheen no longer follows moved wordmark'
    assert cfg['left_background']=='transparent' and cfg['frame']=='none' and cfg['join']=='pre-V11 hard diagonal'
    assert not (SCENE/'frame.png').exists() and not (SCENE/'frame.svg').exists()
    left=np.asarray(scene.mask)>0;right=~left
    assert right.sum()==366192,'Original hard diagonal footprint changed'
    type_record=json.loads((SCENE/'type.json').read_text());assert all(abs(line['ink_box'][0]-52.83)<.001 and line['diagonal_clearance']>80 for line in type_record['lines'])
    for n in ['hero.svg','hero-overlay.svg']:
        text=(MEDIA/n).read_text();assert text.count('id="hero-subtitle"')==1 and 'AGENTIC LOOPING' in text and 'PROMPTING' not in text and '<text' not in text
        assert all(token not in text for token in ['outer-frame','internal-rail','left-environment','plate-gradient'])
    source_delays=[];source_hashes=[];transparent_counts=[]
    with Image.open(MEDIA/'sources/capri-19.gif') as clip:
        for i,t in enumerate(scene.timestamps):
            clip.seek(i);source_delays.append(clip.info['duration']);source_hashes.append(hashlib.sha256(clip.convert('RGB').tobytes()).hexdigest())
            expected=Image.new('RGB',(1400,480));expected.paste(clip.convert('RGB').resize((850,480),Image.Resampling.LANCZOS),(550,0));actual=scene.render(t);pixels=np.asarray(actual)
            assert np.array_equal(pixels[:,:,:3][right],np.asarray(expected)[right]),('Original right footage changed',i)
            assert np.all(pixels[:,:,3][right]==255),('Hole in right footage',i)
            brand=np.asarray(scene.brand_at(scene.state(t)));assert np.array_equal(pixels[:,:,3][left],brand[:,:,3][left]),('Background/frame behind left typography',i)
            empty=left&(brand[:,:,3]==0);assert np.all(pixels[:,:,3][empty]==0) and empty.sum()>left.sum()*.6,('Left is not transparent',i)
            # Top, bottom and far-left probes catch the removed enclosing frame independently of title shape.
            assert pixels[0,:680,3].max()==pixels[-1,:570,3].max()==pixels[:,:25,3].max()==0,('Frame restored unexpectedly',i)
            transparent_counts.append(int(empty.sum()))
            assert scene.state(t)['source_frame']==i and scene.state(t+source_delays[-1]/2)['source_frame']==i
    delays=[];hashes=[];disposals=set();alpha_counts=[]
    with Image.open(MEDIA/'hero.gif') as gif:
        assert gif.size==(1000,343) and gif.n_frames==120 and gif.info.get('loop')==0
        for i in range(gif.n_frames):
            gif.seek(i);rgba=gif.convert('RGBA');delays.append(gif.info['duration']);disposals.add(gif.disposal_method)
            canonical=rgba.copy();canonical.paste((0,0,0,0),mask=canonical.getchannel('A').point(lambda a:255 if a==0 else 0))
            h=hashlib.sha256(canonical.tobytes()).hexdigest();hashes.append(h);assert h==timeline['quantized_rgba_sha256'][i],('Encoded alpha trails or palette drift',i)
            alpha=np.asarray(rgba.getchannel('A'));assert set(np.unique(alpha))=={0,255};assert not alpha[:,:17].any() and not alpha[:2,:480].any(),('Opaque GIF background/frame',i)
            alpha_counts.append(int((alpha==0).sum()))
    assert disposals=={1,2},'Retain compact deltas and clear disappearing alpha'
    assert record['disposal_methods'].count(2)>0
    assert delays==source_delays==timeline['delays_ms'] and len(delays)==120 and sum(delays)==4000
    assert len(set(hashes))==120 and (MEDIA/'hero.gif').stat().st_size<=8000000
    assert record['frames']==120 and record['duration_ms']==4000 and timeline['source_timestamps_ms']==scene.timestamps
    assert not ImageChops.difference(scene.render(0),scene.render(4000)).getbbox()
    assert scene.render(cfg['poster_ms']).tobytes()==Image.open(MEDIA/'hero.png').convert('RGBA').tobytes()
    # Render the actual SVG on both page colors to catch accidental opaque fills or stale exports.
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)/'hero.png';subprocess.run(['rsvg-convert',str(MEDIA/'hero.svg'),'-o',str(output)],check=True)
        svg=Image.open(output).convert('RGBA');poster=Image.open(MEDIA/'hero.png').convert('RGBA');parity=[]
        for color in ['#ffffff','#0d1117']:
            bg=Image.new('RGBA',scene.size,color);a=np.asarray(Image.alpha_composite(bg,svg)).astype(int);b=np.asarray(Image.alpha_composite(bg,poster)).astype(int);difference=np.abs(a-b)
            assert difference.max()<=2,('SVG/PNG mismatch',color,int(difference.max()));parity.append({'background':color,'maximum_channel_error':int(difference.max())})
    for n,h in record['derived'].items():assert sha(MEDIA/n)==h,('Stale derivative',n)
    assert sha(SCENE/'wordmark-mask.png')==record['wordmark_mask_sha256']
    assert sha(SCENE/'scene.json')==record['scene_sha256'] and sha(SCENE/'brand.svg')==record['brand_svg_sha256'] and sha(SCENE/'brand.png')==record['brand_png_sha256']
    return {'status':'PASS','delivery':[1000,343],'frames':120,'distinct_decoded_frames':len(set(hashes)),'duration_ms':4000,'delays_match_original_source':True,'source_sample_hashes':source_hashes,'right_exact_source_checks':120,'right_pixels_checked_per_frame':int(right.sum()),'right_region_exclusions':0,'transparent_master_pixels_minimum':min(transparent_counts),'transparent_gif_pixels_minimum':min(alpha_counts),'gif_disposal':sorted(disposals),'frame_removed':True,'fill_only_type_and_moved_mask':True,'active_portrait_loaded':False,'wordmark_geometry_preserved':True,'descriptor_font_and_ink_alignment':'PASS','shared_scene_loop_exact':True,'svg_png_compositing_parity':parity,'bytes':(MEDIA/'hero.gif').stat().st_size,'palette_colors':record['palette_colors'],'scope':'Actual encoded/source/alpha/geometry checks; continuous human perceptual, physical-device and artistic approval remain separate.'}
if __name__=='__main__':print(json.dumps(check(),indent=2))
