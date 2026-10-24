import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: settings
    required property var owner
    function scopePoints() {
        return JSON.stringify({root: rootInput.mapToGlobal(rootInput.width/2,rootInput.height/2), save: scopeSave.mapToGlobal(scopeSave.width/2,scopeSave.height/2), viewport: settings.mapToGlobal(0,0), viewportHeight:settings.height, contentY:contentItem.contentY, rootLength: rootInput.text.length, rootFocused:rootInput.activeFocus});
    }
    function revealScopeSave() { rootInput.focus=false; contentItem.cancelFlick(); contentItem.contentY = Math.max(0,scopeSave.mapToItem(settingsColumn,0,0).y - 90); }
    function revealScope() { contentItem.contentY = Math.max(0,rootInput.y - 4); }
    property bool scopeDirty: false
    Connections {
        target: owner
        function onSnapshotChanged() {
            if (!settings.scopeDirty) {
                rootInput.text=(owner.snapshot.scope?.roots || []).join("\n");
                desktopScope.checked=owner.snapshot.scope?.desktop || false;
            }
        }
    }
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        id: settingsColumn
        width: settings.availableWidth
        spacing: 10
        Text {
            text: "Presence and attention"
            color: "#efedf2"
            font.pixelSize: 17
        }
        Flow {
            Layout.fillWidth: true
            spacing: 12
            CheckBox {
                text: "Quiet"
                checked: owner.profile.quiet || false
                onToggled: owner.preference("quiet", checked)
            }
            CheckBox {
                text: "Pinned"
                checked: owner.profile.pinned || false
                onToggled: owner.preference("pinned", checked)
            }
            CheckBox {
                text: "Reduced motion"
                checked: owner.profile.reduced_motion || false
                onToggled: owner.preference("reduced_motion", checked)
            }
            CheckBox {
                text: "Do not disturb"
                checked: owner.profile.dnd || false
                onToggled: owner.preference("dnd", checked)
            }
            CheckBox {
                text: "Pause observation and tasks"
                checked: owner.profile.paused || false
                onToggled: owner.preference("paused", checked)
            }
            CheckBox {
                text: "Initiative"
                checked: owner.profile.initiative ?? true
                onToggled: owner.preference("initiative", checked)
            }
            CheckBox {
                text: "Mute sounds"
                checked: owner.profile.mute || false
                onToggled: owner.preference("mute", checked)
            }
            CheckBox {
                text: "Ctrl+Enter sends"
                checked: owner.profile.send_with_ctrl || false
                onToggled: owner.preference("send_with_ctrl", checked)
            }
        }
        RowLayout {
            Text {
                text: "Size"
                color: "#bdb4c6"
            }
            Slider {
                from: 160
                to: 420
                stepSize: 10
                value: owner.profile.character_size || 280
                onMoved: owner.preference("character_size", Math.round(value))
                Layout.fillWidth: true
                Accessible.name: "Character size"
            }
            Text {
                text: "Sound"
                color: "#bdb4c6"
            }
            Slider {
                from: 0
                to: 100
                stepSize: 5
                value: owner.profile.sound_volume ?? 15
                onMoved: owner.preference("sound_volume", Math.round(value))
                Layout.fillWidth: true
                Accessible.name: "Notification sound volume"
            }
            CapriButton {
                text: "Test sound"
                onClicked: owner.send("test_sound", {})
            }
        }
        RowLayout {
            Text {
                text: "Output"
                color: "#bdb4c6"
            }
            CapriComboBox {
                model: owner.outputNames
                currentIndex: Math.max(0, owner.outputNames.indexOf(owner.selectedOutput))
                onActivated: owner.chooseOutput(currentText)
                Layout.fillWidth: true
            }
            CapriButton {
                text: "Snooze 3 hours"
                onClicked: owner.send("snooze", {
                    minutes: 180
                })
            }
            CapriButton {
                text: "Stop shortcut…"
                onClicked: owner.send("shortcut_setup", {})
            }
        }
        RowLayout {
            Text {
                text: "Check-in gap (minutes)"
                color: "#bdb4c6"
            }
            SpinBox {
                from: 15
                to: 240
                value: owner.profile.min_gap_minutes || 45
                onValueModified: owner.preference("min_gap_minutes", value)
            }
            SpinBox {
                from: 30
                to: 480
                value: owner.profile.max_gap_minutes || 120
                onValueModified: owner.preference("max_gap_minutes", value)
            }
            Text {
                text: "Quiet hours"
                color: "#bdb4c6"
            }
            TextField {
                id: quietStart
                placeholderText: "HH:MM"
                Component.onCompleted: text = owner.profile.quiet_start || ""
                maximumLength: 5
                implicitWidth: 75
            }
            TextField {
                id: quietEnd
                placeholderText: "HH:MM"
                Component.onCompleted: text = owner.profile.quiet_end || ""
                maximumLength: 5
                implicitWidth: 75
            }
            CapriButton {
                text: "Save"
                onClicked: owner.send("preferences", {
                    changes: {
                        timezone: timezoneInput.text,
                        quiet_start: quietStart.text,
                        quiet_end: quietEnd.text
                    }
                })
            }
        }
        TextField {
            id: timezoneInput
            placeholderText: "IANA timezone, e.g. America/Edmonton"
            Component.onCompleted: text = owner.profile.timezone || "America/Edmonton"
            Layout.fillWidth: true
            Accessible.name: "Quiet hours timezone"
        }
        Text {
            text: "Account and model"
            color: "#efedf2"
            font.pixelSize: 17
        }
        RowLayout {
            CapriButton {
                text: "Continue with ChatGPT"
                onClicked: owner.command("/signin")
            }
            CapriComboBox {
                model: owner.snapshot.models || []
                textRole: "name"
                valueRole: "id"
                currentIndex: Math.max(0,(owner.snapshot.models || []).findIndex(m => m.id === owner.snapshot.model))
                Layout.fillWidth: true
                onActivated: owner.command("/model " + currentValue)
                Accessible.name: "Discovered ChatGPT account model"
            }
            CapriButton {
                text: "Refresh models"
                onClicked: owner.command("/models")
            }
            CapriButton {
                text: "Sign out"
                onClicked: owner.command("/logout")
            }
        }
        Text {
            text: "Work scope and observed projects"
            color: "#efedf2"
            font.pixelSize: 17
        }
        Text {
            text: "Choose exact project roots. Observation stays local unless you explicitly allow selected excerpts. Work tasks cannot access credentials or Capri's live authority/update files."
            color: "#a5a2af"
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 12
        }
        TextArea {
            id: rootInput
            placeholderText: "/absolute/project — one exact directory per line"
            Component.onCompleted: text = (owner.snapshot.scope?.roots || []).join("\n")
            onTextChanged: if (activeFocus) settings.scopeDirty = true
            Layout.fillWidth: true
            Layout.preferredHeight: 75
            color: "#efedf2"
            textFormat: TextEdit.PlainText
            Accessible.name: "Selected project roots"
            background: Rectangle { color: "#111219"; radius: 6 }
        }
        CheckBox {
            id: desktopScope
            text: "Allow typed application, window, media and volume actions for requested Tasks"
            Component.onCompleted: checked = owner.snapshot.scope?.desktop || false
            onToggled: settings.scopeDirty = true
        }
        Text {
            text: "Sending a Task authorizes edits and tests within these folders for up to 30 minutes / 64 actions. Selected file contents and task results may be sent to your selected ChatGPT model. Network and general GUI input remain unavailable. Stop revokes the task."
            color: "#a5a2af"; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12
        }
        RowLayout {
            CapriButton {
                id: scopeSave
                text: "Use for work"
                onClicked: {
                    owner.send("set_scope", {
                        roots: rootInput.text.split("\n").map(x => x.trim()).filter(x => x.length),
                        desktop: desktopScope.checked
                    });
                    settings.scopeDirty = false;
                }
            }
            CapriButton {
                text: "Observe locally"
                onClicked: owner.send("observe_project", {
                    root: rootInput.text,
                    cloud: false
                })
            }
            CapriButton {
                text: "Allow event metadata to model"
                onClicked: owner.send("observe_project", {
                    root: rootInput.text,
                    cloud: true
                })
            }
        }
        Text {
            text: owner.snapshot.sources_text || "No selected project observation."
            color: "#a5a2af"
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 12
        }
        Repeater {
            model: owner.snapshot.observation_sources || []
            delegate: RowLayout {
                required property var modelData
                Text { text: modelData.root; color: "#c5bfcc"; textFormat: Text.PlainText; wrapMode: Text.Wrap; Layout.fillWidth: true }
                CapriButton { text: "Stop observing"; onClicked: owner.send("unobserve_project",{root:modelData.root}) }
            }
        }
        Text { text: "Recent tasks"; color: "#efedf2"; font.pixelSize: 17 }
        Repeater {
            model: owner.snapshot.tasks || []
            delegate: RowLayout {
                required property var modelData
                Text { text: modelData.status + " · " + modelData.objective; textFormat: Text.PlainText; color: "#c5bfcc"; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; Layout.fillWidth: true }
                CapriButton { text: "Resume"; enabled: !owner.busy && modelData.status !== "running"; onClicked: owner.send("resume_task",{id:modelData.id}) }
            }
        }
        Text { text: "Recent verified activity"; color: "#efedf2"; font.pixelSize: 17 }
        Repeater {
            model: owner.snapshot.activity || []
            delegate: Text { required property var modelData; text: modelData.kind + " · " + modelData.detail; textFormat: Text.PlainText; color: "#a5a2af"; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
        }
        Text {
            text: "Read-only inbox"
            color: "#efedf2"
            font.pixelSize: 17
        }
        Text {
            text: owner.snapshot.mail_status || "Not connected. Capri needs its own desktop OAuth registration; the chat's Gmail connector does not supply a token to this app."
            color: "#a5a2af"
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 12
        }
        TextField {
            id: mailRegistration
            placeholderText: "Path to your Gmail desktop OAuth client JSON"
            Layout.fillWidth: true
            Accessible.name: "Gmail desktop OAuth registration path"
        }
        TextField {
            id: mailLabels
            placeholderText: "Labels, e.g. INBOX"
            text: "INBOX"
            Layout.fillWidth: true
        }
        Text {
            text: "Google metadata access reads headers, not bodies. Plain-text summaries require gmail.readonly. These are restricted Google scopes; label filters apply in Capri and do not narrow Google's account-wide grant. No send/modify scope is requested."
            color: "#a5a2af"; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12
        }
        CapriComboBox { id: mailSummary; model: ["Metadata only", "Plain-text summary"]; Accessible.name: "Mail summary scope" }
        CheckBox { id: mailCloud; text: "Allow selected mail metadata/excerpts to the current ChatGPT model"; checked: false }
        RowLayout {
            CapriButton {
                text: "Connect read-only…"
                onClicked: owner.send("mail_connect", {
                    registration: mailRegistration.text,
                    labels: mailLabels.text.split(","),
                    summary: mailSummary.currentIndex === 0 ? "metadata" : "body",
                    cloud: mailCloud.checked
                })
            }
            CapriButton {
                text: "Check now"
                onClicked: owner.send("mail_poll", {})
            }
            CapriButton {
                text: "Disconnect"
                onClicked: owner.send("mail_disconnect", {})
            }
        }
        Text {
            text: "Maintenance"
            color: "#efedf2"
            font.pixelSize: 17
        }
        Text {
            text: owner.snapshot.update_status || "No trusted automatic release channel is configured. Self-authored code is staged for your review."
            color: "#a5a2af"
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 12
        }
        RowLayout {
            CapriButton {
                text: "Stage an improvement"
                onClicked: owner.send("maintenance_stage", {})
            }
            CapriButton { text: "Verify proposal"; onClicked: owner.send("maintenance_verify",{}) }
            CapriButton {
                text: "Check releases"
                onClicked: owner.send("update_check", {})
            }
            CapriButton {
                text: "Review staged change"
                onClicked: owner.send("maintenance_review", {})
            }
            CapriButton {
                text: "Rollback…"
                onClicked: owner.send("rollback_request", {})
            }
        }
        RowLayout {
            visible: !!owner.snapshot.rollback_target
            Text { text: "Return to version " + (owner.snapshot.rollback_target || "").slice(0,12) + "? Draft and private account data stay retained."; color: "#d2cbd8"; wrapMode: Text.Wrap; Layout.fillWidth: true }
            CapriButton { text: "Confirm rollback"; onClicked: owner.send("rollback_confirm",{digest:owner.snapshot.rollback_target}) }
        }
        Text {
            text: "Memory and local data"
            color: "#efedf2"
            font.pixelSize: 17
        }
        RowLayout {
            CapriButton {
                text: "Show memories"
                onClicked: owner.command("/memories")
            }
            CapriButton {
                text: "Export conversation"
                onClicked: owner.command("/export")
            }
        }
    }
}
