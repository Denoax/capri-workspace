import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: settings
    required property var owner
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
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
                text: owner.profile.quiet_start || ""
                maximumLength: 5
                implicitWidth: 75
            }
            TextField {
                id: quietEnd
                placeholderText: "HH:MM"
                text: owner.profile.quiet_end || ""
                maximumLength: 5
                implicitWidth: 75
            }
            CapriButton {
                text: "Save"
                onClicked: owner.send("preferences", {
                    changes: {
                        quiet_start: quietStart.text,
                        quiet_end: quietEnd.text
                    }
                })
            }
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
        TextField {
            id: rootInput
            placeholderText: "/absolute/project (one path per line in the full scope dialog)"
            Layout.fillWidth: true
            Accessible.name: "Selected project root"
        }
        RowLayout {
            CapriButton {
                text: "Use for work"
                onClicked: owner.send("set_scope", {
                    roots: [rootInput.text],
                    desktop: true
                })
            }
            CapriButton {
                text: "Observe locally"
                onClicked: owner.send("observe_project", {
                    root: rootInput.text,
                    cloud: false
                })
            }
            CapriButton {
                text: "Allow selected excerpts…"
                onClicked: owner.send("observe_project", {
                    root: rootInput.text,
                    cloud: true
                })
            }
        }
        Text {
            text: owner.snapshot.sources_text || "No project or inbox is being observed."
            color: "#a5a2af"
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            font.pixelSize: 12
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
        RowLayout {
            CapriButton {
                text: "Connect read-only…"
                onClicked: owner.send("mail_connect", {
                    registration: mailRegistration.text,
                    labels: mailLabels.text.split(","),
                    summary: "metadata"
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
