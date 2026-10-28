# Context inputs, coordination and evidence

**Illustrative inputs — not a CAPRI benchmark.** The [canonical six-call assumptions](../showcase/capri/source-match/source/assets/data/context-budget.json) remain unchanged. The [story configuration](../showcase/capri/story/story.json) refers to them; the [generated model](../showcase/capri/story/model-results.json) feeds Markdown, graph geometry and local controls through `tools/capri_context_budget.py`.

## Inputs per request

All amounts are assumed input tokens. Role instructions and handoff inputs are already budgeted in scoped calls. They have not been measured or validated as sufficient for equal-quality work.

| Request | Growing history | Curated single session | Scoped roles |
| ---: | ---: | ---: | ---: |
| 1 | 10,000 | 10,000 | 10,000 |
| 2 | 18,000 | 12,000 | 8,000 |
| 3 | 26,000 | 14,000 | 10,000 |
| 4 | 34,000 | 16,000 | 12,000 |
| 5 | 42,000 | 18,000 | 8,000 |
| 6 | 50,000 | 20,000 | 12,000 |
| **Total** | **180,000** | **90,000** | **60,000** |

For this append illustration, `I = nB + g × n(n−1)/2`. With 6 calls, initial 10k and 8k retained per continuation, growing input is `6×10k + 8k×15 = 180k`. The curated example uses 2k retained per continuation: `6×10k + 2k×15 = 90k`. Scoped input is its listed sum, 60k. This is an explanation of these assumptions, not a rule that ordinary chats must grow this way.

`(180−60)/180 = 66.7%` and `(90−60)/90 = 33.3%` mean **lower assumed input**. Curated prompting also improves the example. Equal calls do not establish equal work, sufficient information or equal quality. A well-managed single session may match or beat scoped input. More roles do not inherently save tokens.

Cumulative input is a sum across requests, not a simultaneously filled context window. Listed peak request inputs are Growing history 50k, Curated single session 20k, Scoped roles 12k. Neither those footprints nor their sum establishes exact native active occupancy; it remains **UNKNOWN** where unestablished.

## Additional coordination input

Let H be input beyond the scoped scenario's already-included instructions and handoffs. Scoped input is `60k + H`; its margin versus curated is `30k − H`. Do not count an included handoff twice.

| Additional H | Scoped total | Relation to curated 90k |
| ---: | ---: | :--- |
| 0k | 60k | 33.3% lower assumed input |
| 15k | 75k | 16.7% lower assumed input |
| 30k | 90k | equal assumed input |
| 45k | 105k | 16.7% higher assumed input |

The raw-input advantage disappears at H=30k. That is not a cost, latency or quality break-even. Additional calls also have output and time, and every extra role/probe/retry/compaction/recovery attempt belongs in evaluation.

## Caching and money

Prefix caching reuses matching computation; it does not delete instructions, create semantic memory or free logical context capacity. Context selection can avoid replaying irrelevant material; lossy summaries can omit useful requirements. Keep authoritative originals available for review. Do not infer that every long prompt automatically drops instructions or that a fresh session guarantees retention.

The old toy example is `50k + 0.05×130k = 56.5k` normalized weighted units versus 60k assumed uncached scoped inputs. It deliberately excludes cache-write premiums, output and actual observations. The 0.05 coefficient is hypothetical, not a current complete provider price model. It only shows why fewer raw tokens do not determine price order.

Actual accounting needs disjoint ordinary-input, cached-read, cache-write and output buckets with applicable model/request tiers, across every attempt. Tools, infrastructure, latency and human work are separate dimensions. Use the preserved [benchmark protocol](BENCHMARK_PROTOCOL.md); comparison rows remain unrun and missing usage stays missing. No native/model/paid experiment is launched by this presentation.

[Visual story and controls](VISUAL_STORY.md) · [Fixture explanation](CAPRI_EXPLAINS.md) · [Current qualification](STATUS.md).
