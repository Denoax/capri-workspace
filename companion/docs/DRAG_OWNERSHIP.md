# Native drag ownership (V4 task 1 candidate)

`PositionController.qml` owns the output-logical anchor. `Position.js` contains the
state transitions; shell geometry and the actor only render it. Every restore,
bounds correction, IPC placement and travel animation uses that owner. Capture
revokes travel, blocks other writers and snapshots output identity/dimensions,
actor-local press offset, hit rectangle, size and the allowed painted footprint.
The footprint includes current animation plus pickup and release envelopes.

Dragging uses a separate, on-demand `capri.pointer --gesture EPOCH` reader at up to
120 Hz. It queries owned Hyprland native IPC directly, normalizes output geometry,
and maps global logical coordinates into the captured Qt output frame exactly
once. It never uses the moving layer-surface origin or the 8 Hz attention reader.
Each helper belongs to one gesture epoch; old data/exit callbacks cannot cancel a
new gesture. It is stopped on every end and has a parent-death signal. No helper
is added to idle operation. Tracing is off by default.

The native layer surface remains bounded; its captured canvas includes the actor
root and frozen painted footprint so edge clamping retains native input. Expanding it during an active grab
caused early release on the installed Qt/Quickshell/Hyprland stack. Native-global
input allows bounded surface repositioning without using those changing margins
as input coordinates. A fixed captured actor-sized canvas and native hit rectangle prevents animated alpha holes from
ending the held grab; idle input returns to the existing alpha regions. No
full-output input region is introduced. Speech controls are hidden during a
grab without changing the stored draft and return after capture ends.

A moved release sends a bounded control message to its helper and waits for a
sample acquired after that message, with a 50 ms deadline, before saving once.
Already queued pre-release samples cannot complete release. Cancel, hide, lock, core disconnect, pointer loss and graceful shell
destruction retain the last valid placement and revoke capture. A changed/lost
output discards that gesture save, aborts recovery, then resynchronizes and clamps
the placement on the remaining output. Same-screen dimension changes and external
IPC placement also abort recovery before clamping and saving. Cross-display transfer is not implemented:
reaching another output ends cleanly at the captured footprint boundary. Abrupt
process kill cannot save an in-flight gesture; the last saved placement survives.
A moved end suppresses automatic cue changes through the bounded recovery clip,
then schedules normal rest; it cannot select a new idle clip and reclamp the
anchor between release and recovery. Click without a drag opens quick reply; right click retains Settings behavior.

`CAPRI_DRAG_TRACE=1` explicitly enables local geometry diagnostics. Samples carry
native monotonic timestamps, epoch, global pointer/frame and input source; scene
callbacks carry wall time (the QA collector records monotonic receipt time).
Trace includes logical output size, DPR, anchor, bounds, surface, writer, clip,
travel and save count. It records no text, keys, microphone or provider data.
Disable tracing for resource measurements.

The source-bound review distinguishes reproduced cancellation failure from the
reported spontaneous exploding event, which remains unreproduced. Unit checks
alone do not prove native motion, physical input, fractional-DPI/hotplug behavior,
human visual approval or the complete V4 resource target.
