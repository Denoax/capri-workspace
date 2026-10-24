import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell

FloatingWindow {
    id: window
    required property var owner
    title: "Capri"
    implicitWidth: 740
    implicitHeight: 700
    minimumSize: Qt.size(420, 420)
    visible: owner.conversationOpen && !owner.snapshot.locked
    color: "#19191f"
    onVisibleChanged: if (!visible)
        owner.conversationOpen = false
    Pane {
        anchors.fill: parent
        padding: 0
        palette.window: "#19191f"
        palette.base: "#111219"
        palette.windowText: "#efedf2"
        palette.text: "#efedf2"
        palette.button: "#24242c"
        palette.buttonText: "#efedf2"
        palette.placeholderText: "#9a91a6"
        palette.highlight: "#43fba5"
        palette.highlightedText: "#082015"
        palette.mid: "#514655"
        palette.light: "#514655"
        palette.dark: "#111219"
        background: Rectangle {
            color: "#19191f"
        }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "Capri"
                    color: "#efedf2"
                    font.family: "Manrope"
                    font.pixelSize: 23
                    Layout.fillWidth: true
                }
                CapriButton {
                    text: "Settings"
                    onClicked: owner.settingsOpen = !owner.settingsOpen
                }
                CapriButton {
                    text: "Stop"
                    onClicked: owner.stop()
                    Accessible.name: "Stop current work"
                }
                CapriButton {
                    text: "Close"
                    onClicked: {
                        owner.flushDraft();
                        owner.conversationOpen = false;
                    }
                }
            }
            Text {
                text: owner.snapshot.error || (owner.snapshot.provider === "chatgpt_plan" ? "ChatGPT plan · " + owner.snapshot.model : "No model connected · Settings → Continue with ChatGPT")
                textFormat: Text.PlainText
                color: owner.snapshot.error ? "#ff94b6" : "#a5a2af"
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Loader {
                active: owner.settingsOpen
                visible: active
                Layout.fillWidth: true
                Layout.preferredHeight: active ? 370 : 0
                sourceComponent: SettingsView {
                    owner: window.owner
                }
            }
            TextField {
                id: search
                visible: !owner.settingsOpen
                placeholderText: "Find in this conversation"
                Layout.fillWidth: true
                Accessible.name: "Search visible conversation"
            }
            Flickable {
                id: transcript
                clip: true
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: !owner.settingsOpen
                contentWidth: width
                contentHeight: history.height
                property bool followLatest: true
                onMovementEnded: followLatest = contentY + height >= contentHeight - 36
                onContentHeightChanged: if (followLatest)
                    Qt.callLater(() => contentY = Math.max(0, contentHeight - height))
                ScrollBar.vertical: ScrollBar {
                    onPressedChanged: if (!pressed)
                        transcript.followLatest = transcript.contentY + transcript.height >= transcript.contentHeight - 36
                }
                Column {
                    id: history
                    width: transcript.width
                    spacing: 22
                    Repeater {
                        model: owner.snapshot.history || []
                        delegate: Column {
                            required property var modelData
                            width: history.width
                            spacing: 6
                            visible: !search.text || modelData.text.toLowerCase().includes(search.text.toLowerCase())
                            height: visible ? implicitHeight : 0
                            Text {
                                text: modelData.role === "user" ? "You" : "Capri"
                                color: modelData.role === "user" ? "#cbb8d5" : "#43fba5"
                                font.family: "Inter"
                                font.pixelSize: 12
                            }
                            TextEdit {
                                width: parent.width
                                text: modelData.text
                                textFormat: TextEdit.PlainText
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.Wrap
                                color: "#efedf2"
                                font.family: "Inter"
                                font.pixelSize: 15
                                Accessible.name: (modelData.role === "user" ? "You: " : "Capri: ") + text
                            }
                            Text {
                                visible: modelData.status !== "completed"
                                text: modelData.status
                                color: "#d6a1b3"
                                font.pixelSize: 12
                            }
                        }
                    }
                    TextEdit {
                        width: parent.width
                        visible: owner.partial.length > 0
                        text: owner.partial
                        textFormat: TextEdit.PlainText
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        color: "#efedf2"
                        font.family: "Inter"
                        font.pixelSize: 15
                    }
                    Text {
                        visible: owner.busy
                        text: owner.snapshot.task_phase || "Thinking…"
                        color: "#43fba5"
                        font.pixelSize: 13
                    }
                }
            }
            CapriButton {
                text: "Jump to latest"
                visible: !transcript.followLatest
                onClicked: {
                    transcript.followLatest = true;
                    transcript.contentY = Math.max(0, transcript.contentHeight - transcript.height);
                }
            }
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#39333f"
            }
            TextArea {
                id: longEntry
                Layout.fillWidth: true
                Layout.preferredHeight: 90
                text: owner.draftLocal
                placeholderText: "Ask, or select Task to work inside your chosen scope"
                placeholderTextColor: "#9a91a6"
                wrapMode: TextEdit.Wrap
                textFormat: TextEdit.PlainText
                color: "#efedf2"
                font.family: "Inter"
                font.pixelSize: 15
                selectByMouse: true
                Accessible.name: "Message to Capri"
                background: Rectangle {
                    radius: 10
                    color: "#111219"
                    border.color: longEntry.activeFocus ? "#43fba5" : "#514655"
                }
                onTextChanged: if (activeFocus && text !== owner.draftLocal)
                    owner.editDraft(text)
                Keys.onPressed: event => owner.inputKey(event)
                Connections {
                    target: owner
                    function onFocusConversation() {
                        longEntry.forceActiveFocus();
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                CapriComboBox {
                    model: ["Chat", "Task", "Commands"]
                    currentIndex: owner.inputModeIndex
                    onActivated: owner.inputModeIndex = currentIndex
                    Accessible.name: "Request type"
                }
                Text {
                    text: owner.inputModeIndex === 1 ? (owner.snapshot.work_available ? "Scoped agent task" : "Work engine not yet available") : ""
                    color: "#a5a2af"
                    Layout.fillWidth: true
                    font.pixelSize: 12
                }
                CapriButton {
                    text: owner.busy ? "Running…" : "Send"
                    enabled: !owner.busy && owner.draftLocal.trim().length > 0
                    onClicked: owner.submitDraft()
                }
            }
        }
    }
}
