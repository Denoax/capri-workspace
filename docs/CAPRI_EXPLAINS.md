# CAPRI — Agentic Loop Prompting: what the handoff carries

CAPRI separates planning, coding and checking into ordered Codex sessions. The brief carries current decisions, relevant source, allowed changes and acceptance checks. One worker writes; the reviewer compares the candidate with the request and evidence; findings return through Thinker to the human decision. Separate contexts do not guarantee better answers or remove shared model blind spots.

## An authored correction example

The [original request](../evaluation/fixtures/A/INITIAL.md) asks for outer trimming while preserving case and internal spaces, non-string TypeError and changes only to `label.py`. The [latest correction](../evaluation/fixtures/A/CORRECTION.md) changes blank output from Anonymous to Untitled. Compatible original rules remain authoritative.

An incomplete teaching brief says: “return Untitled for blanks.” That omits scope, whitespace, case and type requirements. This is an authored example of lost information, **not an observed model failure** and not caching deleting instructions.

A complete packet includes:

- Original request and current correction, with retrievable source paths.
- Scope: `label.py` only.
- Trim outer whitespace; preserve case and internal spaces.
- Blank → `Untitled`; non-strings → `TypeError`.
- Expected checks, then candidate, results and known limits.

| Input/check | Expected result |
| :--- | :--- |
| `"   "` | `"Untitled"` |
| `"  MiX  Case  "` | `"MiX  Case"` |
| `None` | raises `TypeError` |
| Changed files | only `label.py` |

The reaching-hands lesson places this correction at the source contact. Skull/sword/rain holds the retained brief; the scanline cat accompanies checking. Those are credited teaching scenes, not native traces or security/quality guarantees. The black-hole graph uses assumed input totals; no artwork measures occupancy or model performance.

## Choose the tradeoff

One ordinary session is often appropriate for a short, clear change. Explicit handoffs are useful when a plan, scoped implementation and separate checking need inspectable boundaries. They also add coordination, output, time and possible shared errors. The [input illustration and sensitivity](CONTEXT_BUDGET.md) are arithmetic, not proof that this workflow is cheaper, faster or better at requirements retention.

[Interactive visual story](VISUAL_STORY.md#local-companion) · [Architecture](../ARCHITECTURE.md) · [Benchmark protocol](BENCHMARK_PROTOCOL.md) · [Native status](STATUS.md).


## Agentic Loop Prompting: rationale and tradeoffs

CAPRI uses focused stage inputs and explicit retained requirements to limit replayed exploration, followed by a separate checking pass. This is a design inference from the implementation and the techniques below, not evidence of CAPRI superiority or a measured quality/cost gain.

[Building effective agents](https://www.anthropic.com/research/building-effective-agents) describes staged workflows and evaluation when criteria are clear, with added latency/cost tradeoffs. [Effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) discusses focused contexts, retrieval and condensed results alongside other approaches. [When to fold subagents into the main loop](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop) explains shared-context benefits and lossy-handoff/coordination costs. These primary sources support conditional mechanisms; their examples or percentages are not CAPRI results.

A curated single session can match or beat scoped input. Additional handoffs must earn their cost, and separate review can share model blind spots. CAPRI needs its own matched end-to-end comparison before claiming relative cost, speed or quality. Stages are ordered, with one write owner and a human integration decision.
