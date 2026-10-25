import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Flickable {
    id: transcript
    required property var owner
    property string query: ""
    property real textScale: 1
    property bool followLatest: true
    property string partition: ""
    contentWidth: width
    contentHeight: history.height
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    function latest() {
        followLatest = true;
        contentY = Math.max(0, contentHeight - height);
    }
    function metrics() {
        return JSON.stringify({
            offset: contentY,
            height: height,
            contentHeight: contentHeight,
            followingLatest: followLatest,
            turns: turns.count
        });
    }
    function sync() {
        if (partition !== (owner.snapshot.partition || "")) {
            turns.clear();
            partition = owner.snapshot.partition || "";
            stream.clear();
            followLatest = true;
        }
        var incoming = owner.snapshot.history || [];
        if (incoming.length) {
            while (turns.count && turns.get(0).turnId < incoming[0].id)
                turns.remove(0);
        } else if (turns.count)
            turns.clear();
        for (var i = 0; i < incoming.length; i++) {
            var m = incoming[i], row = {
                turnId: m.id,
                who: m.role,
                message: m.text,
                terminal: m.status
            };
            if (i >= turns.count)
                turns.append(row);
            else if (turns.get(i).turnId !== m.id) {
                turns.remove(i, turns.count - i);
                turns.append(row);
            } else
                for (var key of ['who', 'message', 'terminal'])
                    if (turns.get(i)[key] !== row[key])
                        turns.setProperty(i, key, row[key]);
        }
        updateStream();
    }
    function updateStream() {
        var next = owner.partial || "";
        if (next.startsWith(stream.text))
            stream.insert(stream.length, next.slice(stream.length));
        else
            stream.text = next;
    }
    onMovementStarted: followLatest = false
    onMovementEnded: followLatest = contentY + height >= contentHeight - 36
    onHeightChanged: if (followLatest)
        Qt.callLater(latest)
    onContentHeightChanged: if (followLatest)
        Qt.callLater(latest)
    onQueryChanged: if (query)
        followLatest = false
    Component.onCompleted: sync()
    Connections {
        target: transcript.owner
        function onSnapshotChanged() {
            transcript.sync();
        }
        function onPartialChanged() {
            transcript.updateStream();
        }
    }
    ListModel {
        id: turns
    }
    ScrollBar.vertical: ScrollBar {
        onPressedChanged: if (!pressed)
            transcript.followLatest = transcript.contentY + transcript.height >= transcript.contentHeight - 36
    }
    Column {
        id: history
        width: transcript.width
        spacing: 24
        Repeater {
            model: turns
            delegate: Column {
                id: messageItem
                required property string who
                required property string message
                required property string terminal
                width: history.width
                spacing: 8
                property bool matchesQuery: !transcript.query || message.toLowerCase().includes(transcript.query.toLowerCase())
                visible: matchesQuery
                height: matchesQuery ? implicitHeight : 0
                Text {
                    text: messageItem.who === 'user' ? 'You' : 'Capri'
                    color: messageItem.who === 'user' ? Theme.muted : Theme.green
                    font.family: 'Inter'
                    font.pixelSize: 12 * transcript.textScale
                }
                Rectangle {
                    width: parent.width
                    height: body.implicitHeight + (messageItem.who === 'user' ? 24 : 0)
                    radius: 18
                    color: messageItem.who === 'user' ? Theme.raised : 'transparent'
                    TextEdit {
                        id: body
                        x: messageItem.who === 'user' ? 14 : 0
                        y: messageItem.who === 'user' ? 12 : 0
                        width: parent.width - 2 * x
                        text: messageItem.message
                        textFormat: TextEdit.PlainText
                        readOnly: true
                        selectByMouse: true
                        persistentSelection: true
                        wrapMode: TextEdit.Wrap
                        color: Theme.ink
                        selectionColor: Theme.green
                        selectedTextColor: Theme.onGreen
                        font.family: 'Inter'
                        font.pixelSize: 16 * transcript.textScale
                        Accessible.name: (messageItem.who === 'user' ? 'You: ' : 'Capri: ') + text
                    }
                }
                Text {
                    visible: messageItem.terminal !== 'completed'
                    text: messageItem.terminal
                    color: Theme.pink
                    font.pixelSize: 12 * transcript.textScale
                }
            }
        }
        TextEdit {
            id: stream
            width: history.width
            visible: length > 0
            textFormat: TextEdit.PlainText
            readOnly: true
            selectByMouse: true
            persistentSelection: true
            wrapMode: TextEdit.Wrap
            color: Theme.ink
            selectionColor: Theme.green
            selectedTextColor: Theme.onGreen
            font.family: 'Inter'
            font.pixelSize: 16 * transcript.textScale
            Accessible.name: 'Capri’s current response'
        }
        Text {
            visible: transcript.owner.busy
            text: transcript.owner.snapshot.task_phase || 'Thinking…'
            color: Theme.green
            font.pixelSize: 14 * transcript.textScale
        }
        Item {
            width: 1
            height: 8
        }
    }
}
