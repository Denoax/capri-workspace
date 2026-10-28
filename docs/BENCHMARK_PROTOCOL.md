# Measuring CAPRI

Status: protocol and offline report tooling. **There is no completed native comparison proving that CAPRI is better or cheaper.** Exact active context occupancy remains UNKNOWN. The previous original/v2/v3/v4 evaluation records are historical conditions and must not be pooled with new source revisions.

## Separate the questions

| Question | Comparison | What it can establish |
| --- | --- | --- |
| Does managed context help within CAPRI? | Same three-role pipeline, context policy off versus on | The effect of the context policy within the tested configuration |
| Does the full workflow help compared with ordinary Codex? | One Codex session versus three-role baseline versus three-role managed context | The cost/quality tradeoff of each complete recipe |
| Does recovery work? | Named compaction, reread, replacement and restart qualification cases | Mechanism reliability; these are not ordinary task-performance scores |

All arms request `gpt-6.1-sol`. Keep the selected three-role medium/medium/high efforts, installed binary/schema, tool environment, initial instructions, task inputs and hidden grader fixed. The single-session recipe must state its effort explicitly. Differences between complete recipes are not causal proof that role count alone explains a result.

## Execution order

1. Finish the supported native launch integration. Fence the preserved incomplete compaction only through the validated stopped route. A scope-preparation receipt still does not authorize model dispatch. Preserve all historical task/counter/event identities.
2. Qualify one disposable native cycle, including actual compaction completion, exact original rereads, role replacement and controller restart. Keep the 240-second/12-tool per-turn AND combined-stage guards and the 60-second compaction limit. Freeze source/profile and the actual report-collection format before measured tasks.
3. Run the separate eight-row A/B mechanism smoke comparison required by the existing plan. Keep all eight scheduled rows, failures, aborts, missing usage and unrun rows. This small fixture set cannot establish general product superiority.
4. Run a first three-arm pilot with four preregistered representative tasks and two repeats per arm: 24 scheduled runs. Use a small bug fix, a change across files, a correction after irrelevant context, and a longer multi-step change. Freeze exact issues, baseline repository commits, checks and held-out tests before dispatch. Randomize arm order within each task/repeat using a recorded seed. Budget and source-bind this pilot separately; do not quietly broaden an admitted stage or run it before native readiness.
5. Review the pilot for regressions and measurement coverage before expanding to diverse real repository tasks. Report confidence intervals and task-level paired outcomes when the sample supports them. Neither four tasks nor a hand-selected showcase justifies a universal savings claim.

The three-arm pilot schedule in `evaluation/benchmark-v1/schedule.json` is deliberately unrun. Task definitions are not frozen yet; it is a planning artifact, not executable model-launch authority. A parent-owned deterministic grader must be absent from model mounts and repository history available to the worker. Keep gold patches, future commits and expected hidden answers out of model/search access.

Record cache-hit exposure and arm order. A fresh thread does not guarantee a cold provider cache, and ordinary clients cannot assume they can flush it. Analyze observed cold/warm or mixed cache conditions explicitly; balanced order and repeated tasks help expose this effect but do not prove it is eliminated.

## Measurement contract

Count every role and all model-backed probes, compactions, recovery rereads, rejected work and charged retries. Count failed/aborted run costs in cost per successful task; never report only the successful paths. Record end-to-end and active wall time separately, tool interactions, human interventions, task outcome, regression failures and isolation/source-scope violations. Use the same predeclared end-to-end resource envelope across complete recipes, while preserving each existing per-stage ceiling. A new experiment budget is explicit source/profile data; it cannot reset an exhausted admitted operation.

Keep raw usage evidence immutable. Deduplicate repeated usage notifications by identity. Cumulative thread snapshots are not individual inference costs: derive a validated cumulative delta for totals, or obtain actual per-request usage. Do not sum both forms. Reasoning output is already part of output accounting when the provider schema defines it that way. Unknown or reset counters remain gaps.

`tools/benchmark_report.py` accepts **already normalized per-inference request rows**, each with thread/request identity, model, evidence reference and disjoint uncached-input, cached-input, cache-write-input and output buckets. The local native collector still needs an adapter proving that conversion and full inference coverage. Until it exists, `usage_complete` stays false and savings stay null. A supplied JSON flag is not independent proof; retain original evidence and review the converter.

The report's peak request input is a footprint measurement, not exact active occupancy. Cache hits reduce repeated-prefix computation and price; they do not create semantic memory or prevent hallucinations. Cached tokens are not free space in the context window. Record original-requirement retention with held-out behavioral checks, not an ACK repeating hashes supplied in the prompt.

## Money

The versioned price profile uses the official GPT-6.1 Sol Standard API token rates as of 23 October 2026, with per-request long-context and cache-write tiers. It produces **token API-equivalent estimates only**. It excludes tool, infrastructure and human cost and is not your ChatGPT subscription bill or credit consumption. Actual billed cost remains null until a matching billing source is available. Record native account usage/credits separately where supported; do not migrate authentication or billing to obtain a number.

```sh
python3 tools/benchmark_report.py evaluation/benchmark-v1/schedule.json
python3 -B -m unittest discover -s tests -v
```

The unrun schedule produces no savings percentage. The twelve offline analyzer tests exercise arithmetic and rejection behavior; none is a native benchmark result.

## Research basis

- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) supports tracking outcome, latency, token use and cost on stable tasks, using suitable deterministic, model and human graders. Our choice is deterministic task grading plus retained execution traces; no paid judge is added to the product loop.
- [Anthropic: Harness design for long-running apps](https://www.anthropic.com/research/harness-design-long-running-apps) describes structured handoffs and a planner/generator/evaluator architecture, but also the overhead of resets and opportunities to simplify scaffolding. This supports measuring CAPRI's overhead, not assuming a Claude result transfers to Sol.
- [Harness-Bench, revised 15 October 2026](https://arxiv.org/abs/2605.27922) treats the model/harness configuration as the evaluation unit and records artifacts, traces, usage and validators. It is external research, not a CAPRI benchmark result.
- [SWE-bench documentation](https://www.swebench.com/SWE-bench/) provides a model of repository/issue/patch/test evaluation. We borrow controlled grading and isolated environments; our small fixtures are not SWE-bench scores.
- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching), [model rates](https://developers.openai.com/api/docs/models/gpt-6.1-sol), and [pricing](https://developers.openai.com/api/docs/pricing) define the accounting reference. Native schema and billing compatibility still require evidence from the installed CLI/account.


## Agentic Loop Prompting: rationale and tradeoffs

CAPRI uses focused stage inputs and explicit retained requirements to limit replayed exploration, followed by a separate checking pass. This is a design inference from the implementation and the techniques below, not evidence of CAPRI superiority or a measured quality/cost gain.

[Building effective agents](https://www.anthropic.com/research/building-effective-agents) describes staged workflows and evaluation when criteria are clear, with added latency/cost tradeoffs. [Effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) discusses focused contexts, retrieval and condensed results alongside other approaches. [When to fold subagents into the main loop](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop) explains shared-context benefits and lossy-handoff/coordination costs. These primary sources support conditional mechanisms; their examples or percentages are not CAPRI results.

A curated single session can match or beat scoped input. Additional handoffs must earn their cost, and separate review can share model blind spots. CAPRI needs its own matched end-to-end comparison before claiming relative cost, speed or quality. Stages are ordered, with one write owner and a human integration decision.
