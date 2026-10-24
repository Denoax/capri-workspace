import QtQuick
import QtQuick.Controls

Rectangle {
    id: bubble
    required property var owner
    property bool tailRight: true
    property real anchorY: 60
    function inputPoint() {
        return entry.mapToItem(bubble, entry.width / 2, entry.height / 2);
    }
    function modePoint() {
        return mode.mapToItem(bubble, mode.width / 2, mode.height / 2);
    }
    function conversationPoint() {
        return conversationButton.mapToItem(bubble, conversationButton.width / 2, conversationButton.height / 2);
    }
    function entryFocused() {
        return entry.activeFocus;
    }
    color: "#1d1c25"
    radius: 16
    border.color: "#615064"
    implicitHeight: body.implicitHeight + 32
    Column {
        id: body
        x: 18
        y: 16
        width: parent.width - 36
        spacing: 10
        Row {
            width: parent.width
            Text {
                text: owner.busy ? (owner.snapshot.task_phase || "Thinking") : "Capri"
                color: "#43fba5"
                font.family: "Inter"
                font.pixelSize: 15
                width: body.width - (owner.busy ? 128 : 32)
                Accessible.name: text
            }
            CapriButton {
                text: "Stop"
                visible: owner.busy
                onClicked: owner.stop()
                Accessible.name: "Stop Capri's current task"
            }
            CapriButton {
                text: "×"
                implicitWidth: 28
                onClicked: owner.dismiss()
                Accessible.name: "Dismiss speech and retain draft"
            }
        }
        Text {
            width: parent.width
            text: owner.bubbleText
            textFormat: Text.PlainText
            color: "#efedf2"
            font.family: "Inter"
            font.pixelSize: 15
            wrapMode: Text.Wrap
            lineHeight: 1.4
            maximumLineCount: 5
            elide: Text.ElideRight
            Accessible.name: text
        }
        Flow {
            width: parent.width
            spacing: 6
            CapriButton {
                text: "Reply"
                primary: true
                visible: !owner.replyOpen
                onClicked: owner.openReply()
            }
            CapriButton {
                id: conversationButton
                text: "Open conversation"
                onClicked: owner.openConversation()
            }
            CapriButton {
                text: "Why this?"
                visible: owner.noticeActive
                onClicked: {
                    owner.whyOpen = !owner.whyOpen;
                }
            }
            CapriButton {
                text: "Snooze"
                visible: owner.noticeActive
                onClicked: {
                    owner.send("snooze", {
                        minutes: 180
                    });
                    owner.dismiss();
                }
            }
        }
        Text {
            width: parent.width
            visible: owner.whyOpen
            text: owner.snapshot.notice?.why || ""
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: "#bdb4c6"
            font.pixelSize: 12
        }
        Column {
            visible: owner.replyOpen
            width: parent.width
            spacing: 8
            Rectangle {
                width: parent.width
                height: 1
                color: "#453b4b"
            }
            TextArea {
                id: entry
                width: parent.width
                height: Math.min(120, Math.max(64, contentHeight + 20))
                text: owner.draftLocal
                placeholderText: "Ask Capri…"
                placeholderTextColor: "#9a91a6"
                wrapMode: TextEdit.Wrap
                textFormat: TextEdit.PlainText
                color: "#efedf2"
                font.family: "Inter"
                font.pixelSize: 15
                selectByMouse: true
                Accessible.name: "Quick reply to Capri"
                background: Rectangle {
                    color: "#15141c"
                    radius: 8
                    border.color: entry.activeFocus ? "#43fba5" : "#514655"
                }
                onTextChanged: if (activeFocus && text !== owner.draftLocal)
                    owner.editDraft(text)
                Keys.onPressed: event => owner.inputKey(event)
                Connections {
                    target: owner
                    function onFocusQuick() {
                        entry.forceActiveFocus();
                    }
                }
            }
            Row {
                spacing: 6
                CapriComboBox {
                    id: mode
                    model: ["Chat", "Task", "Commands"]
                    currentIndex: owner.inputModeIndex
                    onActivated: owner.inputModeIndex = currentIndex
                    Accessible.name: "Request type"
                    width: 112
                }
                CapriButton {
                    text: owner.busy ? "Running…" : "Send"
                    enabled: !owner.busy && owner.draftLocal.trim().length > 0
                    onClicked: owner.submitDraft()
                }
                CapriButton {
                    text: owner.profile.pinned ? "Unpin" : "Pin"
                    onClicked: owner.preference("pinned", !owner.profile.pinned)
                }
            }
        }
    }
}
