.pragma library
// Authored numeric motion. No provider-supplied code or authority enters here.
var defaults = {rootX:0,rootY:0,rootRoll:0,rootScale:1,pelvisRoll:0,torsoRoll:0,headRoll:0,rUpper:0,rLower:0,lUpper:0,lLower:0,rThigh:0,rShin:0,lThigh:0,lShin:0,rHand:0,lHand:0,hairRoll:0,legDepth:0};
var limits = {rootX:[-140,140],rootY:[-160,160],rootRoll:[-1080,1080],rootScale:[0.72,1.25],pelvisRoll:[-55,55],torsoRoll:[-40,40],headRoll:[-28,28],rUpper:[-110,110],rLower:[-140,140],lUpper:[-110,110],lLower:[-140,140],rThigh:[-100,100],rShin:[-145,145],lThigh:[-100,100],lShin:[-145,145],rHand:[-30,30],lHand:[-30,30],hairRoll:[-6,6],legDepth:[0,1]};
function clamp(x,a,b) { return Math.max(a,Math.min(b,x)); }
function neutral() { return Object.assign({},defaults); }
function point(p,m) { return [m[0]*p[0]-m[1]*p[1]+m[2],m[1]*p[0]+m[0]*p[1]+m[3]]; }
function around(p,q,degrees,scale) {
    var a=degrees*Math.PI/180,c=Math.cos(a)*(scale===undefined?1:scale),s=Math.sin(a)*(scale===undefined?1:scale);
    return [c,s,q[0]-c*p[0]+s*p[1],q[1]-s*p[0]-c*p[1]];
}
function compose(a,b) { var q=point([b[2],b[3]],a);return [a[0]*b[0]-a[1]*b[1],a[1]*b[0]+a[0]*b[1],q[0],q[1]]; }
function slopes(xs,ys) {
    var n=xs.length,d=[],m=Array(n).fill(0);
    for(var i=0;i<n-1;i++) d.push((ys[i+1]-ys[i])/(xs[i+1]-xs[i]));
    for(var j=1;j<n-1;j++) if(d[j-1]*d[j]>0) {
        var h0=xs[j]-xs[j-1],h1=xs[j+1]-xs[j],w0=2*h1+h0,w1=h1+2*h0;
        m[j]=(w0+w1)/(w0/d[j-1]+w1/d[j]);
    }
    return m;
}
function compile(clip) {
    if(!clip.keys || clip.keys.length<4) throw Error("Clip has no authored phases: "+clip.id);
    var xs=clip.keys.map(k=>k.t),channels={};
    if(xs[0]!==0 || xs[xs.length-1]!==clip.duration_ms) throw Error("Invalid clip endpoints");
    for(var i=1;i<xs.length;i++) if(xs[i]<=xs[i-1]) throw Error("Unordered clip phases");
    for(var name of Object.keys(defaults)) {
        var ys=clip.keys.map(k=>k[name]===undefined?defaults[name]:k[name]);
        if(ys.some(x=>!Number.isFinite(x)||x<limits[name][0]||x>limits[name][1])) throw Error("Joint/channel bound: "+clip.id+"/"+name);
        channels[name]={ys:ys,m:slopes(xs,ys)};
    }
    return Object.assign({},clip,{xs:xs,channels:channels});
}
function compileCatalog(value) {
    if(value.schema_version!==1 || value.clips.length!==48) throw Error("Unexpected motion catalogue");
    var ids={};
    return value.clips.map(c=>{if(ids[c.id])throw Error("Duplicate clip");ids[c.id]=true;return c.asset_status==="AVAILABLE"?compile(c):c;});
}
function sample(clip,time) {
    var t=clamp(time,0,clip.duration_ms),xs=clip.xs,i=0,out={};
    while(i<xs.length-2 && t>xs[i+1]) i++;
    var h=xs[i+1]-xs[i],u=clamp((t-xs[i])/h,0,1),u2=u*u,u3=u2*u;
    for(var name of Object.keys(defaults)) {
        var c=clip.channels[name];
        out[name]=(2*u3-3*u2+1)*c.ys[i]+(u3-2*u2+u)*h*c.m[i]+(-2*u3+3*u2)*c.ys[i+1]+(u3-u2)*h*c.m[i+1];
    }
    return out;
}
function transition(a,velocity,b,u,duration) {
    var t=clamp(u,0,1),t2=t*t,t3=t2*t,out={};
    for(var k of Object.keys(defaults)) {
        var target=b[k];
        // Only the handover chooses an equivalent upright angle. Authored rolls
        // keep their unwrapped winding throughout sample(), including past180.
        if(k==="rootRoll") target+=Math.round((a[k]-target)/360)*360;
        var v=velocity[k]||0;
        out[k]=(2*t3-3*t2+1)*a[k]+(t3-2*t2+t)*duration*v+(-2*t3+3*t2)*target;
        if(k!=="rootRoll") out[k]=clamp(out[k],limits[k][0],limits[k][1]);
    }
    return out;
}
function poseMatrices(p,s) {
    var waist=[p.hip[0],p.hip[1]-56],pelvis=around(p.hip,p.hip,s.pelvisRoll),angle=s.pelvisRoll+s.torsoRoll;
    var chest=around(waist,point(waist,pelvis),angle),root=around(p.hip,[p.hip[0]+s.rootX,p.hip[1]+s.rootY],s.rootRoll,s.rootScale);
    function upper(o,a,base,roll) { return around(o,point(o,base),roll+a); }
    function lower(o,j,a,b,base,roll) { return around(j,point(j,upper(o,a,base,roll)),roll+a+b); }
    var m={1:around(p.neck,point(p.neck,chest),angle+s.headRoll),2:chest,11:pelvis,
      3:upper(p.rs,s.rUpper,chest,angle),4:lower(p.rs,p.re,s.rUpper,s.rLower,chest,angle),
      5:upper(p.ls,s.lUpper,chest,angle),6:lower(p.ls,p.le,s.lUpper,s.lLower,chest,angle),
      7:upper(p.gh,s.rThigh,pelvis,s.pelvisRoll),8:lower(p.gh,p.gk,s.rThigh,s.rShin,pelvis,s.pelvisRoll),
      9:upper(p.ph,s.lThigh,pelvis,s.pelvisRoll),10:lower(p.ph,p.pk,s.lThigh,s.lShin,pelvis,s.pelvisRoll)};
    m[12]=around(p.rw,point(p.rw,m[4]),angle+s.rUpper+s.rLower+s.rHand);
    m[13]=around(p.lw,point(p.lw,m[6]),angle+s.lUpper+s.lLower+s.lHand);
    m[14]=around([650,250],point([650,250],m[1]),angle+s.headRoll+s.hairRoll);
    for(var tag of Object.keys(m)) m[tag]=compose(root,m[tag]);
    return m;
}
function rectangle(rect,m) {
    // Exact AABB of a uniformly scaled rotation, without allocating four
    // corners and intermediate arrays for every input region on every frame.
    var x=rect[0]+rect[2]/2,y=rect[1]+rect[3]/2;
    var cx=m[0]*x-m[1]*y+m[2],cy=m[1]*x+m[0]*y+m[3];
    var hx=(Math.abs(m[0])*rect[2]+Math.abs(m[1])*rect[3])/2;
    var hy=(Math.abs(m[1])*rect[2]+Math.abs(m[0])*rect[3])/2;
    return [cx-hx,cy-hy,hx*2,hy*2];
}

var drawOrder=[9,10,7,8,11,2,5,6,13,3,4,12,14,1];
function sourceTag(tag) { return ({11:2,12:4,13:6,14:1})[tag]||tag; }
function partRect(p,tag) {
    var q=p.parts.find(v=>v.tag===sourceTag(tag)),r=[q.origin[0],q.origin[1],q.size[0],q.size[1]];
    function left(x){var right=r[0]+r[2];r[0]=Math.max(r[0],x);r[2]=Math.max(0,right-r[0]);}
    function right(x){r[2]=Math.max(0,Math.min(r[0]+r[2],x)-r[0]);}
    function top(y){var bottom=r[1]+r[3];r[1]=Math.max(r[1],y);r[3]=Math.max(0,bottom-r[1]);}
    function bottom(y){r[3]=Math.max(0,Math.min(r[1]+r[3],y)-r[1]);}
    if(tag===1)left(642);if(tag===14)right(658);
    if(tag===2)bottom(p.hip[1]-48);if(tag===11)top(p.hip[1]-64);
    if(tag===4)right(p.rw[0]+8);if(tag===12)left(p.rw[0]-8);
    if(tag===6)top(p.lw[1]-8);if(tag===13)bottom(p.lw[1]+8);
    return r;
}
function bounds(p,s,knownMatrices) {
    var m=knownMatrices&&knownMatrices[1]?knownMatrices:poseMatrices(p,s),rs=drawOrder.map(tag=>rectangle(partRect(p,tag),m[tag]));
    var x=Math.min.apply(null,rs.map(r=>r[0])),y=Math.min.apply(null,rs.map(r=>r[1]));
    return [x,y,Math.max.apply(null,rs.map(r=>r[0]+r[2]))-x,Math.max.apply(null,rs.map(r=>r[1]+r[3]))-y];
}
function makeDirector(clips,seed) {
    var rng=(seed||71)>>>0,history=[],last={},families={},lastFamily="";
    function random() { rng^=rng<<13;rng^=rng>>>17;rng^=rng<<5;return (rng>>>0)/4294967296; }
    return {random:random,history:function(){return history.slice();},choose:function(now,pinned) {
        var allowed=clips.filter(c=>c.asset_status==="AVAILABLE" && c.family!==lastFamily && c.autonomous!==false && (!pinned || c.pinned_safe) && !history.slice(-6).includes(c.id) && now-(last[c.id]===undefined?-Infinity:last[c.id])>=c.cooldown_ms && now-(families[c.family]===undefined?-Infinity:families[c.family])>=14000);
        if(!allowed.length) return null;
        var total=allowed.reduce((s,c)=>s+c.weight,0),v=random()*total,selected=allowed[allowed.length-1];
        for(var c of allowed) {v-=c.weight;if(v<=0){selected=c;break;}}
        history.push(selected.id);history=history.slice(-12);last[selected.id]=now;families[selected.family]=now;lastFamily=selected.family;
        return selected;
    }};
}
