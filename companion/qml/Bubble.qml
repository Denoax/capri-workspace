import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Pane {
    id: bubble
    required property var owner
    property bool tailRight: true
    property real anchorY: 60
    property real textScale: (owner.profile.ui_text_scale || 100) / 100
    property bool longReply: owner.bubbleText.length > 520
    padding: 16
    font.family: "Inter"
    font.pixelSize: 15 * textScale
    implicitHeight: body.implicitHeight + 32
    function inputPoint() {
        return entry.mapToItem(bubble, entry.width / 2, entry.height / 2);
    }
    function modePoint() {
        return mode.mapToItem(bubble, mode.width / 2, mode.height / 2);
    }
    function conversationPoint() {
        return more.mapToItem(bubble, more.width / 2, more.height / 2);
    }
    function entryFocused() {
        return entry.activeFocus;
    }
    background: Rectangle {
        color: Theme.surface
        radius: 20
        border.color: Theme.outline
    }
    contentItem: Column {
        id: body
        width: bubble.availableWidth
        spacing: 12
        Row {
            width: parent.width
            spacing: 4
            Text {
                width: parent.width - more.width - close.width - 8
                text: owner.busy ? (owner.snapshot.task_phase || 'Thinking') : 'Capri'
                color: Theme.green
                font.family: 'Inter'
                font.pixelSize: 16 * bubble.textScale
                font.weight: Font.Medium
                wrapMode: Text.Wrap
                anchors.verticalCenter: parent.verticalCenter
            }
            CapriButton {
                id: more
                text: '···'
                flat: true
                implicitWidth: 44
                onClicked: actions.open()
                Accessible.name: 'Reply actions and full conversation'
            }
            CloseButton {
                id: close
                onClicked: owner.dismiss()
                Accessible.name: 'Dismiss speech and keep draft'
            }
        }
        Text {
            width: parent.width
            text: owner.bubbleText
            textFormat: Text.PlainText
            color: Theme.ink
            font.family: 'Inter'
            font.pixelSize: 15 * bubble.textScale
            wrapMode: Text.Wrap
            lineHeight: 1.5
            maximumLineCount: 5
            elide: Text.ElideRight
            Accessible.name: text
        }
        CapriButton {
            visible: !owner.replyOpen
            text: owner.busy ? 'Stop' : bubble.longReply ? 'Read full reply' : 'Reply'
            primary: !owner.busy
            onClicked: owner.busy ? owner.stop() : bubble.longReply ? owner.openConversation() : owner.openReply()
        }
        Text {
            visible: owner.whyOpen
            width: parent.width
            text: owner.snapshot.notice?.why || ''
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 13 * bubble.textScale
            wrapMode: Text.Wrap
        }
        Column {
            visible: owner.replyOpen
            width: parent.width
            spacing: 8
            CapriTextArea {
                id: entry
                width: parent.width
                height: Math.min(150 * bubble.textScale, Math.max(72 * bubble.textScale, contentHeight + 28))
                text: owner.draftLocal
                placeholderText: 'Ask Capri…'
                Accessible.name: 'Quick reply to Capri'
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
                width: parent.width
                spacing: 8
                CapriButton {
                    id: mode
                    text: ['Chat', 'Task', 'Commands'][owner.inputModeIndex] + ' ▾'
                    flat: true
                    onClicked: modeMenu.open()
                    Accessible.name: 'Request type'
                }
                CapriButton {
                    text: owner.busy ? 'Stop' : 'Send'
                    primary: !owner.busy
                    enabled: owner.busy || owner.draftLocal.trim().length > 0
                    onClicked: owner.busy ? owner.stop() : owner.submitDraft()
                }
            }
        }
    }
    Menu {
        id: actions
        CapriMenuItem {
            text: 'Open conversation'
            onTriggered: owner.openConversation()
        }
        CapriMenuItem {
            text: 'Write a reply'
            onTriggered: owner.openReply()
        }
        CapriMenuItem {
            text: owner.profile.pinned ? 'Unpin' : 'Pin here'
            onTriggered: owner.preference('pinned', !owner.profile.pinned)
        }
        CapriMenuItem {
            text: 'Why this?'
            visible: owner.noticeActive
            onTriggered: owner.whyOpen = !owner.whyOpen
        }
        CapriMenuItem {
            text: 'Snooze for 3 hours'
            visible: owner.noticeActive
            onTriggered: {
                owner.send('snooze', {
                    minutes: 180
                });
                owner.dismiss();
            }
        }
        CapriMenuItem {
            text: 'Open message'
            visible: owner.snapshot.notice?.source === 'selected-mail'
            onTriggered: owner.send('mail_open', {})
        }
    }
    Menu {
        id: modeMenu
        CapriMenuItem {
            text: 'Chat'
            onTriggered: owner.inputModeIndex = 0
        }
        CapriMenuItem {
            text: 'Task · selected scope'
            onTriggered: owner.inputModeIndex = 1
        }
        Menu {
            title: 'Advanced'
            CapriMenuItem {
                text: 'Commands'
                onTriggered: owner.inputModeIndex = 2
            }
        }
    }
}
