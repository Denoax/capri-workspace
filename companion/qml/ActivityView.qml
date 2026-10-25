import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

ScrollView {
    id: activity
    required property var owner
    property real textScale: (owner.profile.ui_text_scale || 100) / 100
    property string eventPartition: ""
    function syncEvents() {
        if (eventPartition !== (owner.snapshot.partition || "")) {
            events.clear();
            eventPartition = owner.snapshot.partition || "";
        }
        var incoming = owner.snapshot.activity || [];
        for (var i = 0; i < incoming.length; i++) {
            var v = incoming[i], row = {
                eventId: v.id,
                kind: v.kind,
                detail: v.detail,
                truncated: !!v.truncated
            };
            if (i >= events.count)
                events.append(row);
            else if (events.get(i).eventId !== v.id) {
                var found = -1;
                for (var j = i + 1; j < events.count; j++)
                    if (events.get(j).eventId === v.id) {
                        found = j;
                        break;
                    }
                if (found >= 0)
                    events.move(found, i, 1);
                else
                    events.insert(i, row);
            }
            for (var key of ['kind', 'detail', 'truncated'])
                if (events.get(i)[key] !== row[key])
                    events.setProperty(i, key, row[key]);
        }
        if (events.count > incoming.length)
            events.remove(incoming.length, events.count - incoming.length);
    }
    function readable(detail) {
        try {
            var v = JSON.parse(detail);
            if (v.arguments?.patch)
                return 'Patch\n' + v.arguments.patch;
            if (typeof v.arguments?.text === 'string')
                return (v.arguments.path || 'File') + '\n\n' + v.arguments.text;
            if (typeof v.result?.output === 'string')
                return 'Exit ' + v.result.exit_code + '\n\n' + v.result.output;
            return JSON.stringify(v, null, 2);
        } catch (e) {
            return detail;
        }
    }
    Component.onCompleted: syncEvents()
    Connections {
        target: activity.owner
        function onSnapshotChanged() {
            activity.syncEvents();
        }
    }
    ListModel {
        id: events
    }
    signal changeScope
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        width: activity.availableWidth
        spacing: 20
        Loader {
            Layout.fillWidth: true
            active: !!activity.owner.snapshot.scope_request
            visible: active
            sourceComponent: ScopeRequest {
                owner: activity.owner
            }
        }
        Label {
            text: activity.owner.busy ? (activity.owner.snapshot.task_phase || 'Working') : 'Activity'
            color: Theme.ink
            font.family: 'Inter'
            font.pixelSize: 24 * activity.textScale
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        Label {
            text: (activity.owner.snapshot.scope?.roots || []).length ? 'Task scope: ' + activity.owner.snapshot.scope.roots.join(', ') : 'Choose exact project roots in Settings before sending a Task.'
            textFormat: Text.PlainText
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        CapriButton {
            text: 'Choose task scope'
            onClicked: activity.changeScope()
        }
        Label {
            text: 'Tasks'
            color: Theme.ink
            font.pixelSize: 18 * activity.textScale
        }
        Repeater {
            model: activity.owner.snapshot.tasks || []
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: 8
                Label {
                    text: modelData.objective
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: Theme.ink
                    Layout.fillWidth: true
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: modelData.status
                        color: Theme.muted
                        padding: 12
                    }
                    CapriButton {
                        text: 'Resume'
                        enabled: !activity.owner.busy && modelData.status !== 'running'
                        onClicked: activity.owner.send('resume_task', {
                            id: modelData.id
                        })
                    }
                }
            }
        }
        Label {
            visible: !(activity.owner.snapshot.tasks || []).length
            text: 'Completed and interrupted tasks appear here.'
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Label {
            text: 'Commands and results'
            color: Theme.ink
            font.pixelSize: 18 * activity.textScale
        }
        Repeater {
            model: events
            delegate: ColumnLayout {
                id: record
                required property int eventId
                required property string kind
                required property string detail
                required property bool truncated
                property bool expanded: false
                Layout.fillWidth: true
                spacing: 8
                CapriButton {
                    Layout.fillWidth: true
                    text: (record.expanded ? '−  ' : '+  ') + record.kind
                    flat: true
                    onClicked: record.expanded = !record.expanded
                }
                CapriTextArea {
                    visible: record.expanded
                    Layout.fillWidth: true
                    readOnly: true
                    text: activity.readable(record.detail)
                    selectByMouse: true
                }
                Label {
                    visible: record.expanded && record.truncated
                    text: 'This preview is truncated; the local task journal retains the stored record.'
                    color: Theme.pink
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
                Rectangle {
                    height: 1
                    Layout.fillWidth: true
                    color: Theme.outline
                }
            }
        }
        Label {
            visible: !(activity.owner.snapshot.activity || []).length
            text: 'Real command, verification and permission records appear after task activity.'
            color: Theme.muted
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
    }
}
