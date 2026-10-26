import QtQml
import "../qml/Position.js" as Position
import "../qml"
QtObject {
    property PositionController control: PositionController {}
    Component.onCompleted: {
        var count=0;
        function check(v, label) { count++; if (!v) throw Error(label); }
        function near(a,b) { return Math.abs(a-b)<.00001; }
        function begin() { return Position.begin(Position.create(400,300),"LEFT",1280,720,[20,10,200,240],[100,80],280,[30,20,170,210]); }
        function packet(s,x,y) { return {epoch:s.capture.epoch,valid:true,x:x,y:y,outputs:[{name:"LEFT",x:-1536,y:-400,width:1536,height:864}]}; }
        function point(s,x,y) { return Position.sample(s,packet(s,-1536+x*1.2,-400+y*1.2)); }
        try {
            var s=begin(), footprint=s.capture.footprint.slice();
            s=point(s,500,380);
            check(s.x===400 && s.y===300 && !s.moved,"stationary native point keeps logical anchor");
            for(var i=0;i<200;i++) s=point(s,600,430);
            check(near(s.x,500)&&near(s.y,350),"repeated absolute samples cannot accumulate movement");
            s=point(s,450,330);
            check(near(s.x,350)&&near(s.y,250),"reversal, negative origin and fractional scale apply exactly once");
            check(s.capture.footprint.every((v,j)=>v===footprint[j]),"immutable captured footprint");
            check(Position.place(s,900,500,"ipc")===s,"external placement rejected during capture");
            check(Position.travel(s,s.epoch,900,500)===s,"travel rejected during capture");
            check(Position.sample(s,{epoch:s.epoch-1,valid:false})===s,"stale sample cannot terminate capture");
            var changed=packet(s,-900,-20); changed.outputs[0].width=1600;
            var lost=Position.sample(s,changed);
            check(!lost.capture&&lost.ended.reason==="output-changed"&&!lost.ended.persist&&lost.x===s.x,"geometry change cancels without wrong-output save");
            lost=Position.sample(s,{epoch:s.epoch,valid:false});
            check(!lost.capture&&lost.ended.persist&&lost.x===s.x,"pointer loss retains last valid anchor");
            var edge=point(s,1279,719);
            check(near(edge.x,1052)&&near(edge.y,462),"fixed footprint right/bottom clamp");
            var crossed=point(s,1300,730);
            check(!crossed.capture&&crossed.ended.reason==="output-boundary"&&near(crossed.x,1052),"output crossing releases at safe boundary");
            check(Position.axis(100,40,-20)===10,"oversized footprint centers");
            check(Position.begin(s,"LEFT",1280,720,[0,0,100,100],[1,1],280,[0,0,100,100])===s,"duplicate capture rejected");
            check(!Position.sample(s,{epoch:s.epoch,valid:true,x:NaN,y:20}).capture,"invalid coordinate rejected");
            check(Position.place(Position.create(1,2),Infinity,9,"ipc").x===1,"nonfinite placement rejected");
            var ended=Position.end(s,"cancel",true);
            check(Position.end(ended,"release",true)===ended,"end is idempotent");
            check(Position.travel(ended,s.epoch,3,4)===ended,"stale travel lease rejected");
            var commits=0;control.commitRequested.connect(()=>commits++);
            control.place(400,300,"test");
            check(control.begin("LEFT",1280,720,[20,10,200,240],[100,80],280,[30,20,170,210]),"controller begins capture");
            control.sample({epoch:control.epoch,valid:true,x:-816,y:116,outputs:[{name:"LEFT",x:-1536,y:-400,width:1536,height:864}]});
            control.end("hidden",true);control.end("cancel",true);control.end("release",true);
            check(!control.captured&&!control.dragging&&commits===1&&control.gestureSaves===1,"hide/cancel/release clears drag and saves once");
            control.begin("LEFT",1280,720,[20,10,200,240],[100,80],280,[30,20,170,210]);control.end("release",true);
            check(commits===1,"stationary click does not save gesture");
            control.begin("LEFT",1280,720,[20,10,200,240],[100,80],280,[30,20,170,210]);
            var epoch=control.epoch;
            control.sample({epoch:epoch,valid:true,x:-780,y:116,outputs:[{name:"LEFT",x:-1536,y:-400,width:1536,height:864}]});
            control.release();
            check(control.captured&&control.releasePending,"moving release waits for final native point");
            control.sample({epoch:epoch,valid:true,final:false,x:-760,y:116,outputs:[{name:"LEFT",x:-1536,y:-400,width:1536,height:864}]});
            check(control.captured&&control.releasePending,"queued pre-release sample cannot complete release");
            control.sample({epoch:epoch,valid:true,final:true,x:-744,y:116,outputs:[{name:"LEFT",x:-1536,y:-400,width:1536,height:864}]});
            check(!control.captured&&!control.releasePending&&near(control.x,560)&&commits===2,"final sample ends epoch and persists final endpoint once");
            console.warn("POSITION_PASS "+count);Qt.exit(0);
        } catch(error) { console.error("POSITION_FAIL "+error);Qt.exit(1); }
    }
}
