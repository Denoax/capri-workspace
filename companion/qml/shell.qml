import QtQuick
import QtQuick.Controls
import QtCore
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import Quickshell.Hyprland
import "Theme.js" as Theme
import "Pointer.js" as Pointer
import "Position.js" as PositionAxis

ShellRoot {
    id: root
    property var snapshot: ({
            history: [],
            models: [],
            profile: {},
            locked: true,
            state: "idle",
            provider: "offline_test",
            draft: ""
        })
    property var profile: snapshot.profile || ({})
    property string assets: Quickshell.env("CAPRI_ASSETS")
    property string selectedOutput: Quickshell.env("CAPRI_SCREEN") || placement.output
    property var outputNames: Quickshell.screens.map(s => s.name)
    property var currentScreen: Quickshell.screens.find(s => s.name === selectedOutput) || Quickshell.screens[0]
    property bool hidden: false
    property bool bubbleOpen: false
    property bool replyOpen: false
    property bool conversationOpen: false
    property bool settingsOpen: false
    property bool motionReviewOpen: false
    readonly property var character: actor
    property bool whyOpen: false
    property bool hovered: false
    readonly property bool dragging: position.dragging
    readonly property bool gestureActive: position.captured
    property bool busy: snapshot.state === "thinking" || snapshot.state === "working"
    property bool fullscreen: Hyprland.monitors.values.find(m => m.name === currentScreen?.name)?.activeWorkspace?.hasFullscreen ?? false
    property bool attentionFullscreen: Hyprland.focusedWorkspace?.hasFullscreen ?? false
    property bool presentationPaused: hidden || conversationOpen || snapshot.locked || profile.paused || (fullscreen && !replyOpen && !conversationOpen)
    property bool noticeActive: !!snapshot.notice
    property string partial: ""
    property string noticeText: ""
    property string draftLocal: ""
    property string draftPartition: ""
    property bool draftLoaded: false
    property int inputModeIndex: 0
    property bool renderReported: false
    property int sequence: 0
    property int pendingSubmit: 0
    property string pendingText: ""
    property bool receivedSnapshot: false
    property int lastReply: 0
    property string idleState: "idle"
    property var hitRects: []
    readonly property real actorX: position.x
    readonly property real actorY: position.y
    property real actorHeight: position.model.capture ? position.model.capture.actorHeight : Math.min(profile.character_size || 280, currentScreen ? currentScreen.height - 80 : 280)
    property real actorWidth: actorHeight * 1856 / 1440
    property real mouthX: actorX + (bubbleVisible ? actor.neutralMouth.x : actor.mouth.x)
    property real mouthY: actorY + (bubbleVisible ? actor.neutralMouth.y : actor.mouth.y)
    property bool bubbleLeft: actorX >= bubbleWidth + 22 && (actorX + actorWidth + bubbleWidth + 22 > (currentScreen?.width || 1000) || mouthX > (currentScreen?.width || 1000) / 2)
    property real bubbleWidth: Math.min(390, currentScreen ? currentScreen.width - 24 : 390)
    property real bubbleX: clamp(bubbleLeft ? actorX - bubbleWidth - 22 : actorX + actorWidth + 22, 12, (currentScreen?.width || 1000) - bubbleWidth - 12)
    property real bubbleY: clamp(mouthY - bubble.height / 2, 12, (currentScreen?.height || 800) - bubble.height - 12)
    property bool bubbleVisible: !position.captured && (bubbleOpen || replyOpen || busy || noticeActive)
    readonly property var surfaceActorBounds: {
        if (!position.model.capture)
            return [actor.paintBounds.x, actor.paintBounds.y, actor.paintBounds.width, actor.paintBounds.height];
        const b = position.model.capture.footprint;
        const left = Math.min(0, b[0]), top = Math.min(0, b[1]);
        return [left, top, Math.max(actorWidth, b[0] + b[2]) - left, Math.max(actorHeight, b[1] + b[3]) - top];
    }
    property real surfaceLeft: Math.max(0, Math.min(actorX + surfaceActorBounds[0], bubbleVisible ? bubbleX - 8 : actorX + surfaceActorBounds[0]) - 8)
    property real surfaceTop: Math.max(0, Math.min(actorY + surfaceActorBounds[1], bubbleVisible ? bubbleY : actorY + surfaceActorBounds[1]) - 8)
    property real surfaceRight: Math.max(actorX + surfaceActorBounds[0] + surfaceActorBounds[2], bubbleVisible ? bubbleX + bubbleWidth + 8 : actorX + surfaceActorBounds[0] + surfaceActorBounds[2]) + 8
    property real surfaceBottom: Math.max(actorY + surfaceActorBounds[1] + surfaceActorBounds[3], bubbleVisible ? bubbleY + bubble.height : actorY + surfaceActorBounds[1] + surfaceActorBounds[3]) + 8
    property string bubbleText: noticeText || partial || (snapshot.notice?.text || latestReply() || "What's on your mind?")
    property bool pointerValid: false
    property real pointerX: 0
    property real pointerY: 0
    property real pointerAt: 0
    property real pointerMovedAt: 0
    property real lastPursuitAt: -100000
    property int pointerSamples: 0
    property bool pointerEnabled: !actor.recovering && !actor.reviewing && !presentationPaused && !bubbleVisible && !hovered && !position.captured && !busy && !profile.quiet && !profile.reduced_motion && !profile.pinned && profile.follow !== false
    function losePointer(retreatIfActive) {
        var wasValid = pointerValid;
        pointerValid = false;
        pointerApproach.stop();
        pointerRetreat.stop();
        if (wasValid && retreatIfActive && pointerEnabled)
            retreat();
    }
    function observePointer(line) {
        try {
            var p = JSON.parse(line);
            pointerSamples++;
            var local = p.valid === true && currentScreen ? Pointer.localPoint(p, currentScreen.name, currentScreen.width, currentScreen.height) : null;
            if (!local) {
                losePointer(true);
                return;
            }
            var x = local[0], y = local[1];
            var moved = pointerValid && (Math.abs(x - pointerX) + Math.abs(y - pointerY) > 9);
            pointerX = x;
            pointerY = y;
            pointerAt = Date.now();
            pointerValid = true;
            if (moved)
                pointerMovedAt = pointerAt;
            // Looking/leaning precedes one bounded approach, never a permanent chase.
            if (moved && pointerAt - lastPursuitAt > 18000 && pointerEnabled && !travel.running) {
                lastPursuitAt = pointerAt;
                actor.play("cursor_gaze");
                pointerApproach.restart();
            }
        } catch (error) {
            losePointer(true);
        }
    }
    Process {
        id: pointerReader
        command: [Quickshell.env("CAPRI_PYTHON"), "-B", "-m", "capri.pointer"]
        running: root.pointerEnabled
        stdout: SplitParser {
            onRead: data => root.observePointer(data)
        }
        onRunningChanged: if (!running)
            root.losePointer(false)
    }
    property var gestureReader: null
    Component {
        id: gestureReaderComponent
        Process {
            property int gestureEpoch
            stdinEnabled: true
            command: [Quickshell.env("CAPRI_PYTHON"), "-B", "-m", "capri.pointer", "--gesture", String(gestureEpoch)]
            running: true
            stdout: SplitParser {
                onRead: data => {
                    if (!position.captured || position.epoch !== gestureEpoch)
                        return;
                    try {
                        position.sample(JSON.parse(data));
                    } catch (error) {
                        position.end("invalid-pointer", true);
                    }
                }
            }
            onExited: {
                if (position.captured && position.epoch === gestureEpoch)
                    position.end("pointer-exited", true);
                destroy();
            }
        }
    }
    Timer {
        interval: 4500
        running: actor.recovering
        onTriggered: {
            actor.recovering = false;
            actor.scheduleRest();
        }
    }
    Timer {
        interval: 50
        running: position.releasePending
        onTriggered: position.end("release-timeout", true)
    }
    Component.onDestruction: position.end("shutdown", true)
    Timer {
        interval: 300
        running: position.captured && !position.model.capture?.frame
        onTriggered: position.end("pointer-timeout", true)
    }
    Timer {
        id: pointerApproach
        interval: 1100
        onTriggered: {
            if (!root.pointerEnabled || !root.pointerValid || Date.now() - root.pointerMovedAt > 2500)
                return;
            var bodyX = root.actorX + actor.bounds.x + actor.bounds.width / 2, bodyY = root.actorY + actor.bounds.y + actor.bounds.height / 2;
            var dx = root.pointerX - bodyX, dy = root.pointerY - bodyY, d = Math.hypot(dx, dy);
            var clearance = Pointer.safeDistance(actor.bounds);
            if (d < clearance || d > 900)
                return;
            actor.play("pointer_stalk");
            var step = Math.min(120, d - clearance);
            travel.toX = root.actorX + dx / d * step;
            travel.toY = root.actorY + dy / d * step;
            travel.restart();
            pointerRetreat.restart();
        }
    }
    Timer {
        id: pointerRetreat
        interval: 7200
        onTriggered: if (root.pointerEnabled) {
            actor.play("snooze_retreat");
            root.retreat();
        }
    }
    Timer {
        interval: 1000
        repeat: true
        running: root.pointerValid
        onTriggered: if (Date.now() - root.pointerAt > 3200) {
            root.losePointer(true);
        }
    }
    signal focusQuick
    signal focusConversation
    Settings {
        id: placement
        location: Quickshell.env("CAPRI_SETTINGS")
        property string output: ""
        property real actorX: 100
        property real actorY: 420
    }
    PositionController {
        id: position
        Component.onCompleted: place(placement.actorX, placement.actorY, "restore")
        onReleaseRequested: {
            if (root.gestureReader)
                root.gestureReader.write("release\n");
        }
        onCaptureStarted: epoch => {
            actor.recovering = false;
            root.gestureReader = gestureReaderComponent.createObject(root, {
                gestureEpoch: epoch
            });
            travel.stop();
            pointerApproach.stop();
            pointerRetreat.stop();
            root.losePointer(false);
        }
        onCaptureEnding: moved => actor.recovering = moved
        onCaptureEnded: (epoch, moved, reason) => {
            if (root.gestureReader) {
                root.gestureReader.running = false;
                root.gestureReader = null;
            }
            drag.moved = moved || reason !== "release";
            if (reason !== "release") {
                drag.enabled = false;
                Qt.callLater(() => drag.enabled = true);
            }
            root.dragTrace("end", {
                epoch: epoch,
                moved: moved,
                reason: reason
            });
            if (["output-change", "output-changed", "output-unavailable"].includes(reason)) {
                root.abortRecovery();
                root.resyncPlacement();
            } else if (moved)
                Qt.callLater(() => {
                    if (!position.captured && !root.presentationPaused)
                        actor.play("drag_release_recover");
                    else
                        actor.recovering = false;
                });
        }
        onCommitRequested: (output, reason) => {
            if (root.currentScreen?.name === output)
                root.savePlacement();
        }
        onDiagnostic: (event, data) => root.dragTrace(event, data)
    }
    function dragTrace(event, data) {
        if (Quickshell.env("CAPRI_DRAG_TRACE") !== "1")
            return;
        console.warn("CAPRI_DRAG " + JSON.stringify(Object.assign({
            kind: event,
            wall_ms: Date.now(),
            anchor: [actorX, actorY],
            epoch: position.epoch,
            writer: position.model.writer,
            captured: position.captured,
            dragging: dragging,
            pressed: drag.pressed,
            clip: actor.clipId,
            travel: travel.running,
            output: currentScreen?.name,
            dpr: currentScreen?.devicePixelRatio,
            logicalOutput: [currentScreen?.width, currentScreen?.height],
            surface: [surfaceLeft, surfaceTop, panel.width, panel.height],
            bounds: [actor.bounds.x, actor.bounds.y, actor.bounds.width, actor.bounds.height],
            saves: position.gestureSaves
        }, data)));
    }
    FontLoader {
        source: "file://" + root.assets + "/fonts/Inter/Inter-Variable.ttf"
    }
    FontLoader {
        source: "file://" + root.assets + "/fonts/Manrope/Manrope-Variable.ttf"
    }
    function clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v));
    }
    function latestReply() {
        const h = snapshot.history || [];
        for (let i = h.length - 1; i >= 0; i--)
            if (h[i].role === "assistant")
                return h[i].text;
        return "";
    }
    function send(method, args) {
        if (!socket.connected) {
            noticeText = "Core disconnected; reconnect before requesting work.";
            return 0;
        }
        sequence++;
        socket.write(JSON.stringify({
            method: method,
            seq: sequence,
            args: args
        }) + "\n");
        socket.flush();
        return sequence;
    }
    function preference(key, value) {
        let c = {};
        c[key] = value;
        send("preferences", {
            changes: c
        });
    }
    function editDraft(text) {
        draftLocal = text;
        draftSave.restart();
    }
    function flushDraft() {
        draftSave.stop();
        if (draftLoaded)
            send("draft", {
                text: draftLocal
            });
    }
    function submitDraft() {
        if (!draftLocal.trim() || busy)
            return;
        flushDraft();
        pendingText = draftLocal;
        pendingSubmit = send("submit", {
            text: draftLocal,
            mode: ["chat", "work", "command"][inputModeIndex]
        });
        noticeText = "";
        bubbleOpen = true;
    }
    function command(text) {
        flushDraft();
        send("submit", {
            text: text,
            mode: "command"
        });
    }
    function stop() {
        send("stop", {});
        noticeText = "Stopped.";
        partial = "";
        bubbleOpen = true;
    }
    function dismiss() {
        flushDraft();
        bubbleOpen = false;
        replyOpen = false;
        noticeText = "";
        whyOpen = false;
        if (noticeActive)
            send("dismiss_notice", {});
    }
    function openReply() {
        hidden = false;
        bubbleOpen = true;
        replyOpen = true;
        Qt.callLater(() => focusQuick());
    }
    function openConversation() {
        flushDraft();
        settingsOpen = false;
        hidden = false;
        conversationOpen = true;
        replyOpen = false;
        Qt.callLater(() => focusConversation());
    }
    function openMotionReview() {
        flushDraft();
        conversationOpen = false;
        replyOpen = false;
        bubbleOpen = false;
        hidden = false;
        motionReviewOpen = true;
        actor.review("upright_hover", 0, true);
    }
    function inputKey(event) {
        if (event.key === Qt.Key_Escape) {
            flushDraft();
            replyOpen = false;
            conversationOpen = false;
            bubbleOpen = false;
            event.accepted = true;
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            const shift = !!(event.modifiers & Qt.ShiftModifier), ctrl = !!(event.modifiers & Qt.ControlModifier);
            if (!shift && ((!profile.send_with_ctrl && !ctrl) || (profile.send_with_ctrl && ctrl))) {
                submitDraft();
                event.accepted = true;
            }
        }
    }
    function keepOnScreen() {
        if (!currentScreen || position.captured || actor.recovering)
            return;
        var b = actor.paintBounds;
        position.place(PositionAxis.axis(actorX, 8 - b.x, currentScreen.width - b.x - b.width - 8), PositionAxis.axis(actorY, 8 - b.y, currentScreen.height - b.y - b.height - 8), "bounds");
    }
    function savePlacement() {
        if (position.captured || !currentScreen)
            return;
        placement.actorX = actorX;
        placement.actorY = actorY;
        placement.output = currentScreen ? currentScreen.name : "";
    }
    function abortRecovery() {
        if (actor.recovering) {
            actor.recovering = false;
            actor.freeze();
        }
    }
    function resyncPlacement() {
        Qt.callLater(() => {
            if (!position.captured) {
                root.abortRecovery();
                keepOnScreen();
                savePlacement();
            }
        });
    }
    Connections {
        target: root.currentScreen
        function onWidthChanged() {
            position.end("output-changed", false);
            root.resyncPlacement();
        }
        function onHeightChanged() {
            position.end("output-changed", false);
            root.resyncPlacement();
        }
    }
    function chooseOutput(name) {
        position.end("output-change", false);
        travel.stop();
        abortRecovery();
        selectedOutput = name;
        placement.output = name;
        resyncPlacement();
    }
    function retreat() {
        if (position.captured)
            return;
        travel.stop();
        if (!currentScreen)
            return;
        travel.toX = actorX < currentScreen.width / 2 ? 16 : currentScreen.width - actorWidth - 16;
        travel.toY = clamp(actorY, 16, currentScreen.height - actorHeight - 16);
        travel.restart();
    }
    onCurrentScreenChanged: {
        position.end("output-change", false);
        abortRecovery();
        losePointer(false);
        resyncPlacement();
    }
    onProfileChanged: if (profile.pinned || profile.quiet || profile.reduced_motion) {
        travel.stop();
        pointerApproach.stop();
        pointerRetreat.stop();
    }
    onActorWidthChanged: keepOnScreen()
    onActorHeightChanged: keepOnScreen()
    onPresentationPausedChanged: if (presentationPaused) {
        position.end(snapshot.locked ? "lock" : "hidden", true);
        travel.stop();
        flushDraft();
    }
    onReplyOpenChanged: if (replyOpen)
        travel.stop()
    onHoveredChanged: if (hovered)
        travel.stop()
    Timer {
        id: draftSave
        interval: 250
        onTriggered: root.flushDraft()
    }
    Socket {
        id: socket
        path: Quickshell.env("CAPRI_SOCKET")
        connected: true
        onConnectionStateChanged: {
            if (connected) {
                root.sequence = 0;
                root.renderReported = false;
                write(JSON.stringify({
                    version: 1,
                    role: "shell",
                    token: Quickshell.env("CAPRI_UI_TOKEN")
                }) + "\n");
                flush();
            } else {
                position.end("disconnect", true);
                root.snapshot = Object.assign({}, root.snapshot, {
                    locked: true
                });
                root.noticeText = "Core disconnected. Work stopped.";
            }
        }
        parser: SplitParser {
            onRead: data => {
                try {
                    const m = JSON.parse(data);
                    if (m.event === "snapshot") {
                        const old = root.lastReply;
                        if (m.notice && m.notice.id !== root.snapshot.notice?.id)
                            root.noticeText = "";
                        root.snapshot = m;
                        if (!root.draftLoaded || root.draftPartition !== m.partition) {
                            root.draftLocal = m.draft || "";
                            root.draftPartition = m.partition || "";
                            root.draftLoaded = true;
                        }
                        const replies = (m.history || []).filter(r => r.role === "assistant");
                        root.lastReply = replies.length ? replies[replies.length - 1].id : 0;
                        if (root.receivedSnapshot && root.lastReply !== old) {
                            root.partial = "";
                            root.bubbleOpen = true;
                        }
                        root.receivedSnapshot = true;
                    } else if (m.event === "delta") {
                        root.partial = m.text;
                        root.bubbleOpen = true;
                    } else if (m.event === "requestAccepted") {
                        if (m.seq === root.pendingSubmit && root.draftLocal === root.pendingText) {
                            root.draftLocal = "";
                            root.flushDraft();
                        }
                        root.pendingSubmit = 0;
                    } else if (m.event === "notice" || m.event === "denied") {
                        root.noticeText = m.text;
                        root.bubbleOpen = true;
                    } else if (m.event === "hide") {
                        root.flushDraft();
                        root.hidden = true;
                        root.replyOpen = false;
                        root.conversationOpen = false;
                    } else if (m.event === "summon") {
                        root.openReply();
                    } else if (m.event === "prepareQuit") {
                        root.flushDraft();
                        root.send("ui_quit_ready", {});
                    } else if (m.event === "quit") {
                        root.flushDraft();
                        Quickshell.quit();
                    }
                } catch (e) {
                    root.noticeText = "Invalid core message. Stop and reconnect.";
                    root.send("stop", {});
                }
            }
        }
    }
    Timer {
        interval: 1000
        repeat: true
        running: socket.connected
        onTriggered: {
            root.send("heartbeat", {});
            if (!root.renderReported && actor.ready && root.draftLoaded) {
                root.send("render_ready", {
                    ready: true,
                    drafts: true
                });
                root.renderReported = true;
            }
            root.send("attention", {
                fullscreen: root.attentionFullscreen,
                hidden: root.hidden
            });
        }
    }
    Timer {
        interval: 1000
        repeat: true
        running: !socket.connected
        onTriggered: socket.connected = true
    }
    Timer {
        interval: 88000
        repeat: true
        running: !actor.recovering && !actor.reviewing && !root.presentationPaused && !root.replyOpen && !root.conversationOpen && !position.captured && !root.hovered && !root.profile.pinned && !root.profile.quiet && root.profile.roam !== false && !root.busy && root.snapshot.input_idle === true
        onTriggered: {
            travel.toX = root.actorX < root.currentScreen.width / 2 ? 16 : root.currentScreen.width - root.actorWidth - 16;
            travel.toY = root.clamp(root.actorY + (root.actorY > root.currentScreen.height / 2 ? -180 : 180), 16, root.currentScreen.height - root.actorHeight - 16);
            travel.restart();
        }
    }
    ParallelAnimation {
        id: travel
        property real toX: 0
        property real toY: 0
        NumberAnimation {
            target: position
            property: "travelX"
            to: travel.toX
            duration: 1400
            easing.type: Easing.InOutCubic
        }
        NumberAnimation {
            target: position
            property: "travelY"
            to: travel.toY
            duration: 1400
            easing.type: Easing.InOutCubic
        }
        onStarted: if (!position.prepareTravel())
            stop()
        onRunningChanged: if (!running)
            position.traveling = false
        onFinished: if (!position.captured && position.travelEpoch === position.model.epoch)
            root.savePlacement()
    }
    FileView {
        path: root.assets + "/input-regions.json"
        onLoaded: root.hitRects = JSON.parse(text())
    }
    Loader {
        id: stageLoader
        active: Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1"
        sourceComponent: TestStage {
            output: root.currentScreen
            lowered: root.conversationOpen
        }
    }
    PanelWindow {
        id: panel
        screen: root.currentScreen
        visible: !root.presentationPaused
        anchors {
            left: true
            top: true
        }
        margins {
            left: Math.round(root.surfaceLeft)
            top: Math.round(root.surfaceTop)
        }
        implicitWidth: Math.ceil(root.surfaceRight - root.surfaceLeft)
        implicitHeight: Math.ceil(root.surfaceBottom - root.surfaceTop)
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "capri-v2-presence"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: root.replyOpen ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
        mask: Region {
            id: inputMask
            Region {
                item: bubble
                intersection: bubble.visible ? Intersection.Combine : Intersection.Subtract
            }
            // This bounded canvas includes the captured pointer at clamped edges.
            // Idle immediately returns to the live alpha input regions below.
            Region {
                x: actor.x + root.surfaceActorBounds[0]
                y: actor.y + root.surfaceActorBounds[1]
                width: position.captured ? root.surfaceActorBounds[2] : 0
                height: position.captured ? root.surfaceActorBounds[3] : 0
            }
            Region {
                item: stopButton
                intersection: stopButton.visible ? Intersection.Combine : Intersection.Subtract
            }
        }
        Instantiator {
            model: actor.regionData
            delegate: Region {
                required property var modelData
                property var geometry: actor.mapRegion(modelData)
                x: actor.x + geometry[0]
                y: actor.y + geometry[1]
                width: geometry[2]
                height: geometry[3]
            }
            onObjectAdded: (index, object) => inputMask.regions.push(object)
            onObjectRemoved: (index, object) => inputMask.regions = inputMask.regions.filter(v => v !== object)
        }
        Canvas {
            id: speechTail
            visible: bubble.visible
            property real tipX: root.actorX + actor.mouth.x - root.surfaceLeft
            property real tipY: root.actorY + actor.mouth.y - root.surfaceTop
            property real baseX: bubble.x + (root.bubbleLeft ? bubble.width : 0)
            property real baseY: root.clamp(tipY, bubble.y + 24, bubble.y + bubble.height - 24)
            x: Math.min(tipX, baseX) - 2
            y: Math.min(tipY, baseY - 7) - 2
            width: Math.abs(baseX - tipX) + 4
            height: Math.abs(baseY - tipY) + 18
            onTipXChanged: requestPaint()
            onTipYChanged: requestPaint()
            onBaseXChanged: requestPaint()
            onBaseYChanged: requestPaint()
            onVisibleChanged: if (visible)
                requestPaint()
            onPaint: {
                const c = getContext("2d");
                c.reset();
                c.fillStyle = Theme.surface;
                c.strokeStyle = Theme.outline;
                c.lineWidth = 1;
                c.beginPath();
                c.moveTo(tipX - x, tipY - y);
                c.lineTo(baseX - x, baseY - y - 7);
                c.lineTo(baseX - x, baseY - y + 7);
                c.closePath();
                c.fill();
                c.stroke();
            }
        }
        Actor {
            id: actor
            assets: root.assets
            x: root.actorX - root.surfaceLeft
            y: root.actorY - root.surfaceTop
            width: root.actorWidth
            height: root.actorHeight
            state: root.dragging ? "dragged" : root.snapshot.state === "idle" ? (root.replyOpen ? "listening" : root.idleState) : root.snapshot.state
            reading: root.bubbleVisible
            pinned: !!root.profile.pinned
            ownerInteracting: root.hovered || position.captured
            grabbed: position.captured
            pointerValid: root.pointerValid
            pointerTarget: Qt.point(root.pointerX - root.actorX, root.pointerY - root.actorY)
            onClipStarted: root.keepOnScreen()
            onClipFinished: name => {
                if (recovering && name === "drag_release_recover") {
                    recovering = false;
                    scheduleRest();
                }
            }
            paused: root.presentationPaused
            reduced: !!root.profile.reduced_motion || !!root.profile.quiet
            MouseArea {
                id: drag
                x: position.model.capture ? position.model.capture.hit[0] : actor.bounds.x
                y: position.model.capture ? position.model.capture.hit[1] : actor.bounds.y
                width: position.model.capture ? position.model.capture.hit[2] : actor.bounds.width
                height: position.model.capture ? position.model.capture.hit[3] : actor.bounds.height
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                hoverEnabled: true
                property bool moved: false
                onEntered: root.hovered = true
                onExited: root.hovered = false
                onPressed: mouse => {
                    moved = false;
                    if (mouse.button !== Qt.LeftButton || !root.currentScreen)
                        return;
                    const local = actor.mapFromItem(drag, mouse.x, mouse.y), b = actor.bounds;
                    if (!position.begin(root.currentScreen.name, root.currentScreen.width, root.currentScreen.height, actor.grabFootprint(), [local.x, local.y], root.actorHeight, [b.x, b.y, b.width, b.height]))
                        moved = true;
                    root.dragTrace("press", {
                        accepted: position.captured
                    });
                }
                onReleased: mouse => {
                    if (mouse.button !== Qt.LeftButton || !position.captured)
                        return;
                    moved = position.model.moved;
                    position.release();
                }
                onCanceled: {
                    moved = true;
                    position.end("cancel", true);
                }
                onClicked: mouse => {
                    if (moved)
                        return;
                    if (mouse.button === Qt.RightButton) {
                        root.openConversation();
                        root.settingsOpen = true;
                    } else
                        root.replyOpen ? root.dismiss() : root.openReply();
                }
                onDoubleClicked: if (!moved)
                    root.openConversation()
            }
        }
        Bubble {
            id: bubble
            owner: root
            width: root.bubbleWidth
            visible: root.bubbleVisible
            x: root.bubbleX - root.surfaceLeft
            y: root.bubbleY - root.surfaceTop
            tailRight: root.bubbleLeft
            anchorY: root.mouthY - root.bubbleY
        }
        CapriButton {
            id: stopButton
            visible: root.busy && !bubble.visible
            text: "Stop"
            x: actor.x + actor.width / 2 - width / 2
            y: actor.y + actor.height - height
            onClicked: root.stop()
        }
    }
    Loader {
        id: conversationLoader
        // Draft and transcript live in the root/core, so a closed window need not stay resident.
        active: root.conversationOpen
        onLoaded: Qt.callLater(() => root.focusConversation())
        sourceComponent: Conversation {
            owner: root
        }
    }
    Loader {
        active: root.motionReviewOpen
        sourceComponent: MotionReview {
            owner: root
            actor: root.character
        }
    }
    IpcHandler {
        target: "capri"
        function summon(): void {
            root.openReply();
        }
        function hide(): void {
            root.flushDraft();
            root.hidden = true;
            root.replyOpen = false;
            root.conversationOpen = false;
        }
        function stop(): void {
            root.stop();
        }
        function quit(): void {
            root.flushDraft();
            root.send("quit", {});
        }
        function conversation(): void {
            root.settingsOpen = false;
            root.openConversation();
        }
        function revealTextSize(): void {
            if (Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1" && conversationLoader.item)
                conversationLoader.item.revealTextSize();
        }
        function uiPoints(): string {
            return Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1" && conversationLoader.item ? conversationLoader.item.reviewPoints() : "{}";
        }
        function uiState(): string {
            return Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1" && conversationLoader.item ? conversationLoader.item.reviewState() : "{}";
        }
        function settings(): void {
            root.openConversation();
            root.settingsOpen = true;
        }
        function revealScope(): void {
            if (Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1")
                if (conversationLoader.item)
                    conversationLoader.item.revealScope();
        }
        function revealScopeSave(): void {
            if (Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1")
                if (conversationLoader.item)
                    conversationLoader.item.revealScopeSave();
        }
        function transcriptMetrics(): string {
            return Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1" && conversationLoader.item ? conversationLoader.item.transcriptMetrics() : "{}";
        }
        function scopePoints(): string {
            return Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1" ? (conversationLoader.item ? conversationLoader.item.scopePoints() : "{}") : "{}";
        }
        function presence(): void {
            root.replyOpen = false;
            root.bubbleOpen = false;
            root.conversationOpen = false;
            root.hidden = false;
        }
        function reviewClip(name: string, time: int, paused: bool): bool {
            return Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1" ? actor.review(name, time, paused) : false;
        }
        function reviewTransition(name: string): bool {
            if (Quickshell.env("CAPRI_EVIDENCE_STAGE") !== "1")
                return false;
            actor.reviewing = true;
            actor.reviewPaused = false;
            return actor.play(name);
        }
        function endReview(): void {
            if (Quickshell.env("CAPRI_EVIDENCE_STAGE") === "1")
                actor.endReview();
        }
        function motionStatus(): string {
            return JSON.stringify({
                clip: actor.clipId,
                emotion: actor.emotion,
                time: actor.clock,
                moving: actor.moving,
                ready: actor.ready,
                regions: actor.regionData.length,
                bounds: actor.bounds,
                paintBounds: actor.paintBounds,
                handover: actor.handover,
                implemented: actor.catalog.filter(c => c.asset_status === "AVAILABLE").length,
                pointerEnabled: root.pointerEnabled,
                pointerValid: root.pointerValid,
                pointerSamples: root.pointerSamples
            });
        }
        function dragDiagnostic(): string {
            return Quickshell.env("CAPRI_DRAG_TRACE") === "1" ? JSON.stringify({
                pressed: drag.pressed,
                dragging: root.dragging,
                captured: position.captured,
                epoch: position.epoch,
                writer: position.model.writer,
                hidden: root.hidden,
                replyOpen: root.replyOpen,
                conversationOpen: root.conversationOpen,
                settingsOpen: root.settingsOpen,
                anchor: [root.actorX, root.actorY],
                clip: actor.clipId,
                reviewing: actor.reviewing,
                saves: position.gestureSaves,
                surface: [root.surfaceLeft, root.surfaceTop, panel.width, panel.height]
            }) : "{}";
        }
        function dragTestPoint(): string {
            if (Quickshell.env("CAPRI_EVIDENCE_STAGE") !== "1")
                return "{}";
            const regions = actor.regionData.filter(r => r.tag === 1).map(r => actor.mapRegion(r)).sort((a, b) => b[2] * b[3] - a[2] * a[3]);
            const b = regions[0];
            return JSON.stringify({
                x: root.actorX + b[0] + b[2] / 2,
                y: root.actorY + b[1] + b[3] / 2,
                anchor: [root.actorX, root.actorY],
                actor: [actor.width, actor.height],
                bounds: [actor.bounds.x, actor.bounds.y, actor.bounds.width, actor.bounds.height]
            });
        }
        function actorGeometry(): string {
            return JSON.stringify({
                x: root.actorX,
                y: root.actorY,
                width: root.actorWidth,
                height: root.actorHeight,
                output: root.currentScreen?.name
            });
        }
        function renderStatus(): string {
            return JSON.stringify({
                ready: actor.ready,
                visible: panel.visible,
                output: root.currentScreen?.name,
                width: panel.width,
                height: panel.height,
                namespace: "capri-v2-presence"
            });
        }
        function inputPoint(): string {
            const p = bubble.inputPoint();
            return Math.round(root.bubbleX + p.x) + "," + Math.round(root.bubbleY + p.y);
        }
        function modePoint(): string {
            const p = bubble.modePoint();
            return Math.round(root.bubbleX + p.x) + "," + Math.round(root.bubbleY + p.y);
        }
        function conversationPoint(): string {
            const p = bubble.conversationPoint();
            return Math.round(root.bubbleX + p.x) + "," + Math.round(root.bubbleY + p.y);
        }
        function entryFocused(): bool {
            return bubble.entryFocused();
        }
        function backgroundFocused(): bool {
            return stageLoader.item ? stageLoader.item.fieldFocused : false;
        }
        function backgroundLength(): int {
            return stageLoader.item ? stageLoader.item.fieldLength : 0;
        }
        function inputMode(): string {
            return ["chat", "work", "command"][root.inputModeIndex];
        }
        function placement(x: int, y: int): void {
            travel.stop();
            if (position.captured)
                return;
            root.abortRecovery();
            if (!position.place(x, y, "ipc"))
                return;
            root.keepOnScreen();
            root.savePlacement();
        }
        function output(name: string): void {
            root.chooseOutput(name);
        }
        function size(pixels: int): void {
            root.preference("character_size", root.clamp(pixels, 160, 420));
        }
        function quiet(value: bool): void {
            root.preference("quiet", value);
        }
        function pose(name: string): void {
            if (["idle", "curious", "listening", "thinking", "working", "success", "blocked"].includes(name))
                root.idleState = name;
        }
    }
}
