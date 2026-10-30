# Completed read-validation failure recovery

The second bounded binding profile also covers the observed maintenance
precondition rejection after a complete source-bound restart. It requires the
complete preceding role turns and model-visible owner sections, a stale ledger
at the maintenance timestamp, no subsequent model/tool turn in validated frame
receipts, held capabilities and fully retired runtime ownership. The original
maintenance uncertainty remains recorded. This does not recover a timed-out
compaction, unknown command or possible write. The same inspect, foreground
prepare, deterministic publication and one-use launch commands apply.

This parent-only route applies to the reviewed source-revision restart that
completed its Thinker probe and combined original read, but failed the separate
section-read validator. It does not recover unknown execution, writes, missing
terminal events or arbitrary failed restarts. Ordinary checkpoint/resume guards
remain unchanged.

The operator supplies a binding to the prior source/config, committed admission
and consumed attempt, frozen prior review/capture references, stopped registry,
corrected source/config and owner's scoped instruction. Source, candidate,
inputs, original checkpoints, complete allowed public read effects, held
capabilities and retired processes/frontends are checked independently. Diagnosis
text is not authority. Read-only SQLite inspection may update transient shared
memory read marks; it writes no event, task, source or receipt.

Use the qualified Python environment and actual paths:

```sh
python3 controller/native_loopctl.py --config CONFIG.json inspect-read-recovery --binding BINDING.json
python3 controller/native_loopctl.py --config CONFIG.json prepare-read-recovery --binding BINDING.json
```

Inspection starts nothing. Preparation uses the unchanged controlling-terminal
boundary, prints one exact `recover ...` instruction, and admits the exact source
only after that input. It starts no model and accepts/integrates no task. The
old source admission and failed dispatch remain immutable and consumed.

One stable failed-parent identity owns one successor relationship; another UUID
cannot create a second successor. Reconciliation and source admission are
separate append-only Store events, revalidated under native startup/writer locks
and transactions. They do not report successful rehydration. Observed Doer
restore lineage is a checkpoint projection, not proof that its original reread
completed. The next native restart must still probe and reread originals.

SQLite commitment and file publication are separate boundaries. After a lost
publication/response, regenerate only the exact committed projection:

```sh
python3 controller/native_loopctl.py --config CONFIG.json publish-read-recovery --binding BINDING.json
```

An orphan file grants no authority. Publication cannot dispatch. Do not overwrite
an inconsistent file or delete evidence to make it publish. Once the projection
is verified, the existing restart command consumes it once:

```sh
python3 controller/native_loopctl.py --config CONFIG.json resume-runtime --prepared PREPARED.json --prepared-sha256 SHA256 --check
python3 controller/native_loopctl.py --config CONFIG.json resume-runtime --prepared PREPARED.json --prepared-sha256 SHA256
```

Launch revalidates the current state/source and committed projection and writes
its intent before external effects. A crash or failed turn after that intent
remains held. Never replay it or interpret dead processes as proof of no effects.
The existing three-role model/effort, isolation, tool/time budgets and final human
gate apply. A check-only result, restored terminal or deterministic transport test
is not actual native completion or release qualification.
