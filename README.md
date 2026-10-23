# Codex three-role workflow

An experimental deterministic controller coordinates three native Codex terminal
slots: Thinker, Doer and an independent Reviewer. It preserves frozen source,
question recovery, one writer, collector checks and the final human decision.
The accepted original checkout is not the development candidate.

Python 3.11+, Linux namespaces, bubblewrap and the qualified Codex CLI 0.163.0
profile are the current target. Native transport uses websockets 17.1. Existing
Codex authentication is mounted read-only; no new provider or API billing is
required. Native selector, full lifecycle, research and recovery qualification
are still pending. This is not a production cutover or a public release.

## Offline checks

From the source root:

```sh
python3 -m pip install --require-hashes -r requirements.lock
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s controller/tests -v
```

Tests do not call models or require authentication or a vault. The full suite
includes Linux namespace checks: namespace availability is a host prerequisite,
not a reason to silently skip a required check. CI installs bubblewrap and probes
user, mount, PID and network namespaces through the actual collector before the
full suite. Installation alone does not prove isolation. See EVALUATION.md for
source-specific results, inherited evidence and outstanding host/CI checks.

## Native startup

Adapt `examples/config.json`: choose an explicit private home, short state root,
source fixture, existing auth file and executable. Create the role input and
placeholder directories first. Keep production automation disabled. Only
human-registered fixture repositories can dispatch while that guard is disabled.
The controller needs a real foreground terminal for the initial request.

```sh
python3 controller/native_loopctl.py --config /absolute/native-config.json start
python3 controller/native_loopctl.py --config /absolute/native-config.json --headless start
python3 controller/native_loopctl.py --config /absolute/native-config.json status
python3 controller/native_loopctl.py --config /absolute/native-config.json --role doer attach
python3 controller/native_loopctl.py --config /absolute/native-config.json stop
```

Ordinary startup uses an existing tmux installation in a task-private server
(`state_dir/ui.sock`) with three recorded role panes. Each actual native client
uses a private frontend configuration preserving the selected model/effort.
Headless startup prints the corresponding commands and refreshes them when role
mappings change. An empty thread uses
normal `--remote` attachment; an existing rollout uses exact-thread resume.
Native terminal windows do not establish VS Code sidebar integration.

The foreground controller creates scoped Thinker intake, performs bounded
probes and hands off through the injected native adapter. Unsupported, stale or
uncertain stages stop. Automatic recovery orchestration is implemented but has
not been qualified end to end. Input typed in native clients is held as
unattested; explicit foreground confirmation records a correction for supported
re-contracting. A UID or model message cannot approve a task.

`stop` requests termination of the recorded supervisor after process checks.
Reconcile actual backend/child exits before restarting; disconnect is not turn
completion. Existing live sessions/endpoints are not blindly replaced. Startup preserves any
old three-role registry in a prestart snapshot and refuses a new task on that
root. Checked recovery APIs restore from a frozen snapshot; automatic CLI resume
of the entire interrupted workflow is not yet qualified. Cleanup closes only a
verified owned terminal session and preserves its archived pane registry. Registry thread/generation changes synchronously reconnect the same owned role
pane before subsequent controller work. Unknown panes, reused process identities
or an unrecorded server stop reconnection and cleanup. These controls have
synthetic coverage; live tmux behavior remains for parent qualification.

## Explicit native continuation

The trusted parent prepares a binding to the held task/version/generation,
candidate, controller/configuration, prior registry, exact one-line correction
and original instruction materials. These examples are operator templates;
replace paths and `RECEIPT_SHA256` with verified receipt values. They grant model
roles no authority to dispatch or confirm anything.

```sh
python3 controller/native_loopctl.py --config /absolute/native-config.json recontract --binding /absolute/binding.json --check
python3 controller/native_loopctl.py --config /absolute/native-config.json recontract --binding /absolute/binding.json
python3 controller/native_loopctl.py --config /absolute/native-config.json continue --prepared /absolute/prepared.json --prepared-sha256 RECEIPT_SHA256 --check
python3 controller/native_loopctl.py --config /absolute/native-config.json continue --prepared /absolute/prepared.json --prepared-sha256 RECEIPT_SHA256 --defer-review
```

`recontract --check` validates the binding without requesting input or preparing
a revision. Preparation requires genuine foreground input when no matching core
receipt exists; it reuses an exact committed receipt rather than asking again.
Preparation starts neither models nor the legacy scheduler. `continue --check`
checks the prepared route without claiming an owner or launching models.

Actual `continue` claims the core-derived owner once, then performs checked role
restoration for one native task. It preserves registry lineage, restores an
existing Doer rollout when applicable, and creates a fresh Reviewer. Partial
startup or a consumed claim requires explicit checked recovery, never a blind
retry. Old processes/endpoints and uncertain attempts must be reconciled first.
Headless continuation requires all three clients to attach within the implemented
15-second window; it does not bypass attachment checks. `attach` prints a client
command for the operator to execute. `status` reports recorded process identities,
not task completion.

Use `--defer-review` on `continue` while parent qualification is pending. The
engine verifies the exact sealed candidate, records `NATIVE_QUALIFICATION_PENDING`
and leaves the task at `CANDIDATE_SEALED`, with formal review not started and
documentation PENDING. Without that flag, the engine normally invokes review
after sealing. The flag is wired to continuation, not ordinary `start`. A hold
does not qualify the source, approve it or automatically resume final review.
Parent must finish qualification/evaluation before the sole formal review.
Supervision remains active until stop; no successor task starts automatically.

Restart/compaction/replacement recovery APIs preserve owner and role lineage and
withhold writes until lifecycle, source, originals, questions, checks, lease and
fresh usage are validated. There is no general automatic CLI resume guarantee.
These implementation boundaries and synthetic checks remain distinct from
current-source native end-to-end qualification.

## Rollback and legacy route

Stop the isolated supervisor, verify owned processes have exited, and retain its
source, checkpoints, receipts and evidence. Leave the original controller/root
unchanged. Do not reset source, delete history, repair SQLite manually or infer
human acceptance. The existing `controller/loopctl.py` exec adapter remains the
labelled legacy route; it is not proof of three native sessions.

Completed formal PASS, FAIL and UNVERIFIED outcomes stop at `AWAITING_HUMAN`. The existing hash-bound decision
CLI remains the sole accept/revise/reject boundary. No merge, release, remote
write, deployment or successor task follows automatically. Documentation remains
PENDING until the parent owner saves its receipt. License choice is pending.
