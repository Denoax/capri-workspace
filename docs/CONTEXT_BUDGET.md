# Worked context budgets

[Back to the explanation](../README.md#context-and-evidence) · [Current benchmark protocol](BENCHMARK_PROTOCOL.md)

**Illustrative assumptions, not a measured CAPRI run.** Six assumed input calls include the role instructions and handoff material budgeted for each policy. Equal calls do not establish equal work, information sufficiency, output or answer quality.

| Call | Growing history | Curated single session | Scoped roles |
| ---: | ---: | ---: | ---: |
| 1 | 10,000 | 10,000 | 10,000 |
| 2 | 18,000 | 12,000 | 8,000 |
| 3 | 26,000 | 14,000 | 10,000 |
| 4 | 34,000 | 16,000 | 12,000 |
| 5 | 42,000 | 18,000 | 8,000 |
| 6 | 50,000 | 20,000 | 12,000 |
| **Total** | **180,000** | **90,000** | **60,000** |

Scoped versus growing is `(180 − 60) / 180 = 66.7%` lower assumed input. Scoped versus curated is `(90 − 60) / 90 = 33.3%`. The curated single session is itself 50% below growing history. Agent count alone does not cause these differences; the example assumes useful material fits in the listed budgets. Quality equivalence is **untested**. This is neither a tokenizer measurement nor exact active-context occupancy.

## Caching can reverse the cost order

For deliberately hypothetical cached relative rate `r`, weighted input units are `uncached + r × cached`. Assume growing history has 50,000 uncached and 130,000 cached inputs, while all 60,000 scoped inputs miss cache.

| Hypothetical r | Growing weighted units | Scoped weighted units |
| ---: | ---: | ---: |
| 1.00 | 180,000 | 60,000 |
| 0.10 | 63,000 | 60,000 |
| 0.05 | 56,500 | 60,000 |

At `0.05`, the longer cached input is cheaper in this normalized example. None of these coefficients is a provider price or observed cache hit rate. Outputs, real coordination, cache writes, retries, failed work, compaction, recovery, tools, time and human effort are excluded. Real cost/quality comparisons need the accounting in the [current protocol](BENCHMARK_PROTOCOL.md), including missing and unrun outcomes.

## Three different mechanisms

**Context selection** chooses what is supplied to the next request. **Lossy compaction** replaces details with a smaller representation and can omit needed information. **Prefix caching** reuses eligible repeated computation; it does not create semantic memory, remove cached input from logical context, free context capacity or deterministically delete instructions.

A scoped packet should retain the original request, latest corrections, relevant source, constraints and checks. Original sources remain retrievable. A short brief that omits a necessary rule is still wrong. A growing session with careful curation can be the right choice for a small clear task; coordination itself consumes work.

The source distinguishes cumulative usage, request footprint and exact active occupancy. Exact occupancy stays **UNKNOWN** when it cannot be established. No new native run, benchmark, budget adjustment or recovery action is performed here. [Status](STATUS.md) · [Alpha readiness](ALPHA_READINESS.md).

## Reproduce the arithmetic

Canonical inputs: [context-budget.json](../showcase/capri/source-match/source/assets/data/context-budget.json). Calculator: [capri_context_budget.py](../tools/capri_context_budget.py). [Reproducible result](../showcase/capri/source-match/context-budget-results.json).

```sh
python3 tools/capri_context_budget.py
```

The calculator uses exact decimal arithmetic and labels results as assumptions, with no measured-savings field. It does not read model sessions, pricing, credentials or usage telemetry.

## Primary reading

[Anthropic: effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) and [its multi-agent research system](https://www.anthropic.com/research/multi-agent-research-system) discuss relevant design choices and coordination tradeoffs. They do not benchmark CAPRI; vendor percentages are not transferred to this illustration.
