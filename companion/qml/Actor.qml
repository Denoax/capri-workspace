import QtQuick
import Quickshell.Io
import "Motion.js" as Motion

Item {
    id: actor
    required property string assets
    property string state: "idle"
    property bool reduced: false
    property bool paused: false
    property bool reading: false
    property bool pinned: false
    property bool ownerInteracting: false
    property bool pointerValid: false
    property point pointerTarget: Qt.point(0, 0)
    property var rig: null
    property var catalog: []
    property string libraryRevision: ""
    property var director: null
    property string poseName: "plan"
    readonly property var pose: rig ? rig.poses[poseName] : null
    property var currentClip: null
    property string clipId: currentClip ? currentClip.id : "rest"
    property string reviewEmotion: ""
    property real reviewAngle: 0
    property string emotion: reviewing && reviewEmotion ? reviewEmotion : currentClip ? currentClip.emotion : "neutral"
    property real clock: 0
    property real elapsed: 0
    property real winding: 0
    property bool moving: false
    property bool handover: false
    property var fromPose: Motion.neutral()
    property var fromVelocity: Motion.neutral()
    property var poseValue: Motion.neutral()
    property var velocity: ({})
    property rect envelope: Qt.rect(0, 0, width, height)
    // Include the live transformed silhouette during interruption as well as the
    // precomputed clip envelope. A roll-to-upright handover can sweep outside
    // both endpoint boxes; the native surface must never crop that sweep.
    readonly property rect paintBounds: {
        if (!moving)
            return bounds;
        var x = Math.min(bounds.x - 8, envelope.x), y = Math.min(bounds.y - 8, envelope.y);
        return Qt.rect(x, y, Math.max(bounds.x + bounds.width + 8, envelope.x + envelope.width) - x, Math.max(bounds.y + bounds.height + 8, envelope.y + envelope.height) - y);
    }
    property bool reviewing: false
    property bool reviewPaused: false
    property bool blink: false
    property real factor: width / 1856
    property real gazeRoll: pointerValid && !reading && !ownerInteracting ? Motion.clamp((pointerTarget.x - width / 2) / 30, -10, 10) : 0
    Behavior on gazeRoll {
        NumberAnimation {
            duration: 180
            easing.type: Easing.OutCubic
        }
    }
    readonly property var value: {
        var v = Object.assign({}, poseValue);
        if (reviewing)
            v.rootRoll += reviewAngle;
        v.headRoll = Motion.clamp(v.headRoll + gazeRoll, -28, 28);
        return v;
    }
    readonly property var matrices: pose ? Motion.poseMatrices(pose, value) : ({})
    readonly property rect bounds: {
        if (!pose)
            return Qt.rect(0, 0, width, height);
        var r = Motion.bounds(pose, value, matrices);
        return Qt.rect((160 + r[0]) * factor, (160 + r[1]) * factor, r[2] * factor, r[3] * factor);
    }
    readonly property point neutralMouth: pose ? Qt.point((160 + pose.mouth[0]) * factor, (160 + pose.mouth[1]) * factor) : Qt.point(width / 2, height / 3)
    readonly property point mouth: {
        if (!pose || !matrices[1])
            return Qt.point(width / 2, height / 3);
        var p = Motion.point(pose.mouth, matrices[1]);
        return Qt.point((160 + p[0]) * factor, (160 + p[1]) * factor);
    }
    property var regionData: []
    function mapRegion(region) {
        if (!pose || !matrices[region.tag])
            return [0, 0, 0, 0];
        var q = Motion.rectangle(region.rect, matrices[region.tag]);
        return [(160 + q[0]) * factor, (160 + q[1]) * factor, q[2] * factor, q[3] * factor];
    }
    readonly property bool ready: {
        if (!pose || !catalog.length || !regionData.length || pieces.count !== 14)
            return false;
        for (var i = 0; i < pieces.count; i++)
            if (!pieces.itemAt(i)?.ready)
                return false;
        return true;
    }
    implicitWidth: 370
    implicitHeight: 288
    signal clipStarted(string name)
    signal clipFinished(string name)
    function installValue(next, dt) {
        var speed = {};
        for (var k of Object.keys(Motion.defaults))
            speed[k] = dt > 0 ? (next[k] - poseValue[k]) / dt : 0;
        velocity = speed;
        poseValue = next;
    }
    function play(name) {
        var c = catalog.find(v => v.id === name && v.asset_status === "AVAILABLE");
        if (!c)
            return false;
        rest.stop();
        var r = [bounds.x, bounds.y, bounds.width, bounds.height];
        for (var n = 0; n <= 48; n++) {
            var b = Motion.bounds(pose, Motion.sample(c, c.duration_ms * n / 48));
            var q = [(160 + b[0]) * factor, (160 + b[1]) * factor, b[2] * factor, b[3] * factor];
            var right = Math.max(r[0] + r[2], q[0] + q[2]), bottom = Math.max(r[1] + r[3], q[1] + q[3]);
            r[0] = Math.min(r[0], q[0]);
            r[1] = Math.min(r[1], q[1]);
            r[2] = right - r[0];
            r[3] = bottom - r[1];
        }
        envelope = Qt.rect(r[0] - 8, r[1] - 8, r[2] + 16, r[3] + 16);
        currentClip = c;
        clock = 0;
        elapsed = 0;
        fromPose = Object.assign({}, poseValue);
        fromVelocity = Object.assign({}, velocity);
        winding = Math.round(fromPose.rootRoll / 360) * 360;
        handover = true;
        moving = true;
        clipStarted(name);
        return true;
    }
    function freeze() {
        rest.stop();
        moving = false;
        handover = false;
        velocity = {};
    }
    function scheduleRest() {
        if (paused || reduced || reading || ownerInteracting || reviewing)
            return;
        rest.interval = 7000 + Math.round(director ? director.random() * 11000 : 2000);
        rest.restart();
    }
    function settle() {
        rest.stop();
        moving = false;
        handover = false;
        currentClip = null;
        velocity = {};
        poseValue = Motion.neutral();
        blink = false;
    }
    function chooseNext() {
        if (!director || paused || reduced || reading || ownerInteracting || reviewing)
            return;
        var c = director.choose(Date.now(), pinned);
        if (c)
            play(c.id);
        else
            actor.scheduleRest();
    }
    function cue() {
        if (!ready || reviewing)
            return;
        if (paused || reduced) {
            settle();
            return;
        }
        if (ownerInteracting) {
            if (state === "dragged")
                play("pickup_dangle");
            else
                freeze();
            return;
        }
        if (reading) {
            play("reply_settle");
            return;
        }
        var names = {
            listening: "listen_wait",
            thinking: "focused_hold",
            working: "focused_hold",
            success: "happy_bounce",
            blocked: "mock_annoyed",
            dragged: "pickup_dangle"
        };
        if (names[state])
            play(names[state]);
        else
            chooseNext();
    }
    function review(name, time, pause) {
        if (!catalog.some(c => c.id === name && c.asset_status === "AVAILABLE"))
            return false;
        reviewing = true;
        play(name);
        handover = false;
        clock = Motion.clamp(time, 0, currentClip.duration_ms);
        reviewPaused = pause;
        winding = 0;
        poseValue = Motion.sample(currentClip, clock);
        velocity = {};
        return true;
    }
    function endReview() {
        reviewing = false;
        reviewEmotion = "";
        reviewAngle = 0;
        reviewPaused = false;
        settle();
        actor.scheduleRest();
    }
    onStateChanged: cue()
    onPinnedChanged: {
        if (pinned) {
            settle();
            actor.scheduleRest();
        } else
            cue();
    }
    onReadingChanged: cue()
    onOwnerInteractingChanged: cue()
    onPausedChanged: {
        if (paused)
            settle();
        else
            cue();
    }
    onReducedChanged: {
        if (reduced)
            settle();
        else
            cue();
    }
    onReadyChanged: if (ready)
        cue()
    FileView {
        path: actor.assets + "/actor/RIG.json"
        onLoaded: actor.rig = JSON.parse(text())
    }
    FileView {
        path: Qt.resolvedUrl("motion-clips.json").toString().replace(/^file:\/\//, "")
        onLoaded: {
            var data = JSON.parse(text());
            actor.libraryRevision = data.revision || "unversioned";
            actor.catalog = Motion.compileCatalog(data);
            actor.director = Motion.makeDirector(actor.catalog, 71);
        }
    }
    FileView {
        path: Qt.resolvedUrl("motion-regions.json").toString().replace(/^file:\/\//, "")
        onLoaded: actor.regionData = JSON.parse(text()).plan
    }
    FrameAnimation {
        running: actor.moving && !actor.paused && !actor.reduced && actor.visible && !(actor.reviewing && actor.reviewPaused)
        onTriggered: {
            var dt = Math.min(100, frameTime * 1000);
            actor.elapsed += dt;
            if (actor.handover) {
                var target = Motion.neutral();
                target.rootRoll = actor.winding;
                actor.installValue(Motion.transition(actor.fromPose, actor.fromVelocity, target, actor.elapsed / 340, 340), dt);
                if (actor.elapsed >= 340) {
                    actor.handover = false;
                    actor.clock = 0;
                    if (actor.reading && !actor.reviewing) {
                        actor.poseValue = Motion.neutral();
                        actor.velocity = {};
                        actor.moving = false;
                    }
                }
            } else {
                actor.clock = Math.min(actor.currentClip.duration_ms, actor.clock + dt);
                var next = Motion.sample(actor.currentClip, actor.clock);
                next.rootRoll += actor.winding;
                actor.installValue(next, dt);
                if (actor.clock >= actor.currentClip.duration_ms) {
                    actor.moving = false;
                    actor.clipFinished(actor.clipId);
                    if (!actor.reviewing && !actor.reading && !actor.ownerInteracting)
                        actor.scheduleRest();
                }
            }
        }
    }
    Timer {
        id: rest
        interval: actor.director ? 7000 + Math.round(actor.director.random() * 11000) : 9000
        onTriggered: actor.chooseNext()
    }
    Timer {
        interval: 6300
        repeat: true
        running: actor.visible && !actor.paused && !actor.reduced
        onTriggered: {
            actor.blink = true;
            blinkEnd.restart();
        }
    }
    Timer {
        id: blinkEnd
        interval: 120
        onTriggered: actor.blink = false
    }
    Item {
        x: 160 * actor.factor
        y: 160 * actor.factor
        scale: actor.factor
        transformOrigin: Item.TopLeft
        visible: actor.ready
        Repeater {
            id: pieces
            model: actor.pose ? Motion.drawOrder : []
            delegate: RigPiece {
                required property int modelData
                part: actor.pose.parts.find(p => p.tag === Motion.sourceTag(modelData))
                rectangle: Motion.partRect(actor.pose, modelData)
                matrix: actor.matrices[modelData]
                imageSource: "file://" + actor.assets + "/actor/" + actor.poseName + "-part-" + Motion.sourceTag(modelData) + ".png"
                textureFactor: Math.min(1, actor.factor * Screen.devicePixelRatio * 2)
                z: actor.value.legDepth > .5 && (modelData === 7 || modelData === 8) ? -1 : 0
            }
        }
        Expression {
            visible: actor.pose !== null
            pose: actor.pose || ({
                    eyes: [],
                    mouth: [0, 0]
                })
            emotion: actor.emotion
            blink: actor.blink
            transform: Matrix4x4 {
                property var m: actor.matrices[1] || [1, 0, 0, 0]
                matrix: Qt.matrix4x4(m[0], -m[1], 0, m[2], m[1], m[0], 0, m[3], 0, 0, 1, 0, 0, 0, 0, 1)
            }
        }
    }
}
