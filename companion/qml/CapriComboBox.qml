import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

ComboBox {
    id: control
    implicitHeight: Math.max(44, contentItem.implicitHeight + 20)
    implicitWidth: 180
    font.family: "Inter"
    ToolTip.visible: hovered
    ToolTip.text: displayText
    contentItem: Text {
        textFormat: Text.PlainText
        text: control.displayText
        leftPadding: 10
        rightPadding: 26
        color: Theme.ink
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        color: control.down ? "#303039" : "#24242c"
        radius: Theme.controlRadius
        border.color: control.visualFocus ? Theme.green : Theme.outline
    }
    indicator: Text {
        x: control.width - 22
        y: (control.height - height) / 2
        text: "▾"
        color: Theme.muted
        font.pixelSize: 16
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.popup.width
        implicitHeight: Math.max(44, contentItem.implicitHeight + 20)
        text: control.textRole ? modelData[control.textRole] : modelData
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            textFormat: Text.PlainText
            text: parent.text
            color: Theme.ink
            font: control.font
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: parent.highlighted ? "#39313e" : Theme.surface
            radius: 8
        }
    }
    popup: Popup {
        y: control.height + 3
        width: control.width
        padding: 4
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 280)
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle {
            color: Theme.surface
            border.color: Theme.outline
            radius: Theme.controlRadius
        }
    }
}
