.pragma library
// Translate compositor logical layout into this Qt output's local coordinates.
// Per-app fractional scaling may change Qt dimensions without changing Hyprland.
function localPoint(sample, name, width, height) {
    var output = Array.isArray(sample.outputs) ? sample.outputs.find(v => v.name === name) : null;
    if (!output || ![sample.x, sample.y, output.x, output.y, output.width, output.height, width, height].every(Number.isFinite)
            || output.width <= 0 || output.height <= 0 || width <= 0 || height <= 0)
        return null;
    var x = (sample.x - output.x) / output.width, y = (sample.y - output.y) / output.height;
    return x >= 0 && x < 1 && y >= 0 && y < 1 ? [x * width, y * height] : null;
}
function safeDistance(bounds) { return Math.max(250, Math.hypot(bounds.width, bounds.height) / 2 + 90); }
