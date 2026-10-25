"""Check actual encoded subtitle derivatives against the pinned original hero."""
from pathlib import Path
import hashlib,json,math,re
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1];MEDIA=ROOT/'showcase/capri'
ORIGINAL_GIF='e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517'
def check():
    original=MEDIA/'sources/hero-v7'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(original/'hero.gif')==ORIGINAL_GIF,'Original pinned hero identity changed'
    record=json.loads((MEDIA/'BUILD.json').read_text())
    assert record['subtitle']['font']=='fonts/BarlowCondensed-ExtraBoldItalic.ttf'
    assert record['subtitle']['text']=='AGENTIC LOOP PROMPTING'
    assert record['subtitle']['diagonal_clearance']>=30 and record['subtitle']['visible_left']==52.83
    for n in ['hero.svg','hero-overlay.svg']:
        text=(MEDIA/n).read_text();base=(original/n).read_text()
        assert text.count('id="hero-subtitle"')==1 and 'fill="#ff1265"' in text
        match=re.search(r'<g id="hero-subtitle".*?</g>',text,re.S);assert match
        assert 'AGENTIC LOOP PROMPTING' in match[0] and '<text' not in match[0]
        assert text.replace(match[0],'')==base,'Original hero master altered outside added glyph group'
        assert 'scale(0.055,-0.055)' in match[0],'Nonuniform/skewed or wrong-size lettering'
    box=record['subtitle']['ink_box'];roi=(math.floor(box[0]/1.4)-2,math.floor(box[1]*343/480)-2,math.ceil(box[2]/1.4)+2,math.ceil(box[3]*343/480)+2)
    timing=[];original_timing=[];pixels=[]
    with Image.open(original/'hero.gif') as before,Image.open(MEDIA/'hero.gif') as after:
        assert before.size==after.size==(1000,343) and before.n_frames==after.n_frames==48
        assert before.info.get('loop')==after.info.get('loop')==0
        for i in range(48):
            before.seek(i);after.seek(i);timing.append(after.info['duration']);original_timing.append(before.info['duration'])
            a=after.convert('RGB');b=before.convert('RGB');diff=ImageChops.difference(a,b);bounds=diff.getbbox()
            assert bounds and bounds[0]>=roi[0] and bounds[1]>=roi[1] and bounds[2]<=roi[2] and bounds[3]<=roi[3],(i,bounds,roi)
            pixels.append(hashlib.sha256(a.crop(roi).tobytes()).hexdigest())
        assert timing==original_timing and sum(timing)==4000
    assert len(set(pixels))==1,'Subtitle changes between frames'
    with Image.open(original/'hero.png') as before,Image.open(MEDIA/'hero.png') as after:
        assert before.size==after.size==(1400,480)
        bounds=ImageChops.difference(before.convert('RGB'),after.convert('RGB')).getbbox()
        assert bounds and bounds[0]>=50 and bounds[1]>=374 and bounds[2]<=568 and bounds[3]<=418,('Static poster changed beyond subtitle',bounds)
    for n,h in record['original'].items():assert sha(original/n)==h
    for n,h in record['derived'].items():assert sha(MEDIA/n)==h
    return dict(status='PASS',frames=48,duration_ms=4000,subtitle_uniform_in_all_frames=True,unchanged_decoded_pixels_outside_subtitle=True,static_unchanged_outside_subtitle=True,subtitle=record['subtitle'],original_gif_sha256=ORIGINAL_GIF,derived_gif_sha256=sha(MEDIA/'hero.gif'),scope='Actual SVG/decoded frame and original identity checks; human legibility and perceptual approval separate.')
if __name__=='__main__':print(json.dumps(check(),indent=2))
