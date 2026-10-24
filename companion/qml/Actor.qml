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
    property string poseName: state === "success" || state === "working" ? "build" : state === "blocked" || state === "thinking" ? "review" : "plan"
    property var pose: rig ? rig.poses[poseName] : null
    property var matrices: pose ? Motion.matrices(pose, clock, state, reduced) : ({})
    property var order: [1, 9, 10, 7, 8, 2, 5, 6, 3, 4]
    property real factor: width / 1856
    property bool blink: !reduced && (clock % 6300 > 4980 && clock % 6300 < 5120)
    implicitWidth: 370
    implicitHeight: 288
    onStateChanged: {
        clock = 0;
    }
    FileView {
        path: actor.assets + "/actor/RIG.json"
        onLoaded: actor.rig = JSON.parse(text())
    }
    Timer {
        interval: 16
        repeat: true
        running: !actor.paused && !actor.reduced && actor.visible
        onTriggered: actor.clock += 16
    }
    Item {
        x: 160 * actor.factor
        y: 160 * actor.factor
        scale: actor.factor
        transformOrigin: Item.TopLeft
        Repeater {
            model: actor.pose ? actor.order : []
            delegate: Item {
                id: layer
                required property int modelData
                property var part: actor.pose.parts.find(p => p.tag === modelData)
                property var m: actor.matrices[modelData] || [1, 0, 0, 0]
                transform: Matrix4x4 {
                    matrix: Qt.matrix4x4(layer.m[0], -layer.m[1], 0, layer.m[2], layer.m[1], layer.m[0], 0, layer.m[3], 0, 0, 1, 0, 0, 0, 0, 1)
                }
                Image {
                    x: parent.part.origin[0]
                    y: parent.part.origin[1]
                    width: parent.part.size[0]
                    height: parent.part.size[1]
                    source: "file://" + actor.assets + "/actor/" + actor.poseName + "-part-" + parent.modelData + ".png"
                    smooth: true
                    asynchronous: false
                }
                Canvas {
                    visible: parent.modelData === 1 && actor.blink
                    width: 1536
                    height: 1024
                    onVisibleChanged: if (visible)
                        requestPaint()
                    onPaint: {
                        const c = getContext("2d");
                        c.reset();
                        const eyes = actor.pose.eyes;
                        c.fillStyle = "#00ed80";
                        c.strokeStyle = "#0c0715";
                        c.lineWidth = 5;
                        for (let i = 0; i < eyes.length; i++) {
                            const e = eyes[i];
                            c.beginPath();
                            c.ellipse(e[0] - 16, e[1] - 19, 32, 38);
                            c.fill();
                            c.beginPath();
                            c.moveTo(e[0] - 13, e[1] - 7);
                            c.lineTo(e[0], e[1] + 8);
                            c.lineTo(e[0] + 12, e[1] - 7);
                            c.stroke();
                        }
                    }
                }
            }
        }
    }
}
