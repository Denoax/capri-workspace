import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

Rectangle {
    id: scope
    required property var owner
    implicitWidth: 320
    implicitHeight: body.implicitHeight + 32
    color: Theme.raised
    radius: 18
    border.color: Theme.pink
    ColumnLayout {
        id: body
        x: 16
        y: 16
        width: Math.max(1, scope.width - 32)
        spacing: 12
        Label {
            text: 'This task needs additional scope'
            color: Theme.ink
            font.pixelSize: 18
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Label {
            text: (scope.owner.snapshot.scope_request?.reason || '') + '\nFolders: ' + (scope.owner.snapshot.scope_request?.roots || []).join(', ') + '\nTyped desktop tools: ' + (scope.owner.snapshot.scope_request?.desktop ? 'requested' : 'no change') + '\nSelected contents may be sent to the current model. Applies only to this task.'
            textFormat: Text.PlainText
            color: Theme.muted
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            CapriButton {
                text: 'Allow this expansion'
                primary: true
                width: Math.min(implicitWidth, body.width)
                onClicked: scope.owner.send('scope_decision', {
                    id: scope.owner.snapshot.scope_request.id,
                    approved: true
                })
            }
            CapriButton {
                text: 'Decline'
                onClicked: scope.owner.send('scope_decision', {
                    id: scope.owner.snapshot.scope_request.id,
                    approved: false
                })
            }
        }
    }
}
