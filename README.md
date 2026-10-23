<img src="showcase/capri/hero.gif" alt="CAPRI — her green face, expressive eyes, jagged silhouette and long magenta hands." width="1000">

**Give the plan, the patch and the review their own context.**

CAPRI coordinates three Codex sessions: one to research and scope, one to build a candidate, and one to review it against the request. Explicit handoffs carry the decisions forward. You decide what ships.

<p align="center">
  <a href="#quickstart"><img src="showcase/capri/identity/nav-start.svg" width="160" alt="Start — offline setup"></a>
  <a href="#the-loop"><img src="showcase/capri/identity/nav-loop.svg" width="160" alt="The loop — roles and handoffs"></a>
  <a href="docs/AFTERIMAGE.md"><img src="showcase/capri/identity/nav-art.svg" width="160" alt="Afterimage — Capri art and motion"></a>
  <a href="#field-notes"><img src="showcase/capri/identity/nav-docs.svg" width="160" alt="Field notes — implementation documentation"></a>
</p>

<p align="center"><a href="docs/README_STATIC.md">Static edition</a> · <a href="docs/STATUS.md">Development status</a> · <a href="docs/ASSETS.md">Art credits</a></p>

<picture>
  <source media="(max-width: 600px)" srcset="showcase/capri/explainer/context-mobile.svg">
  <img src="showcase/capri/explainer/context.svg" alt="Capri: One task. Three focused conversations. Keep the instructions and evidence. Compare one growing conversation with purpose-specific Thinker, Doer and Reviewer contexts; originals remain retrievable." width="1200">
</picture>

A **context** is the information a role can work with: instructions, source, conversation history and tool results. Separate contexts let each role focus on its purpose. Useful handoffs retain the original request, latest corrections, relevant source, constraints and checks; exploratory bulk need not fill every recipient's conversation. [Why select context?](docs/CAPRI_EXPLAINS.md#why-select-context)

<a id="the-loop"></a>

## Follow the handoff

<picture>
  <source media="(max-width: 600px)" srcset="showcase/capri/explainer/guide-mobile.gif">
  <img src="showcase/capri/explainer/guide.gif" alt="Capri guides four beats: Thinker plans with source and acceptance checks; Doer carries the correction into a scoped candidate; Reviewer checks request, patch and evidence; Thinker reports and the human decides. Uncertain effects hold for reconciliation. Complete static lesson follows." width="1200">
</picture>

[Complete static edition](docs/README_STATIC.md) · [All six lessons and native transcript](docs/CAPRI_EXPLAINS.md) · [What is proven here?](docs/CAPRI_EXPLAINS.md#what-is-proven-here)

1. **Thinker → Doer:** the scoped task, original request and corrections, source identity, acceptance checks and open questions.
2. **Doer → Reviewer:** the candidate, checks and known limits, together with the request and constraints. A fresh review context helps separate building from checking; using the same model can still share blind spots.
3. **Reviewer → Thinker → you:** findings and evidence become a report. Current CAPRI stages are ordered with **one write owner**. Separate sessions do not mean simultaneous editing. Uncertain effects hold for reconciliation. [Implementation boundaries](ARCHITECTURE.md).

<details>
<summary><strong>Read all four beats in one still</strong></summary>

<picture>
  <source media="(max-width: 600px)" srcset="showcase/capri/explainer/comic-mobile.svg">
  <img src="showcase/capri/explainer/comic.svg" alt="Complete four-beat static comic. Thinker: task, source and checks. Doer: candidate, checks and limits. Reviewer: findings and evidence. Thinker report: human decision, no automatic next task. Uncertain effects hold." width="1200">
</picture>

The numbered transcript above conveys every stage without waiting for motion. The [full lesson](docs/CAPRI_EXPLAINS.md) explains the inner tool loop and review limits too. GitHub has no custom playback controls here; the static edition embeds no animated media.

</details>

## Keep the next decision supplied with the right context

**Worked example — assumed input tokens, not a measured CAPRI run.** All three policies below have six requests. The budgets include the handoff/review input assumed for each call; whether those budgets preserve sufficient information and answer quality has not been tested.

<picture>
  <source media="(max-width: 600px)" srcset="showcase/capri/context-budget/budget-mobile.svg">
  <img src="showcase/capri/context-budget/budget.svg" alt="Worked example, assumed input tokens over six requests, not a measured CAPRI run. Growing conversation 180000; curated single session 90000; scoped roles 60000. Common zero baseline. Scoped inputs are 66.7 percent below growing and 33.3 percent below curated under these assumptions. This does not measure bills, latency or quality; cache reuse can reverse cost ordering." width="1200">
</picture>

The totals are **180,000 growing-history**, **90,000 curated-single-session** and **60,000 scoped-role input tokens**. Scoped inputs are **66.7% lower** than growing history and **33.3% lower** than the curated single-session example, under these assumptions. Good context management helps a single session too; agent count alone does not produce these differences. [Editable inputs, calculator and full assumptions](docs/CONTEXT_BUDGET.md).

**Fewer input tokens do not automatically mean a lower bill.** In the hypothetical cache case, growing history contains 50,000 uncached + 130,000 cached tokens, while all 60,000 scoped tokens miss cache. At a hypothetical cached relative rate of `0.05`, growing history uses **56,500 weighted input units**, below scoped inputs' **60,000**. These are normalized example units, not prices or observed usage. Outputs, reasoning charges, tools, retries, wall time and quality are excluded.

<details>
<summary><strong>Inspect all six requests and the cache sensitivity</strong></summary>

**Worked example — assumed input tokens, not a measured CAPRI run.**

| Request | Growing history | Curated single session | Scoped role contexts | Scoped role |
| :--- | ---: | ---: | ---: | :--- |
| 1 | 10,000 | 10,000 | 10,000 | Thinker: plan |
| 2 | 18,000 | 12,000 | 8,000 | Doer: inspect |
| 3 | 26,000 | 14,000 | 10,000 | Doer: implement |
| 4 | 34,000 | 16,000 | 12,000 | Doer: checks |
| 5 | 42,000 | 18,000 | 8,000 | Reviewer |
| 6 | 50,000 | 20,000 | 12,000 | Thinker: report |
| **Total** | **180,000** | **90,000** | **60,000** | Six calls included |

Growing history starts at 10,000 tokens and appends 8,000 per request. Curated and scoped budgets assume sufficient relevant material fits in their listed inputs. Largest assumed request: **50,000 → 12,000** tokens; this is an input-footprint illustration, not exact active-context occupancy or a tokenizer measurement. Equal calls do not establish equal work, output or quality.

For hypothetical cached relative rate `r`, weighted input is `uncached + r × cached`:

| Hypothetical r | Growing weighted input | Scoped weighted input | Scoped difference |
| :--- | ---: | ---: | :--- |
| 1.00 | 180,000 | 60,000 | 66.7% lower |
| 0.10 | 63,000 | 60,000 | 4.8% lower |
| 0.05 | 56,500 | 60,000 | 6.2% higher |

Perfect reusable prefixes in the growing case and all misses in the scoped case are deliberately explicit assumptions. None of these coefficients is a current provider price. [Reproduce the arithmetic](docs/CONTEXT_BUDGET.md#reproduce-the-example).

</details>

## A correction that must travel

**Illustration from fixture A — expected behavior, not a completed live run.** The first request says `label(text)` trims outer whitespace, preserves case and internal spaces, rejects non-strings, and uses `Anonymous` for blank text. The latest correction changes the blank label to **`Untitled`**; compatible earlier rules remain. Only `label.py` may change. [Original request](evaluation/fixtures/A/INITIAL.md) · [Correction](evaluation/fixtures/A/CORRECTION.md).

| Input | Expected check after the correction |
| :--- | :--- |
| `"   "` | `"Untitled"` |
| `"  MiX  Case  "` | `"MiX  Case"` |
| `None` | raises `TypeError` |

**Authored packing examples — not observed model failures.**

> **Incomplete brief:** “Trim text and return Anonymous for blanks.”

This carries a superseded blank rule and omits the internal-space, case, type and scope constraints.

> **Complete handoff:** “Only change label.py. Trim outer whitespace; preserve case and internal whitespace. **Latest correction: blank/whitespace-only input returns Untitled.** Non-strings raise TypeError. Keep the [original request](evaluation/fixtures/A/INITIAL.md) and [correction](evaluation/fixtures/A/CORRECTION.md) retrievable.”

The missing rule is absent from the supplied brief; this is information loss during packing, not cache-driven instruction deletion. Prefix caching reuses processing for matching prefixes. It does not delete instructions or remove cached input from logical context. [Context selection, compaction and caching](docs/CONTEXT_BUDGET.md#three-different-mechanisms).

The Doer's packet carries the correction with the original rules. The Reviewer checks both against the candidate and evidence. A summary saying only “implement a label function” loses the decision that matters. [Walk through the packet](docs/CAPRI_EXPLAINS.md#3-carry-decisions-with-the-packet).

## When is the extra coordination worth it?

Research-heavy work, evolving requirements and changes with checkable outcomes can benefit from focused roles and explicit handoffs. That is the hypothesis behind CAPRI, **not a measured speed or cost advantage**. Coordination itself takes tokens and time. One well-structured session can suit a small, clear task. Broader research finds outcomes depend on task structure and coordination design; it does not benchmark this project. [Research and limits](docs/CAPRI_EXPLAINS.md#when-to-try-it).

**Experimental:** original evaluation: **8 scheduled, 2 started, 1 graded, 1 aborted, 6 unrun**. The graded row passed 8/8 held-out checks. Repaired-source comparison: **8 scheduled, 0 started, 8 unrun**. Native qualification and independent final review remain pending at the recorded cutoff. The approved-main CI isolation check failed and the runtime suite was skipped. [What is proven here?](docs/CAPRI_EXPLAINS.md#what-is-proven-here) · [Evaluation](EVALUATION.md) · [Status](docs/STATUS.md).

<a id="quickstart"></a>
<h2>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="showcase/capri/identity/chapter-start-dark.svg">
  <img src="showcase/capri/identity/chapter-start-light.svg" alt="Jack in — quickstart" width="1000">
</picture>
</h2>

Start with offline inspection from your checkout. Linux x86_64, Python 3.11+ with pip/venv, bubblewrap and working user, mount, PID and network namespaces are required.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s controller/tests -v
```

These tests use disposable fixtures and do not call models or require authentication. A failed isolation prerequisite remains a failure.

[Full setup and diagnostics](docs/QUICKSTART.md) · [Host requirements](ENVIRONMENT.md)

<details>
<summary><strong>Before launching native sessions</strong></summary>

Native use additionally requires the qualified Codex CLI 0.163.0/profile, existing local authentication and tmux for ordinary panes. Start from the [preserved implementation guide](IMPLEMENTATION_README.md#native-startup) and an explicitly registered disposable fixture. Later client versions are not implicitly qualified.

[Compatibility](CLIENT_SUPPORT.md) · [Example configuration](examples/config.json)

</details>

<a href="docs/AFTERIMAGE.md"><img src="showcase/capri/identity/afterimage.svg" alt="Afterimage — three actual Capri poses. Open the character art page." width="1000"></a>

[Enter Afterimage](docs/AFTERIMAGE.md) — new expression, hand and movement compositions, one motion interlude, and the retained triptych and poster. [Still art edition](docs/AFTERIMAGE_STATIC.md).

<a id="field-notes"></a>
<h2>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="showcase/capri/identity/chapter-notes-dark.svg">
  <img src="showcase/capri/identity/chapter-notes-light.svg" alt="Field notes" width="1000">
</picture>
</h2>

| Open the file | What is inside |
| :--- | :--- |
| [Architecture](ARCHITECTURE.md) | Ownership, confinement, handoffs and recovery |
| [Implementation guide](IMPLEMENTATION_README.md) | Existing commands and the native startup path |
| [Evaluation](EVALUATION.md) | Trial definitions, evidence and comparison limits |
| [Development status](docs/STATUS.md) | What has and has not been qualified |
| [Contributing](CONTRIBUTING.md) | How to work on the project |
| [Security](SECURITY.md) | Boundaries and reporting |

<a href="docs/README.md"><img src="showcase/capri/afterimage/path-index.svg" alt="Reading paths — setup, architecture, ownership, recovery and evaluation" width="230"></a>

[Browse the documentation by task](docs/README.md), with a responsive ownership and reconciliation map.

> [!IMPORTANT]
> **Experimental.** Native lifecycle/recovery qualification, the separate repaired-source comparison and final independent review remain pending at the recorded source cutoff. The current CI isolation prerequisite is failing; the runtime suite was skipped. See [current status](docs/STATUS.md).

No source-bound product demo was available. Character animation is artwork, not a controller recording. The transparent actor uses an authorized AI-edited reference with authored hand gestures; it is not a complete-body rig. [Actor sources and motion](docs/CAPRI_ACTOR.md).

**Mani Marami Milani** · [Afterimage](docs/AFTERIMAGE.md) · [Sources and edits](docs/ASSETS.md) · [Presentation references](docs/DESIGN_REFERENCES.md)

Unofficial Capri-inspired fan project; unaffiliated with CD PROJEKT RED, TRIGGER or Netflix. Code licensing and public character-art redistribution remain unresolved.[^art]

[^art]: The hero uses BluRei's source 19; the expression footage uses emdzejus's source 12. Barlow Condensed is bundled under its OFL notice. Uploader attribution does not establish underlying anime-image ownership. [Full asset record](docs/ASSETS.md).
