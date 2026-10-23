# Capri explains CAPRI

[Back to the README](../README.md) · [Complete static edition](README_STATIC.md) · [What is proven here?](#what-is-proven-here)

Capri's speech is original teaching copy, not a quotation from the show. The pictures are illustrations, not controller screenshots. V7's transparent actor uses an authorized AI-edited pose with authored hand articulation; [asset provenance and limits](CAPRI_ACTOR.md). The user-described *Dr. STONE* explanation premise informs the character-as-instructor approach; no shots, dialogue or audio are reproduced from that series. [Design references](DESIGN_REFERENCES.md).

<picture>
  <source media="(max-width: 600px)" srcset="../showcase/capri/explainer/comic-mobile.svg">
  <img src="../showcase/capri/explainer/comic.svg" alt="Complete static comic: plan, build, review, report to human; uncertain effects hold. Transcript follows." width="1200">
</picture>

<a id="why-select-context"></a>

## 1. Why select context?

> Capri: “One task. Three focused conversations. I'll show you what moves between them.”

A context is the information available to a role: instructions, messages, source and tool output. A long conversation can mix original requirements with corrections, abandoned approaches and logs. Select information by purpose while keeping authoritative originals retrievable. The goal is relevant working material, not the shortest possible prompt.

Long-context research found retrieval sensitivity to where relevant information appears in the tested tasks; it does not establish that longer context always fails or that CAPRI improves retention. [Lost in the Middle](https://arxiv.org/abs/2307.03172v3). Anthropic describes context engineering as curating the tokens used during inference; its recommendations are external guidance, not CAPRI results. [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

CAPRI's source distinguishes cumulative usage, recent-request footprint and cached input from exact active occupancy, which remains **UNKNOWN** when it cannot be established. Provider prefix caching reuses computation; it does not remove instructions or make cached input cease to occupy context. [Context implementation](../controller/loop/context.py) · [Architecture](../ARCHITECTURE.md).

## 2. Give each role a purpose

> Capri: “Plan here. Build here. Review with fresh eyes.”

**Thinker:** research, define scope and acceptance checks, identify relevant source and unresolved questions. **Doer:** implement the scoped candidate and return checks and limits. **Reviewer:** examine the request, corrections, candidate and evidence in a fresh context. **Thinker:** turn the findings into a report for your decision.

These are separate sessions with controlled stage order and one write owner, not a swarm of simultaneous editors. The selected profile requests the same model for all three roles; separate conversations do not eliminate shared model blind spots or establish statistical independence. [Native profile](../NATIVE_PROFILE.md) · [Stage and ownership contracts](../ARCHITECTURE.md).

<a id="3-carry-decisions-with-the-packet"></a>

## 3. Carry decisions with the packet

> Capri: “Carry the decisions, sources and checks forward.”

A useful packet binds the task to its original request, latest corrections, source identity and applicable instructions; defines allowed changes and acceptance checks; and includes open questions, evidence and uncertainty. Exploration can stay local, but recipients must be able to retrieve authoritative originals. CAPRI checkpoints bind these inputs; a model summary alone is not sufficient authority. [Checkpoint and context code](../controller/loop/context.py) · [Native original-input handling](../controller/loop/native.py).

Within an active role, tool feedback forms a smaller loop: **inspect → act → observe → next permitted step**. This inner loop does not grant a new role, a new task or permission beyond the frozen task boundary. Stage transitions and human decisions belong to the outer workflow. [Architecture](../ARCHITECTURE.md).

See the [worked six-request comparison](CONTEXT_BUDGET.md) for context growth, a strong curated-single-session baseline, cache sensitivity and authored examples of omitted requirements.

## 4. Keep the latest correction

> Capri: “The latest correction travels with the task.”

**Fixture A teaching example; no live run is shown.** The original request permits changes only to `label.py`. Trim outer whitespace, preserve case and internal whitespace, use `Anonymous` for blanks and raise `TypeError` for non-strings. The latest correction changes only the blank label to **`Untitled`**. Every compatible earlier rule still applies. The committed fixture is an input, not a finished implementation. [Original](../evaluation/fixtures/A/INITIAL.md) · [Correction](../evaluation/fixtures/A/CORRECTION.md) · [Fixture source](../evaluation/fixtures/A/label.py).

<details>
<summary><strong>Check your prediction:</strong> What should <code>label("  MiX  Case  ")</code> return?</summary>

`"MiX  Case"`. Removing the internal double space or changing case would violate the original request. A whitespace-only input instead becomes `"Untitled"`; `None` raises `TypeError`. These are expected checks, not observed trial results.

</details>

The handoff needs both the correction and compatible original rules. “Implement a label function” is too vague to preserve them. Doer returns candidate + checks + limits; Reviewer compares that result with the authoritative inputs.

## 5. Review against the request

> Capri: “Check the patch against the request.”

Fresh review context gives the Reviewer a checking purpose rather than continuing the builder's conversation. It still needs the request, corrections, scoped source/candidate, acceptance criteria and evidence. Findings should identify what was checked, what failed and what remains unverified. Multiple agents can fail through system design, inter-agent alignment and task verification; a reviewer label alone proves nothing. [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657v3).

## 6. Return the decision to the human

> Capri: “You decide what ships.”

Thinker reports findings, checks and limits. Formal outcomes stop at `AWAITING_HUMAN`; no successor task starts automatically. Uncertain execution effects hold for source, owner and effect reconciliation. An illustration, passing check or review receipt is not acceptance. [Architecture](../ARCHITECTURE.md).

<a id="when-to-try-it"></a>

## When to try it

Consider CAPRI for work that needs research, evolving requirements or independently checkable outputs. Focused contexts may reduce re-explanation and make handoffs easier to inspect. Those are design hypotheses here; net retention, speed, token use and cost benefits have not been demonstrated.

Coordination adds work and consumes tokens/time. A small, clear change can fit one well-structured session. Research on agent-system scaling reports task- and coordination-dependent outcomes; it does not show that adding agents always helps or that this implementation is faster. [Towards a Science of Scaling Agent Systems](https://arxiv.org/abs/2512.08296v3).

<a id="what-is-proven-here"></a>

## What is proven here?

The source defines staged roles, original-input binding, one write owner and human decision boundaries. The new guide illustrates those contracts. Focused presentation checks verify local links, source integrity, media timing and static alternatives; they do not qualify the native runtime or prove product efficacy.

| Evidence set | Scheduled | Started | Graded | Aborted | Unrun |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Original v1 comparison | 8 | 2 | 1 | 1 | 6 |
| Repaired-source v2 comparison | 8 | 0 | 0 | 0 | 8 |

The single graded v1 row passed **8/8 held-out checks**. The separate M0 canary is excluded from those denominators. The original and repaired-source schedules remain separate. This presentation does not execute trials or alter evaluation evidence. [Frozen evaluation](../EVALUATION.md).

Current-source native lifecycle/research/recovery qualification and independent final review remain pending at the recorded cutoff. Approved-main [CI run 39964880216](https://github.com/Denoax/capri/actions/runs/39964880216) failed collector confinement; the required runtime suite was skipped. No green runtime result is claimed. [Status](STATUS.md).

V6 is a testing-branch presentation candidate. V5 was not merged or accepted. Approved main, runtime, profiles, dependency locks and CI are preserved. The repository is private; code licensing and public character-art redistribution remain unresolved. [Assets and rights](ASSETS.md).

[Try the offline quickstart](QUICKSTART.md) · [Character art](AFTERIMAGE.md) · [Readable static README](README_STATIC.md)
