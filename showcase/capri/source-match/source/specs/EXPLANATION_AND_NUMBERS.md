# Explain focused contexts and handoffs

The presentation should sell the open-source idea by teaching the mechanism clearly and making its limits inspectable. It must not sell a native result that has not happened.

## Mechanism to show

A growing conversation can carry repeated investigation, irrelevant tool output and outdated alternatives into later work. A scoped handoff supplies the original request, current correction, relevant source, allowed changes and acceptance checks to the next role. Authoritative originals stay retrievable. Review compares the candidate against those originals and the evidence.

Use Plan/Build/Review as the comic's teaching labels and connect them to the real Thinker/Doer/Reviewer roles. Preserve ordered stages, one write owner and an uncertainty/hold branch. The current source is a three-session workflow; do not imply simultaneous uncontrolled writers or automatic human approval.

Include a concrete correction: blank input becomes Untitled, while case and internal spaces are preserved, non-strings are rejected, and the allowed change is label.py only. This is an authored teaching example. It is not an instruction to create/change that file in the repository or a documentary recording of successful native retention.

## Editable worked example

The canonical data is assets/data/context-budget.json. Six assumed input requests:

| Method | Input per call, thousands of tokens | Total |
| --- | --- | --- |
| Growing history | 10, 18, 26, 34, 42, 50 | 180k |
| Curated session | 10, 12, 14, 16, 18, 20 | 90k |
| Scoped roles | 10, 8, 10, 12, 8, 12 | 60k |

Scoped versus growing: (180 − 60) / 180 = **66.7% lower assumed input**. Scoped versus curated: (90 − 60) / 90 = **33.3% lower assumed input**. The curated single-session example is also 50% below growing history. These are illustrative inputs, not measured CAPRI savings or a controlled proof of equal quality.

Keep the assumptions near the number, with all six calls available through a native expander or transcript. Scoped inputs include assumed role instructions and handoffs. Extra coordination, output, retries, compaction and recovery matter in actual accounting. Fewer raw input tokens do not imply the same percentage of dollar savings when cache hits and output differ.

Do not animate invented live counters or attach fake speed, accuracy, retention, cache-hit or context-occupancy scores. Exact active occupancy stays UNKNOWN where the source cannot establish it. Preserve missing/unrun outcomes.

## Cache and long context

Prefix caching reuses eligible repeated computation and can change cost/latency. It does not create semantic memory, free context-window capacity or guarantee factual retention. A long prompt does not deterministically cause instruction deletion. Context selection and lossy compaction can omit important information if authored poorly; explicit packets and original-source rereads address that risk.

Retain a short counterexample explaining that a longer stable cached prefix can be cheaper than several shorter mostly uncached requests, depending on rates, outputs and coordination. Do not invent current prices. The source's existing benchmark protocol defines real accounting and unrun comparisons.

Keep empirical claims separate from this illustration. Current main has successful offline CI but remains experimental/BLOCKED for native launch/recovery qualification. The three-arm pilot and historical comparison rows are not completed savings measurements. This task does not run models, alter the recovery state or relax runtime budgets.

## Supporting primary reading

- Anthropic, Effective context engineering for AI agents: https://www.anthropic.com/research/effective-context-engineering-for-ai-agents
- Anthropic, How we built our multi-agent research system: https://www.anthropic.com/research/multi-agent-research-system
- The repository's current docs/BENCHMARK_PROTOCOL.md, with a pinned intake copy supplied.
- GitHub's native collapsed-section documentation: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections

These explain design choices and tradeoffs. Do not transfer vendor benchmark percentages to CAPRI or call the 180k/60k scenario a research finding.

