import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Button {
    id: control
    property bool primary: false
    implicitHeight: Math.max(44, label.implicitHeight + 20)
    implicitWidth: Math.min(parent && parent.width > 0 ? parent.width : 10000, Math.max(44, label.implicitWidth + 28))
    font.family: "Inter"
    Accessible.name: text
    contentItem: Text {
        id: label
        textFormat: Text.PlainText
        text: control.text
        font: control.font
        wrapMode: Text.Wrap
        color: !control.enabled ? Theme.subtle : control.primary ? Theme.onGreen : Theme.ink
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: Theme.controlRadius
        color: !control.enabled ? Theme.raised : control.primary ? (control.down ? "#2ad485" : control.hovered ? "#8cffc8" : Theme.green) : (control.down ? "#423044" : control.hovered ? "#35303f" : control.flat ? "transparent" : Theme.raised)
        border.color: control.visualFocus ? Theme.pink : control.primary || control.flat ? "transparent" : Theme.outline
        border.width: control.visualFocus ? 2 : 1
    }
}
