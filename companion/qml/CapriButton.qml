import QtQuick
import QtQuick.Controls

Button {
    id: control
    implicitHeight: 30
    implicitWidth: Math.max(48, label.implicitWidth + 20)
    font.family: "Manrope"
    font.pixelSize: 12
    contentItem: Text {
        id: label
        text: control.text
        font: control.font
        color: control.enabled ? "#f5eaf5" : "#817489"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 6
        color: control.down ? "#513448" : control.hovered ? "#3b293b" : "#2c2435"
        border.color: control.visualFocus ? "#f15d95" : "#65516d"
        border.width: 1
    }
}
