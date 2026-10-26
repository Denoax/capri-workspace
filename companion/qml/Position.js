.pragma library

// The anchor is output-logical. Native surface origins never enter a move.
function finite(values) {
    return values.every(v => Number.isFinite(v) && Math.abs(v) <= 100000);
}
function axis(value, low, high) {
    return high < low ? (low + high) / 2 : Math.max(low, Math.min(high, value));
}
function create(x, y) {
    return {x:x, y:y, epoch:0, writer:"restore", capture:null, moved:false, ended:null};
}
function place(state, x, y, writer) {
    if (state.capture || !finite([x, y]))
        return state;
    return Object.assign({}, state, {x:x, y:y, epoch:state.epoch + 1, writer:writer, ended:null});
}
function begin(state, name, width, height, footprint, offset, actorHeight, hit) {
    if (state.capture || !name || !finite([width, height, ...footprint, ...offset, actorHeight, ...hit])
            || width <= 0 || height <= 0 || footprint[2] <= 0 || footprint[3] <= 0)
        return state;
    const epoch = state.epoch + 1;
    const capture = {
        epoch:epoch, name:name, width:width, height:height,
        footprint:footprint.slice(), offset:offset.slice(),
        press:[state.x + offset[0], state.y + offset[1]],
        actorHeight:actorHeight, hit:hit.slice(), frame:null
    };
    return Object.assign({}, state, {epoch:epoch, writer:"capture", capture:capture, moved:false, ended:null});
}
function end(state, reason, persist) {
    if (!state.capture)
        return state;
    return Object.assign({}, state, {
        epoch:state.epoch + 1, writer:"idle", capture:null,
        ended:{epoch:state.capture.epoch, name:state.capture.name, reason:reason,
               moved:state.moved, persist:persist !== false}
    });
}
function sample(state, packet) {
    const capture = state.capture;
    if (!capture || packet.epoch !== capture.epoch)
        return state;
    if (!packet.valid || !finite([packet.x, packet.y]))
        return end(state, "pointer-unavailable", true);
    const output = Array.isArray(packet.outputs) ? packet.outputs.find(v => v.name === capture.name) : null;
    if (!output || !finite([output.x, output.y, output.width, output.height]) || output.width <= 0 || output.height <= 0)
        return end(state, "output-unavailable", false);
    if (capture.frame && ["x", "y", "width", "height"].some(k => Math.abs(capture.frame[k] - output[k]) > .01))
        return end(state, "output-changed", false);
    const frame = capture.frame || {x:output.x, y:output.y, width:output.width, height:output.height};
    const point = [(packet.x - frame.x) / frame.width * capture.width,
                   (packet.y - frame.y) / frame.height * capture.height];
    const outside = point[0] < 0 || point[1] < 0 || point[0] >= capture.width || point[1] >= capture.height;
    const moved = state.moved || Math.abs(point[0] - capture.press[0]) + Math.abs(point[1] - capture.press[1]) > 6;
    const bounds = capture.footprint;
    const x = moved ? axis(point[0] - capture.offset[0], 8 - bounds[0], capture.width - bounds[0] - bounds[2] - 8) : state.x;
    const y = moved ? axis(point[1] - capture.offset[1], 8 - bounds[1], capture.height - bounds[1] - bounds[3] - 8) : state.y;
    const next = Object.assign({}, state, {
        x:x, y:y, moved:moved, writer:"drag", ended:null,
        capture:Object.assign({}, capture, {frame:frame})
    });
    return outside ? end(next, "output-boundary", true) : next;
}
function travel(state, epoch, x, y) {
    if (state.capture || epoch !== state.epoch || state.writer !== "travel" || !finite([x, y]))
        return state;
    return Object.assign({}, state, {x:x, y:y});
}
