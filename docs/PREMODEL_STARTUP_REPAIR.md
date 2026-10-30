# Accounted frontend startup repair

The V4 launch reached three native frontend/backend slots, then rejected a valid
tmux mapping before its first probe. The production tmux parser returns PID text;
the verifier compared that field with an integer. The fix compares the validated
PID text with `str(record['pid'])`. All PID creation, pane, thread, generation and
single-client checks remain enforced. An actual-tmux control with synthetic idle
processes reproduces the baseline failure and passes on the repair; it is not
native model lifecycle evidence.

`inspect-startup-repair`, `prepare-startup-repair` and `launch-startup-repair` are
an explicit transition for this observed before-probe failure. They preserve the
original case, fence, source scope, consumed launch and failed home. The inspector
requires exact old intent/hold and failed-home event sequences, no tasks, attempts
or human effects, a revoked held capability, empty read-only roles, exact source,
inputs, config and registry, dead owned processes, absent endpoints and public
receive receipts without model/usage lifecycle. Unknown effects remain held.

The repair target has its own exact source/config/material bindings and unused
disposable home. The existing controlling-terminal origin boundary records one
new source-bound scope in the original Store. It starts no model. A separate
launch revalidates atomically, commits a single-use intent before effects and
reuses the existing native session/normal Engine. Any post-intent crash remains
held without retry. No old fence/scope is replayed, no old state is superseded,
and generic resume, protected core, budgets and isolation remain unchanged.

This source does not establish successful native compaction, qualification,
replacement/restart, usage coverage, benchmark outcomes or final formal review.
Those still require admitted observed execution and retain the final human gate.
