# Fresh disposable native qualification

`native_loopctl.py launch-stopped-qualification --binding <binding.json> --check`
checks a stopped read-only compaction against the pinned recovery tool, exact
target/configuration, original packet/answers/checkpoint, dead processes and
owned endpoints. It initializes no state and starts no model, process or socket.
Before the two existing foreground fence/source-preparation transitions, its
status is `FRESH_QUALIFICATION_NEEDS_FOREGROUND`.

After those transitions, the same command without `--check` commits one
`NATIVE_DISPOSABLE_QUALIFICATION_INTENT` in the original Store before creating a
new disposable home. The old sealed task, scope220, historical failure and all
consumed counters remain unchanged. An ordinary new Engine/Store owns only the
new qualification task. It does not copy old decision authority or bypass the
old Store's human gate. Exact originals and captured answers remain mounted as
hash-bound data. The fresh qualification request is a distinct source condition.

The command reuses native startup's session orchestration, held capability,
normal Engine submission and sealed operator hold. It requires three visible
native clients and verifies backend/frontend PID, thread and generation
mappings before probing. Headless dispatch is rejected. Role settings, stage
budgets, namespaces, human decisions and generic resume remain unchanged.

A launch intent is consumed even if startup fails before a model turn. A lost
response or partial home requires explicit effect reconciliation; rerunning is
rejected. Never remove the home, change a case hash, reset counters or replay an
intent to obtain admission. Stopping closes the owned session; it does not
accept, integrate, cut over or authorize another task. Status/stop use the
existing native CLI with the exact target configuration. Rollback before
admission is simply to leave this isolated proposal unused; preserve evidence.

The parent-only `tools/native_usage.py` converts hash-bound public capture
files against the installed CLI schema. Cumulative deltas must equal `last` to
produce an inference row; duplicates are counted once. Reasoning remains inside
output. Missing boundaries, cache-write retention and unaccounted charged paths
remain explicit gaps. The converter deliberately leaves `usage_complete=false`
until a separate parent dispatch/process reconciliation is implemented and
observed. No invoice or cost saving follows from these unit controls.

This source implements the launch boundary. Actual native qualification,
compaction completion/rereads, replacement/restart, eight-row smoke runset,
24-run comparison and the sole formal Reviewer/report still need observed
admitted execution. Technical checks and source integration do not certify them.
