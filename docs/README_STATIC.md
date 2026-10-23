<!-- Generated from README.md by tools/build_capri_static.py. -->
<img src="../showcase/capri/hero.png" alt="CAPRI — her green face, expressive eyes, jagged silhouette and long magenta hands." width="1000">

**Give the plan, the patch and the review their own context.**

CAPRI coordinates three Codex sessions: one to research and scope, one to build a candidate, and one to review it against the request. Explicit handoffs carry the decisions forward. You decide what ships.

[Start](#quickstart) · [The loop](#the-loop) · [Evidence](#evidence) · [Field notes](#field-notes)

[Static edition](../docs/README_STATIC.md) · [Development status](../docs/STATUS.md) · [Art credits](../docs/ASSETS.md)

<a id="the-loop"></a>

## Follow the handoff

<picture>
  <source media="(max-width: 760px)" srcset="../showcase/capri/scene/portrait-static.svg">
  <img src="../showcase/capri/scene/wide-static.svg" alt="Four-beat lesson: Capri explains the scoped brief, points to blank → Untitled, inspects request/patch/evidence, then returns the decision to the human. One write owner; uncertain effects hold. Complete transcript follows." width="1200">
</picture>

[Read all four beats without motion](../docs/README_STATIC.md#the-loop) · [Six lessons and native transcript](../docs/CAPRI_EXPLAINS.md)

1. **Plan — Thinker:** select the original request, latest corrections, relevant source, allowed changes and acceptance checks. Keep originals retrievable.
2. **Build — Doer:** carry that packet into a scoped candidate. For fixture A, only `label.py` may change; blank text becomes `Untitled`, with the compatible original rules retained. Return the candidate, checks and limits.
3. **Review — Reviewer:** check the request, corrections, patch and evidence together. Fresh context supplies a checking purpose; the same model can still share blind spots. **Uncertain effects hold for reconciliation.**
4. **Decide — Thinker report → you:** findings, checks and limits come back for a human decision. **One write owner; ordered stages.** The teaching replay does not start another task or grant approval. [Implementation boundaries](../ARCHITECTURE.md).

A context contains the instructions, source, history and tool results available to a role. Select it by purpose; keep decisions and authoritative originals available. [Why select context?](../docs/CAPRI_EXPLAINS.md#why-select-context)

<a id="evidence"></a>

## What the numbers do—and do not—show

**Worked example: assumed input tokens, not a measured CAPRI run.** Six requests per policy, including the assumed handoff and review inputs:

| Context policy | Assumed input total |
| :--- | ---: |
| Growing history | 180,000 |
| Curated single session | 90,000 |
| Scoped roles | 60,000 |

Under these assumptions, scoped inputs are **66.7% lower** than growing history and **33.3% lower** than the curated example. Sufficient information and equal answer quality have **not** been established. Good context management helps one session too; agent count alone does not produce these differences. [Six-call table, editable calculator and full assumptions](../docs/CONTEXT_BUDGET.md).

**Fewer inputs do not automatically lower the bill.** In the deliberately hypothetical cache counterexample, 50,000 uncached + 130,000 cached growing-history tokens at relative cached rate `0.05` yield **56,500 weighted units**, below 60,000 all-uncached scoped units. These are normalized example units, not prices or observed usage. Outputs, reasoning charges, tools, retries, time and quality are excluded. [Inspect the cache sensitivity](../docs/CONTEXT_BUDGET.md#reproduce-the-example).

## A correction that must travel

**Illustration from fixture A — expected behavior, not a completed live run.** The first request says `label(text)` trims outer whitespace, preserves case and internal spaces, rejects non-strings, and uses `Anonymous` for blank text. The latest correction changes the blank label to **`Untitled`**; compatible earlier rules remain. Only `label.py` may change. [Original request](../evaluation/fixtures/A/INITIAL.md) · [Correction](../evaluation/fixtures/A/CORRECTION.md).

| Input | Expected check after the correction |
| :--- | :--- |
| `"   "` | `"Untitled"` |
| `"  MiX  Case  "` | `"MiX  Case"` |
| `None` | raises `TypeError` |

**Authored packing examples — not observed model failures.**

> **Incomplete brief:** “Trim text and return Anonymous for blanks.”

This carries a superseded blank rule and omits the internal-space, case, type and scope constraints.

> **Complete handoff:** “Only change label.py. Trim outer whitespace; preserve case and internal whitespace. **Latest correction: blank/whitespace-only input returns Untitled.** Non-strings raise TypeError. Keep the [original request](../evaluation/fixtures/A/INITIAL.md) and [correction](../evaluation/fixtures/A/CORRECTION.md) retrievable.”

The missing rule is absent from the supplied brief; this is information loss during packing, not cache-driven instruction deletion. Prefix caching reuses processing for matching prefixes. It does not delete instructions or remove cached input from logical context. [Context selection, compaction and caching](../docs/CONTEXT_BUDGET.md#three-different-mechanisms).

The Doer's packet carries the correction with the original rules. The Reviewer checks both against the candidate and evidence. A summary saying only “implement a label function” loses the decision that matters. [Walk through the packet](../docs/CAPRI_EXPLAINS.md#3-carry-decisions-with-the-packet).

## When is the extra coordination worth it?

Research-heavy work, evolving requirements and changes with checkable outcomes can benefit from focused roles and explicit handoffs. That is the hypothesis behind CAPRI, **not a measured speed or cost advantage**. Coordination itself takes tokens and time. One well-structured session can suit a small, clear task. Broader research finds outcomes depend on task structure and coordination design; it does not benchmark this project. [Research and limits](../docs/CAPRI_EXPLAINS.md#when-to-try-it).

**Experimental:** original evaluation: **8 scheduled, 2 started, 1 graded, 1 aborted, 6 unrun**. The graded row passed 8/8 held-out checks. Repaired-source comparison: **8 scheduled, 0 started, 8 unrun**. Native qualification and independent final review remain pending at the recorded cutoff. The last recorded testing run failed its isolation prerequisite and skipped the runtime suite; the V8 push is checked separately in the review.  [What is proven here?](../docs/CAPRI_EXPLAINS.md#what-is-proven-here) · [Evaluation](../EVALUATION.md) · [Status](../docs/STATUS.md).

<a id="quickstart"></a>

## Quickstart

<a id="field-notes"></a>

## Field notes

| Open the file | What is inside |
| :--- | :--- |
| [Architecture](../ARCHITECTURE.md) | Ownership, confinement, handoffs and recovery |
| [Implementation guide](../IMPLEMENTATION_README.md) | Existing commands and the native startup path |
| [Evaluation](../EVALUATION.md) | Trial definitions, evidence and comparison limits |
| [Development status](../docs/STATUS.md) | What has and has not been qualified |
| [Contributing](../CONTRIBUTING.md) | How to work on the project |
| [Security](../SECURITY.md) | Boundaries and reporting |


[Browse the documentation by task](../docs/README.md) · [Afterimage: character studies and retained artwork](../docs/AFTERIMAGE.md) · [Still art edition](../docs/AFTERIMAGE_STATIC.md)

**Experimental.** Native lifecycle/recovery qualification, the repaired-source comparison and independent final review remain pending at the recorded source cutoff. Presentation checks do not qualify runtime behavior. [Current limits](../docs/STATUS.md).

No source-bound product demo is shown. The lesson uses three supplied AI-assisted upper-body fan-art poses with authored scene motion, not extracted anime acting or a complete rig. [Pose sources, anchors and motion](../docs/CAPRI_ACTOR.md).

**Mani Marami Milani** · [Sources and edits](../docs/ASSETS.md) · [Presentation references](../docs/DESIGN_REFERENCES.md)

Unofficial Capri-inspired fan project; unaffiliated with CD PROJEKT RED, TRIGGER or Netflix. Code licensing and public character-art redistribution remain unresolved. The approved hero uses BluRei's source 19; source 12 is attributed to emdzejus. Barlow and Barlow Condensed retain their [OFL notice](../showcase/capri/fonts/OFL.txt). Uploader attribution does not establish underlying anime-image ownership.
