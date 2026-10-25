import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

TextArea {
    id: entry
    padding: 14
    color: Theme.ink
    placeholderTextColor: Theme.subtle
    selectionColor: Theme.green
    selectedTextColor: Theme.onGreen
    textFormat: TextEdit.PlainText
    wrapMode: TextEdit.Wrap
    selectByMouse: true
    font.family: "Inter"
    background: Rectangle {
        radius: 16
        color: Theme.field
        border.color: entry.activeFocus ? Theme.green : Theme.outline
        border.width: entry.activeFocus ? 2 : 1
    }
}
