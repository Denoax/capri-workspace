import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

ScrollView {
    id: settings
    required property var owner
    property real textScale: (owner.profile.ui_text_scale || 100) / 100
    function reviewPoints(reference) {
        function at(i) {
            var p = i.mapToItem(reference, i.width / 2, i.height / 2);
            return {
                x: p.x,
                y: p.y
            };
        }
        return {
            root: at(rootInput),
            save: at(scopeSave),
            textSizeFocused: textSize.activeFocus,
            textSizeValue: textSize.value,
            rootFocused: rootInput.activeFocus,
            rootLength: rootInput.text.length,
            viewportWidth: availableWidth,
            contentWidth: settingsColumn.childrenRect.width,
            visibleContentWidth: Math.max.apply(null, settingsColumn.children.filter(i => i.visible).map(i => i.x + i.width))
        };
    }
    function revealHeading(label) {
        for (var item of settingsColumn.children)
            if (item.text === label) {
                contentItem.contentY = Math.max(0, item.y - 4);
                return true;
            }
        return false;
    }
    function revealTextSize() {
        contentItem.contentY = Math.max(0, textSize.mapToItem(settingsColumn, 0, 0).y - 30);
        textSize.forceActiveFocus();
    }
    function scopePoints() {
        return JSON.stringify({
            root: rootInput.mapToGlobal(rootInput.width / 2, rootInput.height / 2),
            save: scopeSave.mapToGlobal(scopeSave.width / 2, scopeSave.height / 2),
            viewport: settings.mapToGlobal(0, 0),
            viewportHeight: settings.height,
            contentY: contentItem.contentY,
            rootLength: rootInput.text.length,
            rootFocused: rootInput.activeFocus
        });
    }
    function revealScopeSave() {
        rootInput.focus = false;
        contentItem.cancelFlick();
        contentItem.contentY = Math.max(0, scopeSave.mapToItem(settingsColumn, 0, 0).y - 90);
    }
    function revealScope() {
        contentItem.contentY = Math.max(0, rootInput.y - 4);
    }
    property bool scopeDirty: false
    Connections {
        target: owner
        function onSnapshotChanged() {
            if (!settings.scopeDirty) {
                rootInput.text = (owner.snapshot.scope?.roots || []).join("\n");
                desktopScope.checked = owner.snapshot.scope?.desktop || false;
            }
        }
    }
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        id: settingsColumn
        width: settings.availableWidth
        spacing: 20
        Label {
            text: "Presence and attention"
            color: Theme.ink
            font.pixelSize: 18 * settings.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 12
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Quiet"
                checked: owner.profile.quiet || false
                onToggled: owner.preference("quiet", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Roam"
                checked: owner.profile.roam !== false
                onToggled: owner.preference("roam", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Cursor curiosity"
                checked: owner.profile.follow !== false
                onToggled: owner.preference("follow", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Pinned"
                checked: owner.profile.pinned || false
                onToggled: owner.preference("pinned", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Reduced motion"
                checked: owner.profile.reduced_motion || false
                onToggled: owner.preference("reduced_motion", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Do not disturb"
                checked: owner.profile.dnd || false
                onToggled: owner.preference("dnd", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Pause observation and tasks"
                checked: owner.profile.paused || false
                onToggled: owner.preference("paused", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Initiative"
                checked: owner.profile.initiative ?? true
                onToggled: owner.preference("initiative", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Mute sounds"
                checked: owner.profile.mute || false
                onToggled: owner.preference("mute", checked)
            }
            CapriToggle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                width: Math.min(implicitWidth, settings.availableWidth)
                text: "Ctrl+Enter sends"
                checked: owner.profile.send_with_ctrl || false
                onToggled: owner.preference("send_with_ctrl", checked)
            }
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            Label {
                text: "Size"
                color: Theme.muted
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
            Label {
                text: "Sound"
                color: Theme.muted
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
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            Label {
                text: "Output"
                color: Theme.muted
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
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            Label {
                text: "Check-in gap (minutes)"
                color: Theme.muted
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
            Label {
                text: "Quiet hours"
                color: Theme.muted
            }
            CapriField {
                id: quietStart
                placeholderText: "HH:MM"
                Component.onCompleted: text = owner.profile.quiet_start || ""
                maximumLength: 5
                implicitWidth: Math.max(112, 100 * settings.textScale)
            }
            CapriField {
                id: quietEnd
                placeholderText: "HH:MM"
                Component.onCompleted: text = owner.profile.quiet_end || ""
                maximumLength: 5
                implicitWidth: Math.max(112, 100 * settings.textScale)
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
        CapriField {
            id: timezoneInput
            placeholderText: "IANA timezone, e.g. America/Edmonton"
            Component.onCompleted: text = owner.profile.timezone || "America/Edmonton"
            Layout.fillWidth: true
            Accessible.name: "Quiet hours timezone"
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            Label {
                text: "Text size"
                color: Theme.muted
                font.pixelSize: 15 * settings.textScale
            }
            Slider {
                id: textSize
                from: 100
                to: 200
                stepSize: 10
                value: owner.profile.ui_text_scale || 100
                onMoved: owner.preference("ui_text_scale", Math.round(value))
                Accessible.name: "Interface text size percent"
            }
            Label {
                text: (owner.profile.ui_text_scale || 100) + "%"
                color: Theme.muted
                font.pixelSize: 15 * settings.textScale
            }
            CapriButton {
                text: "Motion review"
                onClicked: owner.openMotionReview()
            }
        }
        Label {
            text: "Account and model"
            color: Theme.ink
            font.pixelSize: 18 * settings.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            CapriButton {
                text: "Continue with ChatGPT"
                onClicked: owner.command("/signin")
            }
            CapriComboBox {
                model: owner.snapshot.models || []
                textRole: "name"
                valueRole: "id"
                currentIndex: Math.max(0, (owner.snapshot.models || []).findIndex(m => m.id === owner.snapshot.model))
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
        Label {
            text: "Work scope and observed projects"
            color: Theme.ink
            font.pixelSize: 18 * settings.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Label {
            text: "Choose exact project roots. Observation stays local unless you explicitly allow selected excerpts. Work tasks cannot access credentials or Capri's live authority/update files."
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 14 * settings.textScale
        }
        CapriTextArea {
            id: rootInput
            placeholderText: "/absolute/project — one exact directory per line"
            Component.onCompleted: text = (owner.snapshot.scope?.roots || []).join("\n")
            onTextChanged: if (activeFocus)
                settings.scopeDirty = true
            Layout.fillWidth: true
            Layout.preferredHeight: 112
            color: Theme.ink
            textFormat: TextEdit.PlainText
            Accessible.name: "Selected project roots"
            background: Rectangle {
                color: Theme.field
                radius: 6
            }
        }
        CapriToggle {
            id: desktopScope
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: settings.availableWidth
            width: Math.min(implicitWidth, settings.availableWidth)
            text: "Allow typed application, window, media and volume actions for requested Tasks"
            Component.onCompleted: checked = owner.snapshot.scope?.desktop || false
            onToggled: settings.scopeDirty = true
        }
        Label {
            text: "Sending a Task authorizes edits and tests within these folders for up to 30 minutes / 64 actions. Selected file contents and task results may be sent to your selected ChatGPT model. Network and general GUI input remain unavailable. Stop revokes the task."
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 14 * settings.textScale
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
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
        Label {
            text: owner.snapshot.sources_text || "No selected project observation."
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 14 * settings.textScale
        }
        Repeater {
            model: owner.snapshot.observation_sources || []
            delegate: RowLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.maximumWidth: settings.availableWidth
                required property var modelData
                Label {
                    text: modelData.root
                    color: Theme.muted
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                CapriButton {
                    text: "Stop observing"
                    onClicked: owner.send("unobserve_project", {
                        root: modelData.root
                    })
                }
            }
        }
        Label {
            text: "Read-only inbox"
            color: Theme.ink
            font.pixelSize: 18 * settings.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Label {
            text: owner.snapshot.mail_status || "Not connected. Capri needs its own desktop OAuth registration; the chat's Gmail connector does not supply a token to this app."
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 14 * settings.textScale
        }
        CapriField {
            id: mailRegistration
            placeholderText: "Path to your Gmail desktop OAuth client JSON"
            Layout.fillWidth: true
            Accessible.name: "Gmail desktop OAuth registration path"
        }
        CapriField {
            id: mailLabels
            placeholderText: "Labels, e.g. INBOX"
            text: "INBOX"
            Layout.fillWidth: true
        }
        Label {
            text: "Google metadata access reads headers, not bodies. Plain-text summaries require gmail.readonly. These are restricted Google scopes; label filters apply in Capri and do not narrow Google's account-wide grant. No send/modify scope is requested."
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 14 * settings.textScale
        }
        CapriComboBox {
            id: mailSummary
            model: ["Metadata only", "Plain-text summary"]
            Accessible.name: "Mail summary scope"
        }
        CapriToggle {
            id: mailCloud
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: settings.availableWidth
            width: Math.min(implicitWidth, settings.availableWidth)
            text: "Allow selected mail metadata/excerpts to the current ChatGPT model"
            checked: false
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
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
        Label {
            text: "Maintenance"
            color: Theme.ink
            font.pixelSize: 18 * settings.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Label {
            text: owner.snapshot.update_status || "No trusted automatic release channel is configured. Self-authored code is staged for your review."
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 14 * settings.textScale
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            CapriButton {
                text: "Stage an improvement"
                onClicked: owner.send("maintenance_stage", {})
            }
            CapriButton {
                text: "Verify proposal"
                onClicked: owner.send("maintenance_verify", {})
            }
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
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            visible: !!owner.snapshot.rollback_target
            Label {
                text: "Return to version " + (owner.snapshot.rollback_target || "").slice(0, 12) + "? Draft and private account data stay retained."
                color: Theme.muted
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            CapriButton {
                text: "Confirm rollback"
                onClicked: owner.send("rollback_confirm", {
                    digest: owner.snapshot.rollback_target
                })
            }
        }
        Label {
            text: "Memory and local data"
            color: Theme.ink
            font.pixelSize: 18 * settings.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Flow {
            Layout.minimumWidth: 0
            Layout.preferredWidth: settings.availableWidth
            Layout.maximumWidth: settings.availableWidth
            Layout.fillWidth: true
            spacing: 8
            CapriButton {
                text: "Show memories"
                onClicked: owner.command("/memories")
            }
            CapriButton {
                text: "Export conversation"
                onClicked: owner.command("/export")
            }
        }
        Label {
            text: "About and credits"
            color: Theme.ink
            font.pixelSize: 18 * settings.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            textFormat: Text.RichText
            color: Theme.muted
            font.pixelSize: 14 * settings.textScale
            text: 'Native interface rhythm adapted from Mani’s portfolio. Navigation reference: <a href="https://rareui.com">Rare UI / Swami Malode</a>. Original character and licensed Inter / Manrope assets preserved.'
            onLinkActivated: link => Qt.openUrlExternally(link)
        }
    }
}
