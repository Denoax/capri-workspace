#!/usr/bin/env python3
"""Generate V8 hero and trail correction README/static routes from canonical data and display roles."""
from pathlib import Path
import html,json,re
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
FORMATS=json.loads((STORY/'format.json').read_text());CONFIG=json.loads((STORY/'story.json').read_text())
ALTS={'workflow':'Three full-body poses: Plan returns scope/checks, Build returns a patch, Review returns findings. One writer; the human decides.','brief':'Actual native shark field, full-body Capri and a persistent brief: request/correction, relevant source, scope/checks and retrievable originals.','horizon':'The original native ray-traced ASCII horizon with full-body Capri; credited illustration of selective input, not a measured context window.','coordination':'The supplied dotted loop carries60k+H. Additional H30k yields90k, equal to the curated input assumption.','handoff':'Original reaching hands carry blank to Untitled beside full-body Capri. Authored fixture A, not an observed model failure.','checking':'The source cat takeover and eye-anchored beams accompany full-body Review Capri. This illustration does not approve or secure code.','graph':'Illustrative inputs, not a CAPRI benchmark: six assumed requests, thousand tokens per request. Growing history180k, curated 90k, scoped60k.','requirements':'Small source skull/sword/rain vignette: keep original rules, correction and checks retrievable.','closing':'Small source elastic-stack vignette with Capri: keep evidence together and continue to offline checks.'}
def image(name,static=False):
    lesson=CONFIG['lessons'][name];layout=lesson['root_layout'];family=FORMATS['families'][FORMATS['layouts'][layout]]
    def source(which,still=False):
        extension='png' if still or static or lesson.get('static_only') or which in lesson.get('static_layouts',[]) else 'gif'
        return 'showcase/capri/story/exports/'+name+'-'+which+'.'+extension
    sources=[]
    if 'mobile_layout' in lesson:
        mobile=lesson['mobile_layout'];cap=FORMATS['families'][FORMATS['layouts'][mobile]]['display_width'];query='(max-width:'+str(FORMATS['responsive']['breakpoint_px'])+'px)'
        sources += [f'<source media="{query} and (prefers-reduced-motion: reduce)" srcset="{source(mobile,True)}" width="{cap}">',f'<source media="{query}" srcset="{source(mobile)}" width="{cap}">']
    sources.append(f'<source media="(prefers-reduced-motion: reduce)" srcset="{source(layout,True)}">')
    return '<picture>'+''.join(sources)+f'<img src="{source(layout)}" alt="{html.escape(ALTS[name],quote=True)}" width="{family["display_width"]}"></picture>'
def group(*names,static=False):
    return '<p align="center">'+'\n'.join(image(n,static) for n in names)+'</p>'
def divider(static=False):
    c=FORMATS['separator'];src='separator.png' if static else 'separator.gif'
    return '<p align="center"><picture><source media="(prefers-reduced-motion: reduce)" srcset="showcase/capri/story/separator.png"><img src="showcase/capri/story/'+src+'" alt="Green arrow moves right along a magenta track with a long, gradually fading green wake; older track turns magenta again." width="'+str(FORMATS['families']['divider']['display_width'])+'"></picture></p>'
def build(static=False):
    m=json.loads((STORY/'model-results.json').read_text());k=lambda v:f'{v//1000}k';t=m['total_assumed_input_tokens'];g=m['derivations']['growing'];c=m['derivations']['curated'];n=m['calls'];steps='+'.join(str(i) for i in range(n))
    base=(ROOT/'showcase/capri/source-match/BASE_README.md').read_text();start=base.index('Start with offline inspection');quick=base[start:base.index('<a href="docs/AFTERIMAGE.md"><img',start)]
    hero='png' if static else 'gif';opening=f'''<p align="center"><picture><source media="(prefers-reduced-motion: reduce)" srcset="showcase/capri/hero.png"><img src="showcase/capri/hero.{hero}" alt="CAPRI — AGENTIC LOOPING. Original animated Capri and city on the right; CAPRI and AGENTIC LOOPING over a transparent left field, without a frame." width="{FORMATS['hero']['display_width']}"></picture></p>

# CAPRI — Agentic Loop Prompting

**Focused inputs. Scoped execution. A separate review pass.**

CAPRI is an experimental Agentic Loop Prompting workflow for Codex. Planning, implementation and review use their own focused sessions, connected by an explicit brief: the current request, latest correction, relevant source, allowed changes and expected checks.

On complex coding work, the goal is less input spent replaying discarded exploration and clearer checking of each decision. The reviewer returns to the original request and checks the candidate and its evidence. One worker owns edits. **You decide what ships.**

**Experimental.** Offline checks cover implementation contracts; native launch/recovery qualification remains pending. [Setup](#quickstart) · [Architecture](ARCHITECTURE.md) · [Current status](docs/STATUS.md) · [Evaluation](EVALUATION.md).

<a id="the-loop"></a>

## How the loop works

'''+group('workflow','brief',static=static)+'''

A scoped brief carries the request, latest correction, relevant source, allowed files and expected checks. Authoritative originals remain retrievable.

1. **Thinker / Plan:** request + correction + source → scope and acceptance checks.
2. **Doer / Build:** brief + allowed files → patch, check results and limits.
3. **Reviewer / Review:** request + candidate + evidence → findings.
4. **Thinker report → you:** reconcile findings and decide. **One writer; ordered stages.** Uncertain effects hold.

<details>
<summary>Models, ownership and frozen handoffs</summary>

All three roles request `gpt-6.1-sol`. The selected profile uses medium Thinker/Doer effort and high Reviewer effort. Contracts, checkpoints and source checks bind handoffs to their inputs. Formal outcomes stop at `AWAITING_HUMAN`; no successor starts automatically. Separate contexts can share model blind spots.

[Native profile](NATIVE_PROFILE.md) · [Architecture](ARCHITECTURE.md) · [Qualification](docs/STATUS.md)

</details>

'''+divider(static)+'''

<a id="context-and-evidence"></a>

## Why scope the input

'''+group('graph',static=True)+f'''

**Input efficiency:** supply what the next stage needs instead of carrying unrelated exploration. The mechanism is focused input; actual cost, speed and quality gains remain unmeasured.

**Illustrative inputs — not a CAPRI benchmark.** Across six assumed requests: growing history **{k(t['growing'])}**, a curated single session **{k(t['curated'])}**, scoped roles **{k(t['scoped'])}** including already-budgeted instructions and handoffs.

- Growing: `{n} × {k(g['initial'])} + {k(g['increment'])} × ({steps}) = {k(t['growing'])}`.
- Curated: `{n} × {k(c['initial'])} + {k(c['increment'])} × {c['retained_steps']} = {k(t['curated'])}`.
- `(180−60)/180 = {m['scoped_vs_growing_percent_lower']}%` and `(90−60)/90 = {m['scoped_vs_curated_percent_lower']}%` are **hypothetical lower input**, not demonstrated cost, speed, quality or retention gains.

Equal work, sufficient information and equal quality remain untested. The 180k total spans calls; it is not one simultaneously occupied context window. Exact active occupancy remains **UNKNOWN**. A carefully curated single session can match or beat scoped input.

<details>
<summary>Every assumed input — tokens per request</summary>

| Request | Growing history | Curated single session | Scoped roles |
| ---: | ---: | ---: | ---: |
'''+''.join(f"| {r['request']} | {r['values']['growing']:,} | {r['values']['curated']:,} | {r['values']['scoped']:,} |\n" for r in m['requests'])+'''| **Total** | **180,000** | **90,000** | **60,000** |

[Canonical assumptions](showcase/capri/source-match/source/assets/data/context-budget.json) · [Full arithmetic and cache counterexample](docs/CONTEXT_BUDGET.md) · [Unrun comparisons](docs/BENCHMARK_PROTOCOL.md)

</details>

'''+group('horizon','coordination',static=static)+'''

Focused input can avoid replaying discarded exploration; it still needs enough information. Extra coordination must earn its cost: **60k + H** adds input beyond the handoffs already counted. At **H = 30k**, scoped and curated input are equal; the margin is **30k − H**. Do not count a handoff twice.

<details>
<summary>Additional-input sensitivity and accounting limits</summary>

| Additional H | Scoped input | Relation to curated 90k |
| ---: | ---: | :--- |
'''+''.join(f"| {k(r['additional_input'])} | {k(r['scoped_total'])} | "+('equal assumed input' if r['relation']=='equal' else f"{r['percent']}% {r['relation']} assumed input")+' |\n' for r in m['overhead_samples'])+'''
A short, clear task often fits one ordinary session. Prefix caching reuses matching computation; it does not delete instructions or free context capacity. Fewer raw inputs do not establish price order. Actual accounting needs disjoint ordinary-input, cached-read, cache-write and output buckets, applicable tiers and every role/probe/retry/compaction/recovery attempt. [Accounting assumptions](docs/CONTEXT_BUDGET.md) · [Measurement protocol](docs/BENCHMARK_PROTOCOL.md).

</details>

## What a handoff must retain

'''+group('handoff','checking',static=static)+'''

**Output quality:** preserve compatible requirements and give review a separate context and explicit checks so omissions are easier to catch. This is a design goal, not a measured quality improvement; a reviewer can share model blind spots and adds work.

**Authored fixture A, not a recorded model result.** The latest correction changes blank input from `Anonymous` to `Untitled`. An incomplete summary can lose compatible rules; review rereads the [original request](evaluation/fixtures/A/INITIAL.md) and [correction](evaluation/fixtures/A/CORRECTION.md).

| Rule or check | Required result |
| :--- | :--- |
| `"   "` | `"Untitled"` |
| `"  MiX  Case  "` | `"MiX  Case"`: trim outer whitespace, preserve case/internal spaces |
| `None` | raises `TypeError`: non-strings are rejected |
| Allowed changes | only `label.py` |

The checking context compares request, correction, patch and evidence. Findings and limits return to the human. Shared model blind spots remain; neither the illustration nor offline CI proves CAPRI cheaper, faster or better at retaining requirements.

'''+divider(static)+'''

<a id="quickstart"></a>

## Start with offline checks

'''+group('requirements','closing',static=static)+'\n\nKeep original requirements and evidence accessible; full source interactions remain in the companion.\n\n'+quick+'''
## Explore the working source

[Interactive companion](docs/VISUAL_STORY.md#local-companion) · [Static edition](docs/README_STATIC.md) · [Detailed explanation](docs/CAPRI_EXPLAINS.md) · [Art studies](docs/AFTERIMAGE.md) · [Sources and rights](docs/SOURCE_MATCH.md#sources-and-rights)

GitHub displays media and native links/disclosures. The local companion supplies real request/H selection, play/pause/replay/seek and source interactions. The graph is a separate readable figure; source art remains animated.

[Architecture](ARCHITECTURE.md) · [Implementation guide](IMPLEMENTATION_README.md) · [Benchmark protocol](docs/BENCHMARK_PROTOCOL.md) · [Status](docs/STATUS.md) · [Presentation build](docs/VISUAL_STORY.md) · [Contributing](CONTRIBUTING.md)

**Mani Marami Milani.** Unofficial Capri-inspired fan project; unaffiliated with CD PROJEKT RED, TRIGGER or Netflix. Original credits and MIT/OFL notices remain. Native sharks/horizon use supplied source implementations; the five other effects are credited footage composites. Character acting is a fan-art reconstruction. Underlying character/media rights remain as recorded; keep private.
'''
    return opening

def main():
    root=build();(ROOT/'README.md').write_text(root)
    static=build(static=True);static=re.sub(r'((?:src|srcset|href)="|\]\()((?!https?:|#)[^"\s)]+)',lambda m:m[1]+'../'+m[2],static);(ROOT/'docs/README_STATIC.md').write_text('<!-- Generated from the same V7 source/data. -->\n'+static)
    from build_capri_story_docs import main as docs
    docs(json.loads((STORY/'model-results.json').read_text()))
    print('Agentic Loop Prompting root/static editions rebuilt')
if __name__=='__main__':main()
