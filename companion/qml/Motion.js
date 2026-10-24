.pragma library
// Adapted from the supplied legacy rig's original matrix/pivot model.
// Data are numbers only. Provider output never supplies transforms or QML.
function point(p,m) { return [m[0]*p[0]-m[1]*p[1]+m[2],m[1]*p[0]+m[0]*p[1]+m[3]]; }
function around(p,q,degrees) {
    const a=degrees*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
    return [c,s,q[0]-c*p[0]+s*p[1],q[1]-s*p[0]-c*p[1]];
}
function matrices(p,t,state,reduced) {
    const phase=(t%p.duration_ms),keys=p.keys;
    let i=0;
    while(i<keys.length-2 && phase>keys[i+1][0])i++;
    let u=Math.max(0,Math.min(1,(phase-keys[i][0])/(keys[i+1][0]-keys[i][0])));
    u=u*u*(3-2*u);
    let v=keys[i].map((x,j)=>x*(1-u)+keys[i+1][j]*u);
    // Each state has a short entry, readable held attitude, and local settling.
    const strength=reduced?0:({idle:0.12,curious:0.28,listening:0.16,thinking:0.2,working:0.14,success:0.45,blocked:0.2,dragged:0.12}[state]||0.15);
    v=v.map((x,j)=>j===0?x:x*strength);
    const entry=Math.min(1,t/280),ease=entry*entry*(3-2*entry);
    const gestures={curious:[-2,6,-2,9],listening:[3,-8,-4,5],thinking:[-3,7,3,-5],working:[2,-4,0,3],success:[-4,9,-3,-6],blocked:[4,-5,2,7]};
    if(!reduced && gestures[state]) {
        const g=gestures[state];v[3]+=g[0]*ease;v[4]+=g[1]*ease;v[5]+=g[2]*ease;v[6]+=g[3]*ease;
    }
    const head=reduced?0:ease*({curious:6,listening:-4,thinking:4,working:1,success:-2,blocked:5,dragged:2}[state]||0);
    const body=v[1],root=[p.hip[0]+v[11],p.hip[1]+v[12]],torso=around(p.hip,root,body);
    function upper(o,a){return around(o,point(o,torso),body+a);}
    function lower(o,j,a,b){return around(j,point(j,upper(o,a)),body+a+b);}
    return {1:around(p.neck,point(p.neck,torso),body+v[2]+head),2:torso,
        3:upper(p.rs,v[3]),4:lower(p.rs,p.re,v[3],v[4]),5:upper(p.ls,v[5]),6:lower(p.ls,p.le,v[5],v[6]),
        7:upper(p.gh,v[7]),8:lower(p.gh,p.gk,v[7],v[8]),9:upper(p.ph,v[9]),10:lower(p.ph,p.pk,v[9],v[10])};
}
