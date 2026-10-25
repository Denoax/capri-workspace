import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "Theme.js" as Theme

FloatingWindow {
    id: window
    required property var owner
    property real textScale: (owner.profile.ui_text_scale || 100) / 100
    property int selectedPane: owner.settingsOpen ? 2 : 0
    property int displayedPane: selectedPane
    property real paneOpacity: 1
    property bool searchOpen: false
    property bool pendingSearchFocus: false
    property bool pendingTextSizeFocus: false
    property bool everSettings: owner.settingsOpen
    property bool everActivity: false
    property string lastScopeRequest: ""
    title: "Capri"
    implicitWidth: 740
    implicitHeight: 700
    minimumSize: Qt.size(420, 420)
    visible: owner.conversationOpen && !owner.snapshot.locked
    color: "transparent"
    function selectPane(index) {
        if (index < 0 || index > 2)
            return;
        owner.flushDraft();
        if (index === 2)
            everSettings = true;
        if (index === 1)
            everActivity = true;
        if (index !== 0)
            longEntry.focus = false;
        selectedPane = index;
        owner.settingsOpen = index === 2;
        if (owner.profile.reduced_motion) {
            paneSwap.stop();
            displayedPane = index;
            paneOpacity = 1;
            Qt.callLater(focusPane);
        } else
            paneSwap.restart();
    }
    function transcriptMetrics() {
        return transcript.metrics();
    }
    function scopePoints() {
        return settingsLoader.item ? settingsLoader.item.scopePoints() : "{}";
    }
    function revealScopeSave() {
        selectPane(2);
        Qt.callLater(() => {
            if (settingsLoader.item)
                settingsLoader.item.revealScopeSave();
        });
    }
    function revealScope() {
        selectPane(2);
        Qt.callLater(() => {
            if (settingsLoader.item)
                settingsLoader.item.revealScope();
        });
    }
    function reviewState() {
        return JSON.stringify({
            width: window.width,
            height: window.height,
            selectedPane: selectedPane,
            displayedPane: displayedPane,
            opacity: paneOpacity,
            composerFocused: longEntry.activeFocus,
            searchFocused: search.activeFocus,
            contextFocused: contextChoice.activeFocus,
            modeFocused: modeChoice.activeFocus,
            sendFocused: sendButton.activeFocus,
            draftLength: owner.draftLocal.length,
            mode: owner.inputModeIndex,
            textScale: textScale,
            transcript: JSON.parse(transcript.metrics()),
            screenProperty: "screen" in window,
            nav: navigation.reviewState()
        });
    }

    function reviewPoints() {
        function at(item) {
            var p = item.mapToItem(chrome, item.width / 2, item.height / 2);
            return {
                x: p.x,
                y: p.y
            };
        }
        return JSON.stringify({
            composer: at(longEntry),
            send: at(sendButton),
            mode: at(modeChoice),
            context: at(contextChoice),
            close: at(closeWindowButton),
            search: at(search),
            scope: settingsLoader.item ? settingsLoader.item.reviewPoints(chrome) : null
        });
    }
    function revealTextSize() {
        pendingTextSizeFocus = true;
        selectPane(2);
    }

    function focusPane() {
        if (displayedPane === 0 && pendingSearchFocus) {
            pendingSearchFocus = false;
            search.forceActiveFocus();
            return;
        }
        if (displayedPane === 2 && pendingTextSizeFocus && settingsLoader.item) {
            pendingTextSizeFocus = false;
            settingsLoader.item.revealTextSize();
            return;
        }
        if (displayedPane === 2 && settingsLoader.item)
            settingsLoader.item.forceActiveFocus();
        else if (displayedPane === 1 && activityLoader.item)
            activityLoader.item.forceActiveFocus();
        else if (displayedPane === 0)
            longEntry.forceActiveFocus();
    }

    function closeWindow() {
        owner.flushDraft();
        owner.conversationOpen = false;
    }
    onVisibleChanged: if (!visible && owner.conversationOpen && !owner.snapshot.locked)
        Qt.callLater(() => {
            if (!window.visible)
                window.closeWindow();
        })
    Connections {
        target: window.owner
        function onSettingsOpenChanged() {
            if (window.owner.settingsOpen && window.selectedPane !== 2)
                window.selectPane(2);
            else if (!window.owner.settingsOpen && window.selectedPane === 2)
                window.selectPane(0);
        }
        function onFocusConversation() {
            if (window.selectedPane === 0)
                Qt.callLater(() => longEntry.forceActiveFocus());
        }
        function onSnapshotChanged() {
            var id = window.owner.snapshot.scope_request?.id || "";
            if (id && id !== window.lastScopeRequest)
                window.selectPane(1);
            window.lastScopeRequest = id;
        }
    }
    SequentialAnimation {
        id: paneSwap
        onFinished: window.focusPane()
        NumberAnimation {
            target: window
            property: "paneOpacity"
            to: 0
            duration: 85
            easing.type: Easing.InCubic
        }
        ScriptAction {
            script: window.displayedPane = window.selectedPane
        }
        NumberAnimation {
            target: window
            property: "paneOpacity"
            to: 1
            duration: 145
            easing.type: Easing.OutCubic
        }
    }
    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: {
            window.selectPane(0);
            window.searchOpen = true;
            window.pendingSearchFocus = true;
            if (window.displayedPane === 0)
                Qt.callLater(() => search.forceActiveFocus());
        }
    }
    Shortcut {
        sequence: "Alt+1"
        onActivated: window.selectPane(0)
    }
    Shortcut {
        sequence: "Alt+2"
        onActivated: window.selectPane(1)
    }
    Shortcut {
        sequence: "Alt+3"
        onActivated: window.selectPane(2)
    }
    Shortcut {
        sequence: "Escape"
        onActivated: window.closeWindow()
    }
    Shortcut {
        sequence: "Ctrl+."
        onActivated: window.owner.stop()
    }
    Pane {
        id: chrome
        anchors.fill: parent
        padding: 12
        font.family: "Inter"
        font.pixelSize: 15 * window.textScale
        palette.window: Theme.canvas
        palette.base: Theme.field
        palette.text: Theme.ink
        palette.windowText: Theme.ink
        palette.buttonText: Theme.ink
        palette.button: Theme.raised
        palette.highlight: Theme.green
        palette.highlightedText: Theme.onGreen
        palette.placeholderText: Theme.subtle
        background: Rectangle {
            color: Theme.canvas
            radius: Theme.largeRadius
        }
        Dialog {
            id: patchReview
            visible: !!owner.snapshot.maintenance_review
            title: "Review Capri proposal"
            modal: true
            closePolicy: Popup.NoAutoClose
            x: 12
            y: 12
            width: parent.width - 24
            height: parent.height - 24
            ColumnLayout {
                anchors.fill: parent
                Text {
                    text: "Self-authored proposal · " + (owner.snapshot.maintenance_review?.digest || "")
                    color: Theme.ink
                    wrapMode: Text.WrapAnywhere
                    Layout.fillWidth: true
                }
                Text {
                    text: "Changed: " + (owner.snapshot.maintenance_review?.files || []).join(", ") + "\nTests: " + (owner.snapshot.maintenance_review?.verification ? "exit " + owner.snapshot.maintenance_review.verification.exit_code + "; host checks remain separate" : "not run")
                    color: Theme.muted
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    TextArea {
                        text: owner.snapshot.maintenance_review?.patch || "No source differences."
                        readOnly: true
                        textFormat: TextEdit.PlainText
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        color: Theme.ink
                        font.family: "monospace"
                        font.pixelSize: 13 * window.textScale
                    }
                }
                ColumnLayout {
                    CapriButton {
                        Layout.fillWidth: true
                        text: "Install exact reviewed version"
                        enabled: !!owner.snapshot.maintenance_review?.verification && owner.snapshot.maintenance_review.verification.exit_code === 0 && owner.snapshot.maintenance_review.verification.digest === owner.snapshot.maintenance_review.digest && !owner.snapshot.maintenance_review.patch_truncated && owner.snapshot.maintenance_review.files.length > 0
                        onClicked: owner.send("maintenance_install", {
                            id: owner.snapshot.maintenance_review.id,
                            digest: owner.snapshot.maintenance_review.digest
                        })
                    }
                    CapriButton {
                        Layout.fillWidth: true
                        text: "Keep staged"
                        onClicked: owner.send("maintenance_close", {})
                    }
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text {
                    text: "Capri"
                    font.family: "Inter"
                    font.pixelSize: 26 * window.textScale
                    font.weight: Font.DemiBold
                    color: Theme.ink
                    Layout.fillWidth: true
                }
                CapriButton {
                    text: window.owner.snapshot.provider === "chatgpt_plan" ? "Model" : "Connect"
                    flat: true
                    font.pixelSize: 14 * window.textScale
                    onClicked: accountMenu.open()
                    ToolTip.visible: hovered
                    ToolTip.text: window.owner.snapshot.model || "Continue with your ChatGPT account"
                }
                CapriButton {
                    text: "Stop"
                    visible: window.owner.busy && window.selectedPane !== 0
                    onClicked: window.owner.stop()
                    Accessible.name: "Stop current work"
                }
                CloseButton {
                    id: closeWindowButton
                    onClicked: window.closeWindow()
                }
            }
            CapriNavigation {
                id: navigation
                Layout.fillWidth: true
                currentIndex: window.selectedPane
                textScale: window.textScale
                reduced: !!window.owner.profile.reduced_motion
                onSelected: index => window.selectPane(index)
            }
            Text {
                visible: !!window.owner.snapshot.error
                text: window.owner.snapshot.error
                textFormat: Text.PlainText
                color: Theme.danger
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.largeRadius
                color: Theme.surface
                border.color: Theme.outline
                StackLayout {
                    anchors.fill: parent
                    anchors.margins: window.width < 600 ? 16 : 24
                    currentIndex: window.displayedPane
                    opacity: window.paneOpacity
                    Item {
                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 12
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                CapriField {
                                    id: search
                                    visible: window.searchOpen
                                    Layout.fillWidth: true
                                    placeholderText: "Find in this conversation"
                                    Accessible.name: "Search visible conversation"
                                }
                                CapriButton {
                                    visible: window.searchOpen
                                    text: "×"
                                    flat: true
                                    onClicked: {
                                        search.text = "";
                                        window.searchOpen = false;
                                    }
                                    Accessible.name: "Close conversation search"
                                }
                                Item {
                                    visible: !window.searchOpen
                                    Layout.fillWidth: true
                                }
                                CapriButton {
                                    text: "Find"
                                    visible: !window.searchOpen
                                    flat: true
                                    font.pixelSize: 13 * window.textScale
                                    onClicked: {
                                        window.searchOpen = true;
                                        Qt.callLater(() => search.forceActiveFocus());
                                    }
                                    Accessible.name: "Find in conversation, Ctrl F"
                                }
                            }
                            TranscriptView {
                                id: transcript
                                owner: window.owner
                                textScale: window.textScale
                                query: search.text
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                            }
                            CapriButton {
                                text: "Jump to latest"
                                visible: !transcript.followLatest
                                flat: true
                                onClicked: transcript.latest()
                                Layout.alignment: Qt.AlignHCenter
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.maximumWidth: 820
                                Layout.alignment: Qt.AlignHCenter
                                spacing: 8
                                CapriTextArea {
                                    id: longEntry
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Math.min(150 * window.textScale, Math.max(78 * window.textScale, contentHeight + 28))
                                    text: window.owner.draftLocal
                                    placeholderText: window.owner.inputModeIndex === 1 ? "Describe a task inside your selected scope…" : "Ask Capri…"
                                    Accessible.name: "Message to Capri"
                                    onTextChanged: if (activeFocus && text !== window.owner.draftLocal)
                                        window.owner.editDraft(text)
                                    KeyNavigation.priority: KeyNavigation.BeforeItem
                                    KeyNavigation.tab: contextChoice
                                    Keys.onPressed: event => window.owner.inputKey(event)
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    CapriButton {
                                        id: contextChoice
                                        text: "+"
                                        flat: true
                                        font.pixelSize: 22
                                        onClicked: contextMenu.open()
                                        Accessible.name: "Project context and task scope"
                                    }
                                    CapriButton {
                                        id: modeChoice
                                        text: ["Chat", "Task", "Commands"][window.owner.inputModeIndex] + " ▾"
                                        flat: true
                                        onClicked: modeMenu.open()
                                        Accessible.name: "Request type: " + ["Chat", "Task", "Commands"][window.owner.inputModeIndex]
                                    }
                                    Item {
                                        Layout.fillWidth: true
                                    }
                                    CapriButton {
                                        id: sendButton
                                        text: window.owner.busy ? "Stop" : "Send"
                                        primary: !window.owner.busy
                                        enabled: window.owner.busy || window.owner.draftLocal.trim().length > 0
                                        onClicked: window.owner.busy ? window.owner.stop() : window.owner.submitDraft()
                                        Accessible.name: window.owner.busy ? "Stop current work" : "Send message"
                                    }
                                }
                            }
                        }
                    }
                    Loader {
                        id: activityLoader
                        active: window.everActivity
                        sourceComponent: ActivityView {
                            owner: window.owner
                            onChangeScope: window.revealScope()
                        }
                    }
                    Loader {
                        id: settingsLoader
                        active: window.everSettings
                        sourceComponent: SettingsView {
                            owner: window.owner
                        }
                    }
                }
            }
        }
        Menu {
            id: modeMenu
            CapriMenuItem {
                text: "Chat"
                checkable: true
                checked: window.owner.inputModeIndex === 0
                onTriggered: window.owner.inputModeIndex = 0
            }
            CapriMenuItem {
                text: "Task · selected scope"
                checkable: true
                checked: window.owner.inputModeIndex === 1
                onTriggered: window.owner.inputModeIndex = 1
            }
            Menu {
                title: "Advanced"
                CapriMenuItem {
                    text: "Commands"
                    checkable: true
                    checked: window.owner.inputModeIndex === 2
                    onTriggered: window.owner.inputModeIndex = 2
                }
            }
        }
        Menu {
            id: contextMenu
            CapriMenuItem {
                text: "Choose task scope…"
                onTriggered: window.revealScope()
            }
            CapriMenuItem {
                text: "View task activity"
                onTriggered: window.selectPane(1)
            }
        }
        Menu {
            id: accountMenu
            CapriMenuItem {
                text: window.owner.snapshot.model || "No model connected"
                enabled: false
            }
            CapriMenuItem {
                text: "Account and models…"
                onTriggered: window.selectPane(2)
            }
            CapriMenuItem {
                text: "Continue with ChatGPT"
                visible: window.owner.snapshot.provider !== "chatgpt_plan"
                onTriggered: window.owner.command("/signin")
            }
        }
    }
}
