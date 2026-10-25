import QtQuick
import QtQuick.Shapes

Item {
    id: face
    required property var pose
    property string emotion: "neutral"
    property bool blink: false
    // Eyelid aperture, asymmetric lid inclination and mouth contour are authored
    // around the inherited eye/mouth landmarks and cyan-ring identity.
    readonly property var sets: ({
            neutral: [1, 1, 0, 0, 15, 17],
            happy: [.35, .35, -8, 8, 23, 10],
            curious: [1.15, .8, -9, 5, 10, 17],
            puzzled: [.75, 1.05, 13, -8, 5, 9],
            amused: [.5, .65, -6, 8, 24, 23],
            annoyed: [.48, .48, 16, -16, -4, 6],
            startled: [1.23, 1.23, -4, 4, 12, 30],
            focused: [.65, .65, 7, -7, 4, 7],
            sleepy: [.22, .3, 3, 6, 9, 18]
        })
    readonly property var expression: sets[emotion] || sets.neutral
    Repeater {
        model: face.pose.eyes
        delegate: Item {
            required property int index
            required property var modelData
            x: modelData[0] - 23
            y: modelData[1] - 23
            width: 46
            height: 46
            rotation: index === 0 ? 18 : 27
            property real aperture: face.blink ? .07 : face.expression[index]
            Rectangle {
                anchors.fill: parent
                radius: 23
                color: "#080311"
                border.width: 2
                border.color: "#00f572"
            }
            Item {
                anchors.centerIn: parent
                width: 36
                height: Math.min(41, 36 * parent.aperture)
                clip: true
                Rectangle {
                    width: 36
                    height: 36
                    anchors.centerIn: parent
                    radius: 18
                    color: "#09c6d6"
                }
                Rectangle {
                    width: 29
                    height: 29
                    anchors.centerIn: parent
                    radius: 15
                    color: "#08061a"
                }
                Rectangle {
                    width: 21
                    height: 21
                    anchors.centerIn: parent
                    radius: 11
                    color: "#5bb9e8"
                }
                Rectangle {
                    width: 12
                    height: 12
                    anchors.centerIn: parent
                    radius: 6
                    color: "#090518"
                }
            }
            Rectangle {
                x: 2
                y: 2
                width: 42
                height: Math.max(0, (1 - parent.aperture) * 22)
                color: "#080311"
                rotation: face.expression[index + 2]
            }
        }
    }
    Item {
        x: face.pose.mouth[0] - 22
        y: face.pose.mouth[1] - 17
        width: 44
        height: 40
        rotation: 24
        Rectangle {
            anchors.fill: parent
            color: "#080311"
            radius: 12
        }
        Shape {
            anchors.fill: parent
            ShapePath {
                strokeColor: "#f5f5f2"
                strokeWidth: 1.5
                fillColor: "#f5f5f2"
                startX: 6
                startY: 9
                PathQuad {
                    x: 37
                    y: 9
                    controlX: 22
                    controlY: 9 + face.expression[4]
                }
                PathQuad {
                    x: 6
                    y: 9
                    controlX: 20
                    controlY: 9 + face.expression[5]
                }
            }
        }
    }
}
