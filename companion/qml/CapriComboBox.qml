import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    implicitHeight: 34
    implicitWidth: 150
    font.family: "Inter"
    font.pixelSize: 13
    contentItem: Text {
        textFormat: Text.PlainText
        text: control.displayText
        leftPadding: 10
        rightPadding: 26
        color: "#efedf2"
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        color: control.down ? "#303039" : "#24242c"
        radius: 8
        border.color: control.visualFocus ? "#43fba5" : "#514655"
    }
    indicator: Text {
        x: control.width - 22
        y: 7
        text: "▾"
        color: "#bdb4c6"
        font.pixelSize: 16
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width
        text: control.textRole ? modelData[control.textRole] : modelData
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            textFormat: Text.PlainText
            text: parent.text
            color: "#efedf2"
            font: control.font
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: parent.highlighted ? "#39313e" : "#1d1c25"
            radius: 5
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
            color: "#1d1c25"
            border.color: "#615064"
            radius: 8
        }
    }
}
