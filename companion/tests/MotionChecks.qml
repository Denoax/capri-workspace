import QtQml
import "../qml/Motion.js" as Motion
import "../qml/Pointer.js" as Pointer
QtObject {
    Component.onCompleted: {
        var assertions=0;
        function check(value,label){assertions++;if(!value)throw Error(label);}
        function distance(a,b){return Math.hypot(a[0]-b[0],a[1]-b[1]);}
        try {
            var request=new XMLHttpRequest();request.open("GET",Qt.resolvedUrl("../qml/motion-clips.json"),false);request.send();
            var all=Motion.compileCatalog(JSON.parse(request.responseText)),clips=all.filter(c=>c.asset_status==="AVAILABLE");
            check(all.length===48&&clips.length===41,"all briefs classified without view substitution");
            var p={hip:[80,70],neck:[80,20],rs:[95,30],re:[120,50],rw:[150,20],ls:[65,30],le:[40,50],lw:[30,15],gh:[90,65],gk:[110,100],ph:[70,65],pk:[40,95],parts:[]};
            for(var tag=1;tag<=10;tag++)p.parts.push({tag:tag,origin:[tag*8,tag*4],size:[30,40]});
            for(var c of clips) {
                var previous=-Infinity;
                for(var t=0;t<=c.duration_ms;t+=23) {
                    var v=Motion.sample(c,t),m=Motion.poseMatrices(p,v);
                    for(var k of Object.keys(Motion.defaults))check(Number.isFinite(v[k])&&v[k]>=Motion.limits[k][0]-.0001&&v[k]<=Motion.limits[k][1]+.0001,"bounded channel "+c.id+"/"+k);
                    for(var join of [[p.neck,1,2],[p.re,3,4],[p.le,5,6],[p.gk,7,8],[p.pk,9,10],[p.rw,4,12],[p.lw,6,13],[[p.hip[0],p.hip[1]-56],2,11]])check(distance(Motion.point(join[0],m[join[1]]),Motion.point(join[0],m[join[2]]))<1e-7,"stable joint "+c.id);
                    check(Math.abs(distance(Motion.point(p.rs,m[3]),Motion.point(p.re,m[3]))-distance(p.rs,p.re)*v.rootScale)<1e-7,"rigid upper bone "+c.id);
                    if(c.id==="tucked_roll"||c.id==="upside_down_hang"){check(v.rootRoll>=previous-.0001,"unwrapped forward roll "+c.id);previous=v.rootRoll;}
                }
                var mid=Motion.sample(c,c.duration_ms*.44),later=Motion.sample(c,c.duration_ms*.44+.01),speed={};
                for(var k of Object.keys(Motion.defaults))speed[k]=(later[k]-mid[k])/.01;
                var zero=Motion.transition(mid,speed,Motion.neutral(),0,340),epsilon=Motion.transition(mid,speed,Motion.neutral(),.00001,340);
                for(var k of Object.keys(Motion.defaults)) {
                    check(Math.abs(zero[k]-mid[k])<1e-7,"interruption position "+c.id);
                    check(Math.abs((epsilon[k]-zero[k])/.0034-speed[k])<.004,"interruption velocity "+c.id+"/"+k);
                }
            }
            for(var angle=-540;angle<=540;angle+=3) {
                var matrix=Motion.around([13,-19],[-57,91],angle,1.23),rect=[-31,12,245,137];
                var points=[[rect[0],rect[1]],[rect[0]+rect[2],rect[1]],[rect[0],rect[1]+rect[3]],[rect[0]+rect[2],rect[1]+rect[3]]].map(v=>Motion.point(v,matrix));
                var actual=Motion.rectangle(rect,matrix),xs=points.map(v=>v[0]),ys=points.map(v=>v[1]);
                var expected=[Math.min.apply(null,xs),Math.min.apply(null,ys),Math.max.apply(null,xs)-Math.min.apply(null,xs),Math.max.apply(null,ys)-Math.min.apply(null,ys)];
                check(actual.every((v,i)=>Math.abs(v-expected[i])<1e-9),"exact transformed AABB "+angle);
            }
            var monitor={name:"LEFT",x:-1536,y:-400,width:1536,height:864};
            var local=Pointer.localPoint({x:-768,y:32,outputs:[monitor]},"LEFT",1280,720);
            check(local[0]===640&&local[1]===360,"negative origin and per-app fractional scale");
            check(Pointer.localPoint({x:0,y:32,outputs:[monitor]},"LEFT",1280,720)===null,"cross-output boundary relinquishes interest");
            check(Pointer.localPoint({x:-768,y:32,outputs:[]},"LEFT",1280,720)===null,"unavailable output relinquishes interest");
            check(Pointer.safeDistance({width:600,height:600})>500,"large rotated actor keeps pointer clearance");
            var d=Motion.makeDirector(clips,123),first=d.choose(0,false);check(first!==null,"initial novelty choice");
            var recent=[first.id],now=1;
            for(var i=0;i<50;i++){var next=d.choose(now,false);if(next){check(!recent.slice(-6).includes(next.id),"no recent replay");check(next.family!==first.family,"no adjacent family replay");first=next;recent.push(next.id);}now+=100;}
            check(d.choose(now,false)===null,"exhaustion rests rather than bypassing cooldown");
            console.warn("MOTION_PASS "+JSON.stringify({clips:clips.length,blocked:all.length-clips.length,assertions:assertions}));Qt.exit(0);
        } catch(error){console.error("MOTION_FAIL "+error);Qt.exit(1);}
    }
}
