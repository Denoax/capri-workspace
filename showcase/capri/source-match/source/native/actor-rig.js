function createCapriActor(data,redraw){
 const parts=new Map();
 data.parts.forEach(function(p){const im=new Image();im.onload=redraw;im.src=p.src;parts.set(p.tag,{meta:p,image:im});});
 const hip=[803,600],neck=[737,357],rs=[817,408],re=[943,481],ls=[652,380],le=[575,470],gh=[836,554],gk=[1050,493],ph=[806,621],pk=[1006,637];
 function angle(a){return [Math.cos(a*Math.PI/180),Math.sin(a*Math.PI/180)];}
 function point(p,m){return [m[0]*p[0]-m[1]*p[1]+m[2],m[1]*p[0]+m[0]*p[1]+m[3]];}
 function around(origin,target,degrees){const r=angle(degrees);return [r[0],r[1],target[0]-r[0]*origin[0]+r[1]*origin[1],target[1]-r[1]*origin[0]-r[0]*origin[1]];}
 function pose(t){
  const keys=data.keys;t=Math.floor((t%data.duration_ms)*data.fps/1000)*1000/data.fps;
  let i=0;while(i<keys.length-2&&t>keys[i+1][0])i++;
  let u=Math.max(0,Math.min(1,(t-keys[i][0])/(keys[i+1][0]-keys[i][0])));u=u*u*(3-2*u);
  const v=keys[i].map(function(a,j){return a*(1-u)+keys[i+1][j]*u;});
  const body=v[1],head=v[2],root=[hip[0]+v[11],hip[1]+v[12]],torso=around(hip,root,body);
  function upper(origin,a){return around(origin,point(origin,torso),body+a);}
  function lower(origin,joint,a,b){return around(joint,point(joint,upper(origin,a)),body+a+b);}
  return {1:around(neck,point(neck,torso),body+head),2:torso,3:upper(rs,v[3]),4:lower(rs,re,v[3],v[4]),5:upper(ls,v[5]),6:lower(ls,le,v[5],v[6]),7:upper(gh,v[7]),8:lower(gh,gk,v[7],v[8]),9:upper(ph,v[9]),10:lower(ph,pk,v[9],v[10])};
 }
 return {draw:function(ctx,t,x,y,width,rotation){
  const tr=pose(t),camera=data.camera,h=width*camera[3]/camera[2],s=width/camera[2];
  ctx.save();ctx.translate(x,y);ctx.rotate(rotation||0);ctx.translate(-width/2,-h/2);ctx.scale(s,s);ctx.translate(-camera[0],-camera[1]);
  const phase=t%data.duration_ms,blink=(phase>=1000&&phase<1134)||(phase>=1900&&phase<2000);
  [1,9,10,7,8,2,5,6,3,4].forEach(function(tag){const p=parts.get(tag);if(!p.image.complete||!p.image.naturalWidth)return;const m=tr[tag];ctx.save();ctx.transform(m[0],m[1],-m[1],m[0],m[2],m[3]);ctx.drawImage(p.image,p.meta.origin[0],p.meta.origin[1],p.meta.size[0],p.meta.size[1]);
   if(tag===1&&blink){ctx.fillStyle='#00ed80';ctx.beginPath();ctx.ellipse(724,262,18,21,-.25,0,Math.PI*2);ctx.ellipse(784,298,12,16,.30,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#0c0715';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(709,255);ctx.lineTo(726,272);ctx.lineTo(741,258);ctx.moveTo(776,295);ctx.lineTo(786,306);ctx.lineTo(796,293);ctx.stroke();}
   ctx.restore();});ctx.restore();
 },pose:pose};
}
