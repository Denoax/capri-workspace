from pathlib import Path
import json,base64,io
from rebuild_jointed_actor import layers,KEYS,OUT

meta=json.loads((OUT/'KEYFRAMES.json').read_text());box=meta['fixed_crop']
camera=[-150+box[0]*1850/240,-300+box[1]*1850/240,(box[2]-box[0])*1850/240,(box[3]-box[1])*1850/240]
items=[]
for tag,im in layers.items():
 b=im.getchannel('A').getbbox();crop=im.crop(b);out=io.BytesIO();crop.save(out,format='WEBP',quality=70,method=6)
 (OUT/f'part-{tag}.webp').write_bytes(out.getvalue())
 items.append({'tag':tag,'origin':[b[0]*2,b[1]*2],'size':[crop.width*2,crop.height*2],'src':'data:image/webp;base64,'+base64.b64encode(out.getvalue()).decode()})
record={'fps':30,'duration_ms':2800,'camera':camera,'keys':KEYS.tolist(),'parts':items}
(OUT/'rig-assets.json').write_text(json.dumps(record,separators=(',',':')))
print('Layer data bytes',(OUT/'rig-assets.json').stat().st_size)
