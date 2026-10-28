"""Native accessible mathematical and fixture explanation from the same model."""
from pathlib import Path
import json
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
def main(model=None):
    m=model or json.loads((ROOT/'showcase/capri/story/model-results.json').read_text());k=lambda v:f'{v//1000}k';g=m['derivations']['growing'];c=m['derivations']['curated'];t=m['total_assumed_input_tokens']
    text=f'''# Context inputs, coordination and evidence

**Illustrative inputs — not a CAPRI benchmark.** The [canonical six-call assumptions](../showcase/capri/source-match/source/assets/data/context-budget.json) remain unchanged. The [story configuration](../showcase/capri/story/story.json) refers to them; the [generated model](../showcase/capri/story/model-results.json) feeds Markdown, graph geometry and local controls through `tools/capri_context_budget.py`.

## Inputs per request

All amounts are assumed input tokens. Role instructions and handoff inputs are already budgeted in scoped calls. They have not been measured or validated as sufficient for equal-quality work.

| Request | Growing history | Curated single session | Scoped roles |
| ---: | ---: | ---: | ---: |
'''+''.join(f"| {r['request']} | {r['values']['growing']:,} | {r['values']['curated']:,} | {r['values']['scoped']:,} |\n" for r in m['requests'])+f'''| **Total** | **{t['growing']:,}** | **{t['curated']:,}** | **{t['scoped']:,}** |

For this append illustration, `I = nB + g × n(n−1)/2`. With {m['calls']} calls, initial {k(g['initial'])} and {k(g['increment'])} retained per continuation, growing input is `{m['calls']}×{k(g['initial'])} + {k(g['increment'])}×{g['retained_steps']} = {k(t['growing'])}`. The curated example uses {k(c['increment'])} retained per continuation: `{m['calls']}×{k(c['initial'])} + {k(c['increment'])}×{c['retained_steps']} = {k(t['curated'])}`. Scoped input is its listed sum, {k(t['scoped'])}. This is an explanation of these assumptions, not a rule that ordinary chats must grow this way.

`(180−60)/180 = {m['scoped_vs_growing_percent_lower']}%` and `(90−60)/90 = {m['scoped_vs_curated_percent_lower']}%` mean **lower assumed input**. Curated prompting also improves the example. Equal calls do not establish equal work, sufficient information or equal quality. A well-managed single session may match or beat scoped input. More roles do not inherently save tokens.

Cumulative input is a sum across requests, not a simultaneously filled context window. Listed peak request inputs are '''+', '.join(p['label']+' '+k(p['peak_request']) for p in m['policies'])+'''. Neither those footprints nor their sum establishes exact native active occupancy; it remains **UNKNOWN** where unestablished.

## Additional coordination input

Let H be input beyond the scoped scenario's already-included instructions and handoffs. Scoped input is `60k + H`; its margin versus curated is `30k − H`. Do not count an included handoff twice.

| Additional H | Scoped total | Relation to curated 90k |
| ---: | ---: | :--- |
'''+''.join(f"| {k(r['additional_input'])} | {k(r['scoped_total'])} | "+('equal assumed input' if r['relation']=='equal' else f"{r['percent']}% {r['relation']} assumed input")+' |\n' for r in m['overhead_samples'])+f'''
The raw-input advantage disappears at H={k(m['break_even_additional_input'])}. That is not a cost, latency or quality break-even. Additional calls also have output and time, and every extra role/probe/retry/compaction/recovery attempt belongs in evaluation.

## Caching and money

Prefix caching reuses matching computation; it does not delete instructions, create semantic memory or free logical context capacity. Context selection can avoid replaying irrelevant material; lossy summaries can omit useful requirements. Keep authoritative originals available for review. Do not infer that every long prompt automatically drops instructions or that a fresh session guarantees retention.

The old toy example is `50k + 0.05×130k = {weighted_thousands(m['cache_counterexample']['growing_weighted_units'])}k` normalized weighted units versus 60k assumed uncached scoped inputs. It deliberately excludes cache-write premiums, output and actual observations. The 0.05 coefficient is hypothetical, not a current complete provider price model. It only shows why fewer raw tokens do not determine price order.

Actual accounting needs disjoint ordinary-input, cached-read, cache-write and output buckets with applicable model/request tiers, across every attempt. Tools, infrastructure, latency and human work are separate dimensions. Use the preserved [benchmark protocol](BENCHMARK_PROTOCOL.md); comparison rows remain unrun and missing usage stays missing. No native/model/paid experiment is launched by this presentation.

[Visual story and controls](VISUAL_STORY.md) · [Fixture explanation](CAPRI_EXPLAINS.md) · [Current qualification](STATUS.md).
'''
    (ROOT/'docs/CONTEXT_BUDGET.md').write_text(text)
    explanation='''# CAPRI — Agentic Loop Prompting: what the handoff carries

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
'''
    (ROOT/'docs/CAPRI_EXPLAINS.md').write_text(explanation+'\n\n## Agentic Loop Prompting: rationale and tradeoffs'+'\n\nCAPRI uses focused stage inputs and explicit retained requirements to limit replayed exploration, followed by a separate checking pass. This is a design inference from the implementation and the techniques below, not evidence of CAPRI superiority or a measured quality/cost gain.\n\n[Building effective agents](https://www.anthropic.com/research/building-effective-agents) describes staged workflows and evaluation when criteria are clear, with added latency/cost tradeoffs. [Effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) discusses focused contexts, retrieval and condensed results alongside other approaches. [When to fold subagents into the main loop](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop) explains shared-context benefits and lossy-handoff/coordination costs. These primary sources support conditional mechanisms; their examples or percentages are not CAPRI results.\n\nA curated single session can match or beat scoped input. Additional handoffs must earn their cost, and separate review can share model blind spots. CAPRI needs its own matched end-to-end comparison before claiming relative cost, speed or quality. Stages are ordered, with one write owner and a human integration decision.\n')
def weighted_thousands(text):return format(Decimal(text)/Decimal(1000),'.1f')
if __name__=='__main__':main()
