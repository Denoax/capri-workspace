import QtQuick
import QtQuick.Controls
import QtCore
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import Quickshell.Hyprland

ShellRoot {
    id: root
    property bool hidden: false
    property bool composer: false
    property bool settingsOpen: false
    property bool commandMode: false
    property var snapshot: ({
            history: [],
            models: [],
            memories: [],
            state: "idle",
            provider: "offline_test",
            locked: true,
            error: ""
        })
    property string notice: ""
    property string partial: ""
    property int sequence: 0
    property string idleState: "idle"
    property bool visualDemo: false
    property string selectedOutput: Quickshell.env("CAPRI_SCREEN") || preferences.output
    property int idleIndex: 0
    property bool evidence: Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1"
    property string assets: Quickshell.env("CAPRI_ASSETS")
    property bool fullscreen: Hyprland.focusedWorkspace?.hasFullscreen ?? false
    property string acting: snapshot.state === "idle" ? (composer ? "listening" : idleState) : snapshot.state
    property bool paused: hidden || snapshot.locked || (!composer && preferences.hideFullscreen && fullscreen)
    property var hitRects: []
    Settings {
        id: preferences
        location: Quickshell.env("CAPRI_SETTINGS")
        property real characterSize: 280
        property bool reduced: false
        property bool hideFullscreen: true
        property string output: Quickshell.env("CAPRI_SCREEN") || ""
        property real actorX: 100
        property real actorY: 420
    }
    FontLoader {
        id: face
        source: "file://" + root.assets + "/fonts/Manrope/Manrope-Variable.ttf"
    }
    function send(method, args) {
        if (!socket.connected) {
            notice = "Core disconnected; actions are disabled.";
            return;
        }
        sequence++;
        socket.write(JSON.stringify({
            method: method,
            seq: sequence,
            args: args
        }) + "\n");
        socket.flush();
    }
    function submit() {
        if (!entry.text.trim())
            return;
        send("submit", {
            text: entry.text,
            mode: root.commandMode ? "command" : "chat"
        });
        entry.text = "";
        partial = "";
    }
    function command(text) {
        send("submit", {
            text: text,
            mode: "command"
        });
        partial = "";
    }
    Socket {
        id: socket
        path: Quickshell.env("CAPRI_SOCKET")
        connected: true
        onConnectionStateChanged: {
            if (connected) {
                root.sequence = 0;
                write(JSON.stringify({
                    version: 1,
                    role: "shell",
                    token: Quickshell.env("CAPRI_UI_TOKEN")
                }) + "\n");
                flush();
            } else {
                root.snapshot = Object.assign({}, root.snapshot, {
                    locked: true
                });
                root.notice = "Core disconnected. Authority revoked.";
            }
        }
        parser: SplitParser {
            onRead: data => {
                try {
                    const m = JSON.parse(data);
                    if (m.event === "snapshot") {
                        root.snapshot = m;
                        root.partial = "";
                    } else if (m.event === "delta")
                        root.partial = m.text;
                    else if (m.event === "notice" || m.event === "denied")
                        root.notice = m.text;
                    else if (m.event === "hide")
                        root.hidden = true;
                    else if (m.event === "summon") {
                        root.hidden = false;
                        root.composer = true;
                    } else if (m.event === "quit")
                        Quickshell.quit();
                } catch (e) {
                    root.notice = "Invalid core message; actions disabled.";
                    root.send("stop", {});
                }
            }
        }
    }
    Timer {
        interval: 1000
        running: socket.connected
        repeat: true
        onTriggered: root.send("heartbeat", {})
    }
    Timer {
        interval: 11000
        running: !root.paused && !root.composer && !root.visualDemo && root.snapshot.state === "idle"
        repeat: true
        onTriggered: {
            root.idleIndex++;
            root.idleState = ["idle", "curious", "idle", "listening"][root.idleIndex % 4];
        }
    }
    Timer {
        interval: 1000
        repeat: true
        running: !socket.connected
        onTriggered: socket.connected = true
    }
    FileView {
        path: root.assets + "/input-regions.json"
        onLoaded: root.hitRects = JSON.parse(text())
    }
    PanelWindow {
        id: stage
        visible: root.evidence && !root.hidden
        screen: panel.screen
        anchors {
            right: true
            bottom: true
        }
        margins {
            right: 32
            bottom: 32
        }
        implicitWidth: 520
        implicitHeight: 740
        color: "#14121b"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "capri-evidence-stage"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
        MouseArea {
            anchors.fill: parent
            onClicked: console.log("NATIVE_BACKGROUND_CLICK")
        }
        TextField {
            x: 4
            y: 4
            width: 200
            height: 30
            placeholderText: "Native fixture"
            onActiveFocusChanged: if (activeFocus)
                console.log("NATIVE_BACKGROUND_FOCUS")
        }
    }
    PanelWindow {
        id: panel
        screen: Quickshell.screens.find(s => s.name === root.selectedOutput) || Quickshell.screens[0]
        anchors {
            right: true
            bottom: true
        }
        margins {
            right: 32
            bottom: 32
        }
        implicitWidth: Math.min(520, screen.width)
        implicitHeight: Math.min(740, screen.height)
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "capri-desktop-v1"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: root.composer ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
        visible: !root.paused
        mask: Region {
            id: inputMask
            Region {
                item: composerBox
                width: root.composer ? composerBox.width : 0
                height: root.composer ? composerBox.height : 0
            }
            Region {
                item: controls
            }
        }
        Instantiator {
            model: root.hitRects
            delegate: Region {
                required property var modelData
                x: actor.x + modelData[0] * actor.width
                y: actor.y + modelData[1] * actor.height
                width: modelData[2] * actor.width
                height: modelData[3] * actor.height
            }
            onObjectAdded: (index, object) => inputMask.regions.push(object)
            onObjectRemoved: (index, object) => {
                let r = inputMask.regions;
                inputMask.regions = r.filter(v => v !== object);
            }
        }
        Actor {
            id: actor
            assets: root.assets
            width: Math.min(panel.width - 20, preferences.characterSize * 1856 / 1440)
            height: width * 1440 / 1856
            x: Math.max(0, Math.min(preferences.actorX, panel.width - width))
            y: Math.max(root.composer ? 440 : 0, Math.min(preferences.actorY, panel.height - height - 38))
            state: dragArea.drag.active ? "dragged" : root.acting
            reduced: preferences.reduced
            paused: root.paused
            MouseArea {
                id: dragArea
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                drag.target: actor
                drag.minimumX: 0
                drag.maximumX: panel.width - actor.width
                drag.minimumY: 0
                drag.maximumY: panel.height - actor.height - 38
                onReleased: {
                    preferences.actorX = actor.x;
                    preferences.actorY = actor.y;
                }
                onClicked: mouse => {
                    if (mouse.button === Qt.RightButton) {
                        root.send("stop", {});
                        root.notice = "Stopped.";
                    } else
                        root.composer = !root.composer;
                }
            }
        }
        Row {
            id: controls
            x: Math.max(8, Math.min(actor.x + 40, panel.width - width - 8))
            y: Math.min(actor.y + actor.height, panel.height - height)
            spacing: 6
            CapriButton {
                text: root.composer ? "Close" : "Talk"
                onClicked: root.composer = !root.composer
            }
            CapriButton {
                text: "Stop"
                onClicked: {
                    root.send("stop", {});
                    root.notice = "Stopped. Pending authority revoked.";
                }
            }
            CapriButton {
                text: "Hide"
                onClicked: {
                    root.send("stop", {});
                    root.hidden = true;
                }
            }
        }
        Rectangle {
            id: composerBox
            x: 10
            y: 10
            width: panel.width - 20
            height: 420
            visible: root.composer
            radius: 14
            color: "#211c2a"
            border.color: "#675071"
            border.width: 1
            Column {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 8
                Row {
                    spacing: 10
                    Text {
                        text: "Capri"
                        color: "#f8f3f9"
                        font.pixelSize: 22
                        font.bold: true
                    }
                    Text {
                        text: root.snapshot.provider === "offline_test" ? "Offline test mode" : "ChatGPT plan"
                        color: "#c3b7cc"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    CapriButton {
                        text: "Settings"
                        onClicked: root.settingsOpen = !root.settingsOpen
                    }
                    CapriButton {
                        text: "×"
                        onClicked: root.composer = false
                        Accessible.name: "Close composer"
                    }
                }
                Text {
                    width: parent.width
                    text: root.notice || root.snapshot.error || root.snapshot.state
                    color: "#bdfbd4"
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                }
                CapriButton {
                    id: modeButton
                    text: root.commandMode ? "Commands · exact scoped actions" : "Chat · pasted text is data"
                    onClicked: root.commandMode = !root.commandMode
                }
                ListView {
                    id: history
                    width: parent.width
                    height: root.settingsOpen ? 70 : 168
                    clip: true
                    spacing: 10
                    model: root.snapshot.history || []
                    onCountChanged: positionViewAtEnd()
                    delegate: Column {
                        required property var modelData
                        width: history.width
                        spacing: 3
                        Text {
                            text: modelData.role === "user" ? "You" : "Capri"
                            color: "#c19baa"
                            font.pixelSize: 11
                        }
                        Text {
                            width: parent.width
                            text: modelData.text
                            color: "#f0e9f4"
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                            font.pixelSize: 13
                        }
                    }
                    ScrollBar.vertical: ScrollBar {}
                }
                Column {
                    visible: root.settingsOpen
                    width: parent.width
                    spacing: 4
                    Row {
                        spacing: 8
                        CapriButton {
                            text: "Continue with ChatGPT"
                            onClicked: root.command("/signin")
                        }
                        CapriButton {
                            text: "Sign out"
                            onClicked: root.command("/logout")
                        }
                    }
                    ComboBox {
                        width: parent.width
                        model: root.snapshot.models || []
                        textRole: "name"
                        displayText: root.snapshot.model || "No account models discovered"
                        onActivated: root.command("/model " + root.snapshot.models[currentIndex].id)
                    }
                }
                Text {
                    width: parent.width
                    visible: root.partial !== ""
                    text: root.partial.substring(Math.max(0, root.partial.length - 240))
                    color: "#ddd0e8"
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                }
                ScrollView {
                    width: parent.width
                    height: 65
                    TextArea {
                        id: entry
                        color: "#f2eaf6"
                        selectionColor: "#954463"
                        placeholderTextColor: "#ab9bb6"
                        background: Rectangle {
                            color: "#17131e"
                            radius: 6
                            border.color: "#70516e"
                        }

                        onActiveFocusChanged: if (activeFocus)
                            console.log("NATIVE_ENTRY_FOCUS")
                        placeholderText: "Ask Capri · /help for scoped commands"
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        textFormat: TextEdit.PlainText
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Return && (event.modifiers & Qt.ControlModifier)) {
                                root.submit();
                                event.accepted = true;
                            }
                        }
                    }
                }
                Row {
                    spacing: 8
                    CapriButton {
                        text: "Send"
                        enabled: socket.connected && !root.snapshot.locked
                        onClicked: root.submit()
                    }
                    CapriButton {
                        text: "Stop"
                        onClicked: root.send("stop", {})
                    }
                    CapriButton {
                        text: "Help"
                        onClicked: root.command("/help")
                    }
                    Slider {
                        width: 85
                        from: 180
                        to: 320
                        value: preferences.characterSize
                        Accessible.name: "Character size"
                        onMoved: preferences.characterSize = value
                    }
                    CheckBox {
                        text: "Quiet"
                        checked: preferences.reduced
                        onToggled: preferences.reduced = checked
                    }
                }
            }
        }
    }
    IpcHandler {
        target: "capri"
        function actorGeometry(): string {
            return JSON.stringify({
                x: actor.x,
                y: actor.y,
                width: actor.width,
                height: actor.height
            });
        }
        function placement(x: int, y: int): void {
            preferences.actorX = x;
            preferences.actorY = y;
        }
        function entryFocused(): bool {
            return entry.activeFocus;
        }
        function inputPoint(): string {
            const p = entry.mapToItem(composerBox, 0, 0);
            return (composerBox.x + p.x + 20) + "," + (composerBox.y + p.y + 20);
        }
        function modePoint(): string {
            const p = modeButton.mapToItem(composerBox, 0, 0);
            return (composerBox.x + p.x + 20) + "," + (composerBox.y + p.y + 15);
        }
        function inputMode(): string {
            return root.commandMode ? "command" : "chat";
        }
        function summon(): void {
            root.hidden = false;
            root.composer = true;
        }
        function hide(): void {
            root.send("stop", {});
            root.hidden = true;
        }
        function stop(): void {
            root.send("stop", {});
        }
        function quit(): void {
            root.send("stop", {});
            Quickshell.quit();
        }
        function size(pixels: int): void {
            preferences.characterSize = Math.max(180, Math.min(320, pixels));
        }
        function output(name: string): void {
            root.selectedOutput = name;
            preferences.output = name;
        }
        function presence(): void {
            root.hidden = false;
            root.composer = false;
            root.visualDemo = false;
        }
        function quiet(value: bool): void {
            preferences.reduced = value;
        }
        function pose(name: string): void {
            root.composer = false;
            root.hidden = false;
            root.visualDemo = true;
            if (["idle", "curious", "listening", "thinking", "working", "success", "blocked"].includes(name))
                root.idleState = name;
        }
    }
}
