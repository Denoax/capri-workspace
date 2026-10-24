#!/usr/bin/env python3
"""Generate the V3 repository narrative and complete static edition from one model."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def picture(name,alt,width=1000,static=False):
    threshold=1000 if name=='contexts' else 760
    prefix='showcase/capri/story/exports/'+name;extension='png' if static else 'gif'
    return f'''<picture>
  <source media="(prefers-reduced-motion: reduce) and (max-width: {threshold}px)" srcset="{prefix}-portrait.png">
  <source media="(prefers-reduced-motion: reduce)" srcset="{prefix}-wide.png">
  <source media="(max-width: {threshold}px)" srcset="{prefix}-portrait.{extension}">
  <img src="{prefix}-wide.{extension}" alt="{alt}" width="{width}">
</picture>
'''
def main():
    m=json.loads((STORY/'model-results.json').read_text());totals=m['total_assumed_input_tokens'];g=m['derivations']['growing'];c=m['derivations']['curated'];n=m['calls'];steps='+'.join(str(i) for i in range(n));k=lambda v:f'{v//1000}k'
    original=(ROOT/'showcase/capri/source-match/BASE_README.md').read_text();start=original.index('Start with offline inspection');quick=original[start:original.index('<a href="docs/AFTERIMAGE.md"><img',start)]
    root='''<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="showcase/capri/hero.png">
  <img src="showcase/capri/hero.gif" alt="CAPRI — green face, expressive eyes and jagged magenta silhouette; the approved original banner." width="1000">
</picture>

CAPRI gives planning, coding and review their own Codex sessions. Explicit handoffs carry current decisions, relevant files, scope and checks. One worker edits; a separate reviewer checks the candidate against the request and evidence. **You decide what ships.**

**Experimental.** Offline checks cover implementation contracts; native launch/recovery qualification remains pending. [Setup](#quickstart) · [Architecture](ARCHITECTURE.md) · [Current status](docs/STATUS.md) · [Evaluation and evidence](EVALUATION.md).

<a id="the-loop"></a>

## From request to a reviewable candidate

'''+picture('workflow','Three full-body Capri poses carry ordered stages. Thinker receives request, correction and source and returns scope/checks. Doer returns patch/results/limits. Reviewer returns findings; Thinker reports to the human. One write owner; no automatic approval.')+'''
1. **Thinker / Plan:** request + latest correction + relevant source → brief, scope and acceptance checks.
2. **Doer / Build:** brief + allowed files → patch, check results and known limits.
3. **Reviewer / Review:** request + correction + candidate + evidence → findings and uncertainty.
4. **Thinker report → you:** reconcile the evidence and return the decision. **One writer; ordered stages.** Authoritative originals stay retrievable; uncertain effects hold.

<details>
<summary>Inside the loop — models and ownership</summary>

All three roles request `gpt-6.1-sol`. The selected profile uses medium Thinker/Doer effort and high Reviewer effort. Frozen contracts, checkpoints and source checks bind handoffs to their inputs. Formal outcomes stop at `AWAITING_HUMAN`; no successor starts automatically. Separate sessions can still share model blind spots.

[Native profile](NATIVE_PROFILE.md) · [Architecture](ARCHITECTURE.md) · [Qualification status](docs/STATUS.md)

</details>

<a id="context-and-evidence"></a>

## What the next request needs

'''+picture('contexts','The real ray-traced ASCII black hole and full-body Capri share a lesson with a calm, labelled six-request graph and the original articulated shark field. Illustrative inputs—not a CAPRI benchmark: growing history180k, curated single session90k, scoped roles60k. The stable brief retains task, latest correction, relevant source, scope/checks and retrievable originals.')+f'''
Focused contexts can avoid replaying discarded exploration. They still need enough information to do the work. The sharks frame the working brief; the black-hole lesson shows a **six-call input illustration**, not measured occupancy or a claim that caches swallow instructions.

- Growing history: `{n} × {k(g['initial'])} + {k(g['increment'])} × ({steps}) = {k(totals['growing'])}`.
- Curated single session: `{n} × {k(c['initial'])} + {k(c['increment'])} × {c['retained_steps']} = {k(totals['curated'])}`.
- Scoped roles: the listed requests sum to **{k(totals['scoped'])}**, including assumed role instructions and handoff inputs.

`(180−60)/180 = {m['scoped_vs_growing_percent_lower']}%` and `(90−60)/90 = {m['scoped_vs_curated_percent_lower']}%` are **lower assumed input**, not measured cost, speed, quality or retention gains. Equal work, sufficient information and equal quality remain untested. A carefully curated single session can match or beat scoped input; role count alone does not cause a saving.

<details>
<summary>Read every assumed input — tokens per request</summary>

| Request | Growing history | Curated single session | Scoped roles |
| ---: | ---: | ---: | ---: |
'''+''.join(f"| {row['request']} | {row['values']['growing']:,} | {row['values']['curated']:,} | {row['values']['scoped']:,} |\n" for row in m['requests'])+f'''| **Total** | **{totals['growing']:,}** | **{totals['curated']:,}** | **{totals['scoped']:,}** |

The {k(totals['growing'])} total spans six calls; it is not a simultaneously filled context window. Peak request input is a footprint, not exact active occupancy. Exact occupancy stays **UNKNOWN** where the runtime cannot establish it.

[Canonical assumptions](showcase/capri/source-match/source/assets/data/context-budget.json) · [Full arithmetic and accounting](docs/CONTEXT_BUDGET.md) · [Benchmark protocol and unrun comparisons](docs/BENCHMARK_PROTOCOL.md)

</details>

## Keep the correction attached

'''+picture('handoff','The original reaching hands and ASCII interruptions carry blank→Untitled near actual contact, with full-body Capri beneath. The complete authored packet includes label.py-only scope, outer trim, case/internal spaces and TypeError for non-strings, with expected examples. This is teaching artwork, not an observed model failure.',800)+'''
**Authored fixture A, not a recorded model result.** An incomplete brief such as “return Untitled for blanks” loses compatible rules. The complete packet carries the original request, latest correction, relevant source, file scope and expected checks:

| Check | Expected result after the correction |
| :--- | :--- |
| `"   "` | `"Untitled"` |
| `"  MiX  Case  "` | `"MiX  Case"` |
| `None` | raises `TypeError` |
| Changed files | only `label.py` |

Trim **outer** whitespace; preserve case and internal spaces. The latest correction replaces `Anonymous` with `Untitled` for blanks. Review can reread the [original request](evaluation/fixtures/A/INITIAL.md) and [correction](evaluation/fixtures/A/CORRECTION.md). A summary can omit a needed requirement; that is not cache-driven instruction deletion.

## Keep requirements; count coordination

'''+picture('retained','The original skull, sword and diagonal rain retain the scope/current-rule/source/check brief beside Capri. The original rotating dotted loop and surrounding wave carry60k+H, with H30k yielding90k, equal to the curated example. H is additional input beyond already-budgeted handoffs; no price or quality break-even is claimed.')+f'''
Shortening input is useful only if needed information remains available. Keep authoritative originals for implementation and review. Separate checking can challenge a candidate, but it also adds coordination, output and time.

Let **H** be additional input beyond the scoped example's already-budgeted instructions and handoffs. Scoped input becomes **60k + H**; its input margin versus curated is **30k − H**. At **H = {k(m['break_even_additional_input'])}**, that raw-input advantage disappears. Do not count an included handoff twice.

<details>
<summary>Inspect additional-input sensitivity and cost limits</summary>

| Additional H | Scoped input | Relation to curated 90k |
| ---: | ---: | :--- |
'''+''.join(f"| {k(row['additional_input'])} | {k(row['scoped_total'])} | "+('equal assumed input' if row['relation']=='equal' else f"{row['percent']}% {row['relation']} assumed input")+' |\n' for row in m['overhead_samples'])+'''
A short, clear task often fits one ordinary session. Use explicit handoffs when a plan, scoped implementation and separate checking are useful; the coordination has to earn its cost.

Prefix caching reuses matching computation. It does not delete instructions, create semantic memory or free context capacity. Fewer raw inputs do not determine the price order. Actual accounting needs disjoint ordinary-input, cached-read, cache-write and output buckets, applicable tiers, and every role/probe/retry/compaction/recovery attempt. [Detailed assumptions and simplified cache counterexample](docs/CONTEXT_BUDGET.md) · [Actual measurement protocol](docs/BENCHMARK_PROTOCOL.md).

</details>

## Check the candidate against the request

'''+picture('checking','The actual scanline cat changes from monochrome to Capri colors while full-body Review Capri arrives and beams follow source-frame eye anchors. This is an authored checking-stage illustration. A reviewer compares request, correction, patch and evidence; beams do not scan, secure or approve the repository.',640)+'''
A fresh checking context compares the request and correction with the candidate and its evidence. Shared model blind spots remain possible. Findings and limits return to the human; the illustration is not a native controller recording or an approval.

There is no completed native comparison proving CAPRI cheaper, faster or better at requirements retention. Offline CI, model outcomes, total cost and visual approval are separate evidence. [Current status](docs/STATUS.md) · [Evaluation](EVALUATION.md).

<a id="quickstart"></a>

## Start with offline checks

'''+quick+picture('closing','A compact still from the supplied elastic stack keeps scope, current correction and evidence together beside full-body Capri. It closes the teaching story and leads to actual setup; the companion retains its forward/reverse source loop.',480,True)+'''
## Explore the working source

[Interactive companion](docs/VISUAL_STORY.md#local-companion) · [Complete static edition](docs/README_STATIC.md) · [Detailed explanation](docs/CAPRI_EXPLAINS.md) · [Art studies](docs/AFTERIMAGE.md) · [Asset provenance and rights](docs/SOURCE_MATCH.md#sources-and-rights)

GitHub displays exported media, links and native disclosures. The local companion provides request selection, additional-input control, play/pause/replay/seek and source interactions. Its controls change real local scene state.

| Documentation | Purpose |
| :--- | :--- |
| [Architecture](ARCHITECTURE.md) | Ownership, handoffs, confinement and recovery |
| [Implementation guide](IMPLEMENTATION_README.md) | Existing commands and native startup |
| [Benchmark protocol](docs/BENCHMARK_PROTOCOL.md) | Quality, usage, cost and missing evidence |
| [Current status](docs/STATUS.md) | Qualification and human review gates |
| [Visual story build/source record](docs/VISUAL_STORY.md) | Canonical inputs, edited scenes, exports and verification |
| [Contributing](CONTRIBUTING.md) | Project change discipline |

**Mani Marami Milani.** Unofficial Capri-inspired fan project; unaffiliated with CD PROJEKT RED, TRIGGER or Netflix. Original banner and all source credits remain preserved. Native sharks/horizon use actual source implementations; five other effect families are credited footage composites. Character acting is fan-art reconstruction, not an official rig or exact anime acting. Source reuse and underlying character rights remain as recorded; repository stays private.
'''
    (ROOT/'README.md').write_text(root)
    static=root.replace('showcase/capri/hero.gif','showcase/capri/hero.png');static=re.sub(r'(story/exports/[^"\s]+)\.gif',r'\1.png',static)
    static=re.sub(r'((?:src|srcset|href)="|\]\()((?!https?:|#)[^"\s)]+)',lambda x:x[1]+'../'+x[2],static)
    (ROOT/'docs/README_STATIC.md').write_text('<!-- Generated from the same V3 canonical story. -->\n'+static)
    from build_capri_story_docs import main as build_docs
    build_docs(m)
    print('V3 root, static README and native explanations rebuilt')
if __name__=='__main__':main()
