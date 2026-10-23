Current experimental intake/recovery changes and qualification limits: [NATIVE_INTAKE.md](NATIVE_INTAKE.md).

# Codex three-role workflow

An experimental deterministic controller coordinates three native Codex terminal
slots: Thinker, Doer and an independent Reviewer. It preserves frozen source,
question recovery, one writer, collector checks and the final human decision.
The accepted original checkout is not the development candidate.

Python 3.11+, Linux namespaces, bubblewrap and the qualified Codex CLI 0.163.0
profile are the current target. Native transport uses websockets 17.1. Existing
Codex authentication is mounted read-only; no new provider or API billing is
required. Current-source native startup, lifecycle, research and recovery qualification
remain pending; see CLIENT_SUPPORT.md and the source-bound parent receipts. This is not a production cutover or a public release.

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
command for the operator to execute. `status` reads validated durable context and process records without making telemetry fresh. It does not infer task completion.

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

## Source-bound native maintenance

Stabilization adds a separate native-only recovery admission. It keeps the old
core re-contract receipt and one-shot claim consumed. The trusted parent binds
an accounted stopped pre-probe launch, exact old/new source, controller/config,
registry/generations, materials and a new single-line maintenance scope. Checks
use SQLite read-only mode without initializing or migrating runtime state.

```sh
python3 controller/native_loopctl.py --config /absolute/native-config.json prepare-maintenance --binding /absolute/maintenance-binding.json --check
python3 controller/native_loopctl.py --config /absolute/native-config.json prepare-maintenance --binding /absolute/maintenance-binding.json
python3 controller/native_loopctl.py --config /absolute/native-config.json recover-startup --prepared /absolute/prepared.json --prepared-sha256 RECEIPT_SHA256 --check
python3 controller/native_loopctl.py --config /absolute/native-config.json recover-startup --prepared /absolute/prepared.json --prepared-sha256 RECEIPT_SHA256
```

Preparation captures genuine foreground scope only after pure checks. It creates
no model/backend and never resets or reclaims the old claim. A consumed native
launch intent returns a hold. A duplicate or lost response cannot start another
turn. No general recovery from an unaccounted old launch is implied. Startup
creates held capabilities before any role process and revokes them on cleanup.
Foreign owner context ledgers remain unchanged; same-owner history is retained.

The new route always stops implementation at `CANDIDATE_SEALED` for parent
qualification and evaluation. It serves a private parent-only operator socket
on the same supervisor/main thread, with no model mount or second controller.
The parent prepares an exact sealed-task/version/owner/packet/source/controller/
supervisor binding. Maintenance also binds idle Doer thread/generation. Final
review binds at most ten indexed evidence bundles, each <=24000 bytes and total
<=120000 bytes, including INDEX.json; all eight N01-N08 are required.

```sh
python3 controller/native_loopctl.py --config /absolute/native-config.json maintenance --action compact-role --binding /absolute/role-binding.json
python3 controller/native_loopctl.py --config /absolute/native-config.json maintenance --action replace-role --binding /absolute/role-binding.json
python3 controller/native_loopctl.py --config /absolute/native-config.json maintenance --action checkpoint-runtime --binding /absolute/role-binding.json
python3 controller/native_loopctl.py --config /absolute/native-config.json resume-runtime --prepared /absolute/runtime-checkpoint.json --prepared-sha256 RECEIPT_SHA256 --check
python3 controller/native_loopctl.py --config /absolute/native-config.json resume-runtime --prepared /absolute/runtime-checkpoint.json --prepared-sha256 RECEIPT_SHA256
python3 controller/native_loopctl.py --config /absolute/native-config.json finish-review --binding /absolute/review-binding.json
```

`checkpoint-runtime` saves current originals, scope, registry, owner/Doer
checkpoints and stops the existing supervisor. Resume requires exact old process
and endpoint exits, unchanged artifacts/source/config and a one-shot restart
intent. It resumes the same Thinker/Doer rollouts at generation+1, creates a fresh
empty Reviewer, then measures and rereads originals before any work. It returns
to the qualification hold. This route still needs current-source live evidence.

A timeout/uncertain operation stays recorded and prevents review or ordinary
work. Status exposes the journal separately from telemetry. A narrow parent
`maintenance --action reconcile-maintenance` may fence a stopped read-only Doer
compaction using `uncertain_key`: exact process exit, unchanged source/inputs and
pre-operation checkpoint are mandatory. It does not resume or reuse that thread.
A separate `replace-role` binding with `reconciled_key` creates a fresh read-only
Doer and retains the old ledger/counters/probes and fence lineage; measurement and
original rereads must succeed before recovery is recorded. Unknown write turns,
active/reused processes, modified source, questions and final human gates cannot
use this route. Other uncertainty remains held for a separate supported scope.

Only after qualification/evaluation does `finish-review` run the one fresh formal
Reviewer and same Thinker report using the existing Engine. Every completed
formal outcome stops at AWAITING_HUMAN. A missing/incomplete review remains
BLOCKED. None of these commands accepts, integrates or starts a successor.

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
