#!/usr/bin/env python3
"""Pose-specific lossless cutout layers, calibrated anchors and editable acting keys.

The three supplied full-body masters remain immutable. These are authored fan-art
rigs: rigid segment transforms and small joint overlaps, never rubber-sheet warps.
"""
from pathlib import Path
import hashlib,json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageChops
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'showcase/capri/source-match';OUT=BASE/'actor';SOURCE=BASE/'source/assets/characters/masters'
POSES={
 'plan':{'eye':[752,283],'eyes':[[727,262],[785,298]],'mouth':[745,325],'neck':[737,357],'hip':[803,600],'rs':[817,408],'re':[943,481],'rw':[1155,387],'ls':[652,380],'le':[575,470],'lw':[541,338],'gh':[836,554],'gk':[1050,493],'ph':[806,621],'pk':[1006,637],'tip':[1295,404],
  'regions':{3:[[800,366],[835,375],[962,455],[958,500],[918,476],[794,425]],4:[[916,461],[958,500],[1163,395],[1179,410],[1220,446],[1237,449],[1200,407],[1260,427],[1315,408],[1250,389],[1265,382],[1197,372],[1233,353],[1216,344],[1161,358],[1120,383]],5:[[635,359],[669,382],[590,492],[559,477],[574,446],[625,384]],6:[[559,477],[591,476],[541,347],[629,318],[625,307],[566,319],[606,292],[586,287],[548,310],[570,275],[554,274],[516,304],[491,324]],7:[[782,547],[850,503],[1036,466],[1095,510],[1050,545],[905,569],[829,626],[765,658]],8:[[1035,467],[1094,505],[1253,667],[1269,591],[1290,543],[1322,531],[1355,470],[1337,621],[1339,670],[1306,628],[1304,735],[1334,846],[1270,805],[1225,722],[1238,688],[1130,584]],9:[[758,538],[830,548],[1057,592],[1038,663],[982,681],[811,657]],10:[[974,622],[1050,628],[1150,772],[1231,899],[1210,880],[1243,1013],[1177,969],[1112,943],[1048,822],[1039,737]]}},
 'build':{'eye':[740,288],'eyes':[[712,270],[768,306]],'mouth':[748,340],'neck':[745,365],'hip':[795,615],'rs':[802,392],'re':[950,410],'rw':[1230,335],'ls':[642,385],'le':[500,494],'lw':[622,459],'gh':[830,566],'gk':[998,505],'ph':[784,647],'pk':[960,688],'tip':[1409,289],
  'regions':{3:[[780,365],[835,368],[968,389],[952,430],[784,422]],4:[[930,385],[970,431],[1218,350],[1280,365],[1355,352],[1480,275],[1230,309],[1120,342]],5:[[624,360],[666,381],[550,492],[504,513],[432,477],[528,408]],6:[[504,464],[574,479],[626,420],[665,444],[670,520],[728,524],[682,480],[670,560],[606,514],[552,540]],7:[[778,574],[807,551],[989,470],[1080,522],[1027,557],[821,643]],8:[[989,472],[1090,521],[1239,588],[1334,556],[1417,522],[1490,480],[1410,597],[1289,690],[1278,634],[1187,622],[1032,556]],9:[[775,615],[836,588],[1024,638],[975,704],[903,738],[841,715],[769,671]],10:[[902,685],[986,664],[977,737],[858,791],[853,840],[880,799],[897,895],[842,859],[837,1018],[800,943],[776,868],[790,779],[834,740]]}},
 'review':{'eye':[816,254],'eyes':[[789,232],[843,269]],'mouth':[807,300],'neck':[805,319],'hip':[785,584],'rs':[862,365],'re':[994,501],'rw':[1160,598],'ls':[748,355],'le':[687,471],'lw':[710,348],'gh':[817,584],'gk':[846,681],'ph':[742,585],'pk':[594,621],'tip':[719,328],
  'regions':{3:[[833,333],[876,358],[1002,467],[1037,505],[983,528],[931,457],[851,400]],4:[[973,478],[1025,490],[1033,555],[1162,590],[1280,680],[1221,702],[1163,627],[1197,720],[1166,667],[1094,609],[977,565]],5:[[735,329],[777,358],[734,435],[704,482],[664,495],[634,440],[684,391]],6:[[666,447],[707,469],[735,360],[770,344],[761,322],[724,310],[676,341],[673,392]],7:[[780,548],[836,550],[906,657],[858,711],[795,695],[771,631]],8:[[810,660],[884,673],[804,766],[712,838],[674,911],[669,857],[623,849],[611,806],[733,728]],9:[[715,549],[781,578],[706,644],[602,648],[548,601],[550,557],[655,572]],10:[[549,586],[610,615],[650,716],[615,779],[654,840],[628,833],[613,984],[546,896],[502,817],[565,782],[585,718]]}},
}
# Torso/head, right/left upper+lower arms, green/pink thigh+shin, root x/y.
# Anticipation -> gesture -> authored hold -> recovery -> neutral reading hold.
KEYS={
 'plan':[[0,0,0,0,0,0,0,0,0,0,0,0,0],[240,-2,4,3,-4,-3,3,3,-4,-2,3,-3,2],[560,5,-8,-13,-10,-6,8,-15,19,-8,13,6,-3],[820,6,-7,-15,-12,-7,9,-18,22,-9,14,8,-4],[1220,6,-7,-15,-12,-7,9,-18,22,-9,14,8,-4],[1500,-3,5,6,9,4,-6,9,-12,6,-8,-3,2],[1880,0,0,0,0,0,0,0,0,0,0,0,0],[3200,0,0,0,0,0,0,0,0,0,0,0,0]],
 'build':[[0,0,0,0,0,0,0,0,0,0,0,0,0],[220,-2,3,3,3,-3,4,4,-4,-4,3,-3,2],[540,3,-5,-5,-8,5,-6,-10,14,8,-12,7,-2],[760,4,-6,-7,-9,5,-7,-13,16,10,-14,9,-3],[1280,4,-6,-7,-9,5,-7,-13,16,10,-14,9,-3],[1570,-2,4,3,5,-3,4,5,-7,-4,7,-3,1],[1960,0,0,0,0,0,0,0,0,0,0,0,0],[3200,0,0,0,0,0,0,0,0,0,0,0,0]],
 'review':[[0,0,0,0,0,0,0,0,0,0,0,0,0],[300,1,-3,2,3,-2,2,3,-4,-3,4,-2,1],[620,-3,6,-4,-5,3,-3,-6,8,5,-7,-4,-2],[900,-3,6,-4,-5,3,-3,-7,9,6,-8,-4,-2],[1420,-3,6,-4,-5,3,-3,-7,9,6,-8,-4,-2],[1700,2,-4,2,3,-2,2,3,-4,-3,4,2,1],[2160,0,0,0,0,0,0,0,0,0,0,0,0],[3200,0,0,0,0,0,0,0,0,0,0,0,0]],
}
def make(name,data):
 src=Image.open(SOURCE/f'{name}.png').convert('RGBA');alpha=src.getchannel('A').point(lambda a:0 if a<8 else 255 if a>=249 else a);src.putalpha(alpha)
 # Each anatomical envelope is measured on its own master. Uncovered source
 # pixels attach to the nearest envelope, rather than silently remaining torso.
 heads={
  'plan':[[140,0],[600,0],[850,90],[1010,90],[1000,180],[1180,155],[1080,260],[1050,360],[920,400],[820,370],[735,365],[650,385],[625,470],[560,490],[500,595],[400,575],[280,710],[140,705],[220,470],[120,310],[130,160]],
  'build':[[90,70],[420,0],[700,0],[940,70],[1020,0],[1000,185],[1170,110],[1060,225],[1000,330],[905,390],[820,380],[740,384],[655,408],[595,500],[535,665],[413,616],[330,756],[198,673],[263,521],[160,600],[187,488],[98,466],[192,393],[90,385],[159,315],[82,270],[180,263],[82,190]],
  'review':[[350,80],[685,0],[965,0],[1090,80],[1180,70],[1110,170],[1280,170],[1160,250],[1240,320],[1100,360],[1200,440],[1030,400],[1120,570],[1000,510],[927,425],[900,355],[840,337],[780,340],[737,371],[701,440],[600,500],[570,400],[459,429],[490,300],[365,290],[460,227],[400,161]]}
 torsos={
  'plan':[[633,351],[812,351],[868,472],[863,559],[830,651],[744,672],[678,560],[625,467]],
  'build':[[632,351],[812,352],[866,463],[867,569],[818,666],[738,678],[669,561],[614,466]],
  'review':[[727,319],[867,337],[911,466],[856,604],[774,660],[696,618],[702,482]]}
 regions={1:heads[name],2:torsos[name],**data['regions']}
 if name=='plan':
  regions[4]=[[916,450],[1130,352],[1340,330],[1370,460],[1190,475],[960,530]]
  regions[8]=[[1020,467],[1105,480],[1260,650],[1375,450],[1390,740],[1355,890],[1230,775],[1195,690],[1110,580]]
  regions[10]=[[970,620],[1060,615],[1155,760],[1260,875],[1290,1030],[1160,1005],[1080,918],[1030,770]]
 elif name=='build':
  regions[4]=[[916,376],[1190,300],[1495,252],[1495,394],[1190,455],[941,448]]
  regions[8]=[[985,467],[1100,480],[1250,584],[1495,470],[1495,670],[1340,766],[1240,650],[1160,628],[1030,563]]
  regions[10]=[[889,664],[1005,657],[1010,760],[890,822],[904,944],[843,1040],[752,968],[755,817],[810,743]]
 else:
  regions[4]=[[972,471],[1040,479],[1060,553],[1240,578],[1325,748],[1200,735],[1130,665],[979,571]]
  regions[8]=[[810,650],[902,668],[834,773],[746,870],[737,977],[648,948],[597,853],[633,788],[733,716]]
  regions[10]=[[536,580],[620,607],[663,721],[636,789],[697,862],[686,1016],[537,1016],[446,936],[502,803],[555,747]]
 labels=Image.new('L',src.size,0);draw=ImageDraw.Draw(labels)
 for tag,polygon in regions.items():draw.polygon([tuple(point) for point in polygon],fill=tag)
 array=np.asarray(labels).copy();visible=np.asarray(alpha)>0;yy,xx=np.where((array==0)&visible)
 best=np.full(xx.shape,np.inf);chosen=np.zeros(xx.shape,dtype=np.uint8)
 for tag,polygon in regions.items():
  distance=np.full(xx.shape,np.inf)
  for a,b in zip(polygon,polygon[1:]+polygon[:1]):
   dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
   u=np.clip(((xx-a[0])*dx+(yy-a[1])*dy)/den,0,1) if den else 0
   distance=np.minimum(distance,(xx-a[0]-u*dx)**2+(yy-a[1]-u*dy)**2)
  closer=distance<best;chosen[closer]=tag;best[closer]=distance[closer]
 array[yy,xx]=chosen;labels=Image.fromarray(array)
 data['regions']=regions
 labels.save(OUT/f'{name}-labels.png');parts=[]
 for tag in range(1,11):
  mask=labels.point(lambda v:255 if v==tag else 0).filter(ImageFilter.MaxFilter(17));part=src.copy();part.putalpha(ImageChops.multiply(alpha,mask))
  box=part.getbbox();assert box,(name,tag);part=part.crop(box);dest=OUT/f'{name}-part-{tag}.png';part.save(dest,optimize=True)
  parts.append({'tag':tag,'origin':list(box[:2]),'size':list(part.size),'src':'../actor/'+dest.name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
 data['joint_colors']={}
 for key in ['neck','rs','re','ls','le','gh','gk','ph','pk']:
  x,y=data[key];color=None
  for radius in range(13):
   for dx,dy in [(0,0),(radius,0),(-radius,0),(0,radius),(0,-radius)]:
    pixel=src.getpixel((max(0,min(src.width-1,x+dx)),max(0,min(src.height-1,y+dy))))
    if pixel[3]>220:color='#'+''.join(f'{v:02x}' for v in pixel[:3]);break
   if color:break
  data['joint_colors'][key]=color or '#100a19'
 normalized=OUT/f'{name}-rgba.png';src.save(normalized,optimize=True);alpha.save(OUT/f'{name}-alpha.png')
 return {**{k:v for k,v in data.items() if k!='regions'},'keys':KEYS[name],'duration_ms':3200,'parts':parts,'source_sha256':hashlib.sha256((SOURCE/f'{name}.png').read_bytes()).hexdigest(),'rgba_sha256':hashlib.sha256(normalized.read_bytes()).hexdigest(),'eye_span':math.dist(*data['eyes'])}
def main():
 OUT.mkdir(exist_ok=True);poses={name:make(name,data) for name,data in POSES.items()}
 record={'schema_version':1,'duration_ms':3200,'camera':[-160,-160,1856,1440],'poses':poses,'method':'Three distinct supplied full-body masters; pose-specific label masks, 8-pixel original-pixel overlaps and nearest-envelope completion of unassigned visible source pixels, rigid bone rotations, independent head/torso/arms/legs and pose-specific blinks. No new generation or mesh warp.','alpha':'Below 8 removed as faint source fringe; >=249 normalized opaque. Black anatomy retained. Full RGBA and separate alpha masters remain.','source_fidelity':'Fan-art reconstruction compared with supplied source20/source19 frames; not exact extracted anime acting or official anatomy.'}
 (OUT/'RIG.json').write_text(json.dumps(record,indent=2)+'\n');(OUT/'MASKS.json').write_text(json.dumps(POSES,indent=2)+'\n');print('Three pose-specific rigs;',sum(len(v['parts']) for v in poses.values()),'lossless layers',flush=True)
if __name__=='__main__':main()
