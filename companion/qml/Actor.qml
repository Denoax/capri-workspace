import QtQuick
import Quickshell.Io
import "Motion.js" as Motion

Item {
    id: actor
    required property string assets
    property string state: "idle"
    property bool reduced: false
    property bool paused: false
    property var rig: null
    property real clock: 0
    property bool moving: false
    property string poseName: "plan"
    property var pose: rig ? rig.poses[poseName] : null
    property var matrices: pose ? Motion.matrices(pose, clock, state, reduced) : ({})
    property var order: [1, 9, 10, 7, 8, 2, 5, 6, 3, 4]
    property real factor: width / 1856
    property bool blink: false
    property point mouth: {
        if (!pose)
            return Qt.point(width / 2, height / 3);
        const p = Motion.point(pose.mouth, matrices[1] || [1, 0, 0, 0]);
        return Qt.point((160 + p[0]) * factor, (160 + p[1]) * factor);
    }
    property bool ready: {
        if (!rig || pieces.count !== 10)
            return false;
        for (let i = 0; i < pieces.count; i++) {
            const p = pieces.itemAt(i);
            if (!p || !p.imageReady)
                return false;
        }
        return true;
    }
    implicitWidth: 370
    implicitHeight: 288
    function startGesture() {
        if (!reduced && !paused) {
            clock = 0;
            moving = true;
        }
    }
    onStateChanged: {
        const next = state === "success" || state === "working" ? "build" : state === "blocked" || state === "thinking" ? "review" : "plan";
        if (next !== poseName && !reduced) {
            poseChange.targetPose = next;
            poseChange.restart();
        } else {
            poseName = next;
            startGesture();
        }
    }
    onPausedChanged: if (paused) {
        moving = false;
        blink = false;
    }
    onReducedChanged: if (reduced) {
        moving = false;
        blink = false;
        clock = 0;
    }
    FileView {
        path: actor.assets + "/actor/RIG.json"
        onLoaded: {
            actor.rig = JSON.parse(text());
            actor.startGesture();
        }
    }
    FrameAnimation {
        running: actor.moving && !actor.paused && !actor.reduced && actor.visible
        onTriggered: {
            actor.clock += Math.min(100, frameTime * 1000);
            if (actor.clock >= 3200) {
                actor.clock = 3200;
                actor.moving = false;
            }
        }
    }
    Timer {
        interval: 11000
        repeat: true
        running: !actor.paused && !actor.reduced && actor.visible
        onTriggered: actor.startGesture()
    }
    Timer {
        interval: 6300
        repeat: true
        running: !actor.paused && !actor.reduced && actor.visible
        onTriggered: {
            actor.blink = true;
            blinkEnd.restart();
        }
    }
    Timer {
        id: blinkEnd
        interval: 130
        onTriggered: actor.blink = false
    }
    SequentialAnimation {
        id: poseChange
        property string targetPose: "plan"
        NumberAnimation {
            target: drawing
            property: "opacity"
            to: 0.55
            duration: 90
        }
        ScriptAction {
            script: {
                actor.poseName = poseChange.targetPose;
                actor.startGesture();
            }
        }
        NumberAnimation {
            target: drawing
            property: "opacity"
            to: 1
            duration: 160
        }
    }
    Item {
        id: drawing
        x: 160 * actor.factor
        y: 160 * actor.factor
        scale: actor.factor
        transformOrigin: Item.TopLeft
        Repeater {
            id: pieces
            model: actor.pose ? actor.order : []
            delegate: Item {
                id: layer
                required property int modelData
                property var part: actor.pose.parts.find(p => p.tag === modelData)
                property bool imageReady: portrait.status === Image.Ready
                property var m: actor.matrices[modelData] || [1, 0, 0, 0]
                transform: Matrix4x4 {
                    matrix: Qt.matrix4x4(layer.m[0], -layer.m[1], 0, layer.m[2], layer.m[1], layer.m[0], 0, layer.m[3], 0, 0, 1, 0, 0, 0, 0, 1)
                }
                Image {
                    id: portrait
                    x: layer.part.origin[0]
                    y: layer.part.origin[1]
                    width: layer.part.size[0]
                    height: layer.part.size[1]
                    source: "file://" + actor.assets + "/actor/" + actor.poseName + "-part-" + layer.modelData + ".png"
                    sourceSize: Qt.size(Math.ceil(width * Math.min(1, actor.factor * Screen.devicePixelRatio * 2)), Math.ceil(height * Math.min(1, actor.factor * Screen.devicePixelRatio * 2)))
                    smooth: true
                    asynchronous: true
                    cache: false
                }
                Repeater {
                    model: layer.modelData === 1 && actor.blink ? actor.pose.eyes : []
                    delegate: Item {
                        required property var modelData
                        x: modelData[0] - 16
                        y: modelData[1] - 19
                        width: 32
                        height: 38
                        Rectangle {
                            anchors.fill: parent
                            radius: 16
                            color: "#00ed80"
                        }
                        Rectangle {
                            x: 3
                            y: 16
                            width: 27
                            height: 5
                            radius: 2
                            color: "#0c0715"
                            rotation: 16
                        }
                    }
                }
            }
        }
    }
}
