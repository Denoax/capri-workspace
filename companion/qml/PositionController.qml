import QtQuick
import "Position.js" as Position

QtObject {
    id: control
    property var model: Position.create(100, 420)
    readonly property real x: model.x
    readonly property real y: model.y
    readonly property bool captured: model.capture !== null
    readonly property bool dragging: captured && model.moved
    readonly property int epoch: model.capture ? model.capture.epoch : model.epoch
    readonly property real captureHeight: model.capture ? model.capture.actorHeight : 0
    readonly property var hit: model.capture ? model.capture.hit : null
    property bool traveling: false
    property int travelEpoch: -1
    property real travelX: 100
    property real travelY: 420
    property int gestureSaves: 0
    property bool releasePending: false
    signal releaseRequested
    signal captureStarted(int epoch)
    signal captureEnding(bool moved)
    signal captureEnded(int epoch, bool moved, string reason)
    signal commitRequested(string output, string reason)
    signal diagnostic(string event, var data)

    function adopt(next) {
        if (next === model)
            return false;
        const old = model;
        if (old.capture && !next.capture)
            captureEnding(next.ended.moved);
        model = next;
        if (!old.capture && next.capture)
            captureStarted(next.capture.epoch);
        if (old.capture && !next.capture) {
            releasePending = false;
            const ended = next.ended;
            captureEnded(ended.epoch, ended.moved, ended.reason);
            if (ended.moved && ended.persist) {
                gestureSaves++;
                commitRequested(ended.name, ended.reason);
            }
        }
        return true;
    }
    function place(px, py, reason) {
        const accepted = adopt(Position.place(model, px, py, reason));
        if (!accepted && captured)
            diagnostic('rejected-writer', {
                writer: reason,
                epoch: epoch
            });
        return accepted;
    }
    function begin(name, width, height, footprint, offset, actorHeight, hitBounds) {
        traveling = false;
        const accepted = adopt(Position.begin(model, name, width, height, footprint, offset, actorHeight, hitBounds));
        if (accepted)
            diagnostic('begin', {
                epoch: epoch,
                anchor: [x, y],
                footprint: footprint,
                offset: offset
            });
        return accepted;
    }
    function sample(packet) {
        const accepted = adopt(Position.sample(model, packet));
        if (accepted && captured && releasePending && packet.final === true)
            end("release", true);
        if (accepted)
            diagnostic('sample', {
                epoch: packet.epoch,
                monotonic: packet.monotonic,
                pointer: [packet.x, packet.y],
                frame: model.capture ? model.capture.frame : null,
                inputSource: "hyprland-native-global",
                anchor: [x, y],
                moved: model.moved,
                captured: captured
            });
    }
    function release() {
        // Let the native input clock deliver the final point before revoking it.
        if (captured && model.moved) {
            releasePending = true;
            releaseRequested();
        } else
            end("release", true);
    }
    function end(reason, persist) {
        return adopt(Position.end(model, reason, persist));
    }
    function prepareTravel() {
        if (captured)
            return false;
        traveling = false;
        place(x, y, 'travel');
        travelX = x;
        travelY = y;
        travelEpoch = model.epoch;
        traveling = true;
        return true;
    }
    onTravelXChanged: if (traveling)
        adopt(Position.travel(model, travelEpoch, travelX, travelY))
    onTravelYChanged: if (traveling)
        adopt(Position.travel(model, travelEpoch, travelX, travelY))
}
