# Architecture

`Engine` owns frozen contracts, stage ordering, source checks, collector checks
and review/report gates. `Store` owns durable events, questions, attempts,
versions and task generations. The legacy exec adapter/parser remain separate
from `native_protocol.Lifecycle` and `NativeAdapter`.

`NativeSlots` owns one independently confined stdio app-server per role and
owner-only Unix WebSocket frontends. Raw pipes are not mounted into model
sandboxes. Unknown RPCs and frontend mutation methods default to denial, including
sandbox-bypassing `thread/shellCommand`. Bounded queues fan out notifications;
a slow client reconnects rather than taking another client's completion.

`NativeIntake` wraps the unchanged scoped service handler without the old exec
scheduler. Thinker capabilities are revoked in the Store during zero-tool probes.
Role titles, terminal UIDs and prompt text are not authorization.

The initial Doer preflight has an actual outer read-only mount. After remount,
the outer workspace is writable but a named inner recovery profile preserves
private-path denies and denies candidate writes. Fresh same-process usage and
original-file rereads precede explicit write-profile selection. Deterministic
command-sandbox qualification is distinct from pending native selector proof.

`context.ContextState` separates cumulative usage, last-request footprint, cached
input and UNKNOWN exact occupancy. Pressure/headroom are estimates with pending
payload and reserves. Provisional 60/75/85% thresholds checkpoint/compact/hold;
they are configurable policy, not model guarantees. The observed runtime window
is 475000; the native UI estimate uses a 12000-token baseline. Cached input stays
in context and reasoning counters are not added twice.

Checkpoints bind original requests/corrections, source/instructions, questions,
checks, uncertain effects and leases. Only exact recorded role/process lineage
can derive a recovery checkpoint. Restart does not refresh usage or reset budget.
Compaction requires matching item and successful terminal lifecycle; RPC ACK is
insufficient. Internal native inference/tool loops cannot be atomically policed
by the controller between notifications; automatic compaction holds continuation
and requires reconciliation.
