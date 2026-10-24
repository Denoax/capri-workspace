import QtQuick
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    implicitHeight: 34
    implicitWidth: Math.max(48, label.implicitWidth + 20)
    font.family: "Inter"
    font.pixelSize: 13
    contentItem: Text {
        id: label
        textFormat: Text.PlainText
        text: control.text
        font: control.font
        color: control.primary ? "#082015" : control.enabled ? "#f5eaf5" : "#817489"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 6
        color: control.primary ? (control.down ? "#29ce80" : control.hovered ? "#8cffc8" : "#43fba5") : control.down ? "#513448" : control.hovered ? "#3b293b" : "#2c2435"
        border.color: control.visualFocus ? "#f15d95" : "#65516d"
        border.width: 1
    }
}
