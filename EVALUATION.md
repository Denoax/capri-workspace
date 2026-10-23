# Evaluation and limits

Synthetic tests exercise protocol ordering, ACK-before-tools, budgets, admission,
owner/capability holds, source identity, original-read grading, checkpoint tamper,
lineage, context counters, freshness, thresholds and recovery holds. They do not
establish live native behavior, research capability or semantic retention.

Parent-reported supported-host suites belong to their recorded predecessor
sources, not this documentation revision. Earlier portability errors involved a
personal skill path and a pending-question check after credential preparation;
the shipped policy and early question guard address those paths while retaining
the later race fence. An earlier restricted-host snapshot reported 172 tests
with two namespace-runner failures. Retain those historical records; that is
not a current full-suite count.

The bounded S1 run restored source
`dd106743bcf554eaba79aa02e7ec8b8f6044da8d1767d4d5a3115a2fac39c2e3`
and reproduced the deferred-review fixture error: creating another task while
its synthetic parent was held correctly triggered the real gate. Moving only
that test into a fresh isolated fixture produced checkpoint
`d9829247b37537fabd6350c68b474d9196027c8738cef1ef8675b634e7cf9b98`.
Its 20 continuation and 13 completion tests passed locally. These are synthetic
offline controls, not actual native qualification or a full-suite result.

At S2 checkpoint
`8746b8e7c8b8e0746315ee62500a3d46da35a63d2cced70040c96be5089c1f3e`,
three portable checks passed. The new actual-collector namespace probe failed
with `bwrap: loopback: Failed to create NETLINK_ROUTE socket: Operation not permitted`;
both existing isolation runner tests also failed in this nested sandbox. No
required check was skipped or weakened. CI now installs bubblewrap and probes
user/mount/PID/network namespaces before the full suite. Supported-host execution
and actual CI logs remain parent-owned and pending; a workflow edit does not
establish CI success.

Frozen C2 still requires a baseline failure. Its original source lacked the
completion test, so zero discovered baseline tests cannot demonstrate regression
failure. Preserve this UNVERIFIED limitation and separately labelled behavioral
predecessor evidence; do not change the frozen check.

## Frozen small comparison

The planned schedule is eight trials: two synthetic fixtures × baseline/managed
policy × two repeats, alternating policy order and using one writer. Fixture A
checks an exact behavior after compaction. Fixture B applies the latest correction
after interruption/restart and checks duplicate effects. Use the same Sol model,
efforts, tools, source and held-out deterministic checks. Baseline retains safety
gates, native compaction and passive observation; managed adds context policy.

**Results: not run here; 0/8 trials executed by this role.** Parent qualification
and the frozen schedule artifact remain authoritative. Preserve every abort,
failure, retry, timing, usage gap and synthetic/genuine label. Report denominators
and inability to execute separately from retention scores.

Pending evidence includes native per-turn profile negatives, real search plus
original-page inspection, full stage/restart/report traces, compaction/replacement
and controller restart, tmux reconnection and actual eight-trial results. No
hallucination-prevention, optimal-threshold, huge-context-quality or general
superiority claim is supported. API model capacity and ChatGPT feature parity
cannot be inferred from the selected model name.

Parent must collect current-source native/CI/evaluation evidence before the sole
fresh independent formal review. A deferred sealed-candidate hold starts no
formal review and confers no acceptance. Every completed formal outcome,
including FAIL or UNVERIFIED, seals/reports/stops at `AWAITING_HUMAN`; further
repair requires an authorized revision. Delivery and Obsidian documentation
remain PENDING until the parent owner saves the corresponding receipts.

## Parent offline cutoff for this export

Source `189889d0635f4113e809b8e91724f58b263c6bdff1cd06e6c17b9f50f62d5bd7` passed all228 tests on the supported host and all228 in a separate no-network/no-auth collector, without skips or source changes. The same-wire invalid-ACK classification regression passes on this source and fails on preserved predecessor90379. The missing-terminal control stays uncertain. These are bounded technical results; actual CI, live qualification/evaluation and sole final formal review are reported separately in the source-bound private evidence delivery. Frozen C2 retains its absent-original-test limitation.
