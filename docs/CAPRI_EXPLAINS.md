# Capri explains the handoff

[Root comic](../README.md#the-loop) · [Complete static README](README_STATIC.md) · [Worked assumptions](CONTEXT_BUDGET.md)

The artwork illustrates the contracts. It is not a controller recording or a completed native qualification run. Plan/Build/Review are teaching labels for Thinker/Doer/Reviewer. The final human decision remains separate.

## 1. Plan with authoritative inputs

Thinker selects the request, latest correction, relevant source, edit scope and acceptance checks. Exploration and logs need not fill every later context, but authoritative originals stay retrievable. An incomplete small packet can be worse than a carefully curated single session. The original source and task still govern.

## 2. Carry the current correction

**Authored fixture A illustration, not an observed model failure.** The [original request](../evaluation/fixtures/A/INITIAL.md) permits changing only `label.py`; outer whitespace is trimmed, case and internal whitespace are preserved, non-strings raise `TypeError`, and blanks originally use `Anonymous`. The [latest correction](../evaluation/fixtures/A/CORRECTION.md) changes blanks to **`Untitled`**. Compatible rules remain.

<details>
<summary>What should <code>label("  MiX  Case  ")</code> return?</summary>

`"MiX  Case"`: preserve the internal double space and case. Whitespace-only input instead becomes `"Untitled"`; `None` raises `TypeError`. These are expected checks, not observed trial results.

</details>

An incomplete authored brief—“Trim text; use Anonymous for blanks”—carries a superseded rule and omits compatible constraints. A complete handoff says:

> Change `label.py` only. Trim outer whitespace; preserve case and internal spaces. Latest correction: blank/whitespace-only input returns `Untitled`. Non-strings raise `TypeError`. Keep the original request, correction and acceptance checks retrievable.

Information missing from that brief was omitted during packing. Prefix caching did not delete it. [Selection, compaction and caching](CONTEXT_BUDGET.md#three-different-mechanisms).

## 3. Build a scoped candidate

Doer works within the allowed source and returns the patch, checks, uncertainty and known limits. Inside a role, tool feedback supports inspect → act → observe → next permitted action. That inner loop does not grant a new task, ownership or release authority.

## 4. Review against the request

Reviewer gets the request, correction, candidate and evidence in a checking context. Separate conversations do not establish statistical independence or eliminate shared model blind spots. A label saying “reviewed” proves little without concrete findings and check evidence. [Architecture](../ARCHITECTURE.md).

## 5. Hold uncertain effects

Ordered stages have **one write owner**. Separate sessions are not simultaneous uncontrolled editors. Uncertain execution effects hold for source, ownership and effect reconciliation; a screenshot, passing test or return receipt does not silently resume the task.

## 6. Return the decision

Thinker reports findings, checks and limits. **You decide what ships.** Formal outcomes stop at `AWAITING_HUMAN`; replay in the artwork is a teaching loop, not automatic approval or another runtime task.

## What is established here?

The presentation explains existing source contracts and a transparent arithmetic example. It does not measure retention, speed, savings, cost, quality or exact active occupancy. Current main includes newer V3 recovery work and successful offline CI at its recorded base, while native launch/recovery qualification remains **experimental/BLOCKED**. Existing comparison denominators and unrun rows remain unchanged. [Current status](STATUS.md) · [Benchmark protocol](BENCHMARK_PROTOCOL.md).

[Sources, character reconstruction and local companion](SOURCE_MATCH.md) · [Actual implementation guide](../IMPLEMENTATION_README.md).
