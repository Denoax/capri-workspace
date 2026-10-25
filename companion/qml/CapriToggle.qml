import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Switch {
    id: control
    implicitHeight: Math.max(44, label.implicitHeight + 12)
    implicitWidth: label.implicitWidth + 64
    font.family: "Inter"
    indicator: Rectangle {
        x: 0
        y: (control.height - height) / 2
        width: 42
        height: 24
        radius: 12
        color: control.checked ? Theme.green : Theme.raised
        border.color: control.visualFocus ? Theme.pink : Theme.outline
        border.width: control.visualFocus ? 2 : 1
        Rectangle {
            x: control.checked ? 21 : 3
            y: 3
            width: 18
            height: 18
            radius: 9
            color: control.checked ? Theme.onGreen : Theme.muted
        }
    }
    contentItem: Text {
        id: label
        text: control.text
        textFormat: Text.PlainText
        font: control.font
        color: control.enabled ? Theme.ink : Theme.subtle
        leftPadding: 56
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap
    }
}
