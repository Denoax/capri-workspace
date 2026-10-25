import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

TextField {
    id: field
    implicitHeight: Math.max(44, contentHeight + 24)
    implicitWidth: 220
    padding: 12
    color: Theme.ink
    placeholderTextColor: Theme.subtle
    selectionColor: Theme.green
    selectedTextColor: Theme.onGreen
    font.family: "Inter"
    selectByMouse: true
    background: Rectangle {
        radius: Theme.controlRadius
        color: Theme.field
        border.color: field.activeFocus ? Theme.green : Theme.outline
        border.width: field.activeFocus ? 2 : 1
    }
}
