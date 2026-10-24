#!/usr/bin/env python3
"""Reproduce README/static presentation from approved content and current sources."""
from pathlib import Path
import json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE='521598688be57fdc56a26ff15a4b4eddb65d6433'
def picture(name,alt):
 prefix='showcase/capri/source-match/exports/'+name
 return f'''<picture>
  <source media="(prefers-reduced-motion: reduce) and (max-width: 760px)" srcset="{prefix}-portrait.png">
  <source media="(prefers-reduced-motion: reduce)" srcset="{prefix}-wide.png">
  <source media="(max-width: 760px)" srcset="{prefix}-portrait.gif">
  <img src="{prefix}-wide.gif" alt="{alt}" width="{dict(comic=1120,hands=720,sharks=900,rain=720,horizon=960,cat=640,dots=720)[name]}">
</picture>
'''
def main():
 original=(ROOT/'showcase/capri/source-match/BASE_README.md').read_text()
 start=original.index('Start with offline inspection')
 quick=original[start:original.index('<a href="docs/AFTERIMAGE.md"><img',start)]
 assert 'unittest discover -s controller/tests -v' in quick and 'Before launching native sessions' in quick
 fields=original[original.index('| Open the file |'):original.index('<details>\n<summary><strong>Read the handoff map')]
 profile=original[original.index('<details>\n<summary><strong>Inside the loop'):original.index('<a id="quickstart">')]
 data=json.loads((ROOT/'showcase/capri/source-match/source/assets/data/context-budget.json').read_text());series=data['series'];totals=[sum(s['values']) for s in series];assert totals==[180000,90000,60000]
 hero='''<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="showcase/capri/hero.png">
  <img src="showcase/capri/hero.gif" alt="CAPRI — her green face, expressive eyes, jagged silhouette and long magenta hands." width="1000">
</picture>

A three-session Codex workflow for research, scoped implementation and independent review. Explicit handoffs carry the decisions; **you decide what ships**.

[Start](#quickstart) · [The loop](#the-loop) · [Context and evidence](#context-and-evidence) · [Field notes](#field-notes)

[Complete static edition](docs/README_STATIC.md) · [Local companion and source record](docs/SOURCE_MATCH.md) · [Current status](docs/STATUS.md)

<a id="the-loop"></a>

## Plan. Build. Review.

'''
 root=hero+picture('comic','The approved three-panel Handoff comic: full-body Capri plans, points and inspects. Plan maps to Thinker, Build to Doer and Review to Reviewer. Findings, checks and limits return to the human; one write owner, ordered stages, no automatic approval.')+'''
1. **Thinker / Plan:** select the request, latest correction, relevant source, allowed changes and acceptance checks. Keep originals retrievable.
2. **Doer / Build:** implement the scoped candidate; return the patch, checks and known limits with the brief.
3. **Reviewer / Review:** compare the request, correction, candidate and evidence in a fresh checking context. Separate sessions can still share model blind spots.
4. **Thinker report → you:** findings and limits return for a human decision. **One write owner; ordered stages. Uncertain effects hold for reconciliation.** Replay in the artwork is not another task or approval.

'''+profile+'''## Keep the correction with the task

'''+picture('hands','The supplied reaching-hands composition and ASCII interruptions retain their actual choreography. The blank → Untitled packet appears near the measured contact; full-body Capri points beneath it. This is authored teaching artwork, not a native run.')+'''
**Authored fixture A illustration, not an observed model result.** The original request trims outer whitespace, preserves case and internal spaces, rejects non-strings, and permits changes only to `label.py`. The latest correction changes the blank label from `Anonymous` to **`Untitled`**; compatible original rules remain. [Original request](evaluation/fixtures/A/INITIAL.md) · [Correction](evaluation/fixtures/A/CORRECTION.md).

| Input | Expected behavior after the correction |
| :--- | :--- |
| `"   "` | `"Untitled"` |
| `"  MiX  Case  "` | `"MiX  Case"` |
| `None` | raises `TypeError` |

A brief saying only “trim text; return Anonymous for blanks” loses the latest decision and compatible constraints. A complete handoff carries **scope + current correction + original rules + source retrieval + checks**. The loss is in that authored brief; it is not cache-driven instruction deletion. [Walk through the explanation](docs/CAPRI_EXPLAINS.md).

<a id="context-and-evidence"></a>

## Supply a focused working context

'''+picture('sharks','The real source ASCII shark simulation retains swimming articulated sharks, fish, depth and wakes around a calm scoped brief. Full-body Capri gestures beside blank → Untitled. The local companion has real ripple and pointer interactions; this README is exported media.')+'''
A context is the information available to a role: instructions, source, history and tool results. Exploration, abandoned alternatives and logs need not fill every later request. Select by purpose while retaining the request, corrections, relevant source and authoritative originals. A short packet that omits a needed rule is still wrong.

'''+picture('rain','The supplied skull, vertical sword, stippled texture and diagonal rain remain together. Capri inspects a retained working brief with the correction, source and checks. Deliberate context selection is the teaching metaphor; no security or retention guarantee is claimed.')+'''
### Worked example: assumed input tokens

**Not a measured CAPRI run.** Six requests per policy, including assumed role instructions and handoff inputs:

| Context policy | Assumed input total |
| :--- | ---: |
| Growing history | 180,000 |
| Curated single session | 90,000 |
| Scoped roles | 60,000 |

Under these inputs, scoped requests are **66.7% lower** than growing history and **33.3% lower** than the curated example. The curated single session is itself 50% below growing history. Information sufficiency and equal answer quality have **not** been established. Agent count alone does not create these differences.

<details>
<summary>Inspect all six assumed calls</summary>

| Call | Growing history | Curated session | Scoped roles |
| ---: | ---: | ---: | ---: |
'''+''.join(f'| {i+1} | {a:,} | {b:,} | {c:,} |\n' for i,(a,b,c) in enumerate(zip(*[s['values'] for s in series])))+'''| **Total** | **180,000** | **90,000** | **60,000** |

[Canonical editable inputs](showcase/capri/source-match/source/assets/data/context-budget.json) · [Calculator and complete assumptions](docs/CONTEXT_BUDGET.md) · [Actual benchmark protocol](docs/BENCHMARK_PROTOCOL.md)

</details>

**Fewer raw inputs do not guarantee the same reduction in cost.** At a hypothetical cached relative rate of `0.05`, 50k uncached + 130k cached growing-history inputs use **56.5k weighted units**, below 60k uncached scoped inputs. These are normalized assumptions, not prices. Outputs, coordination, retries, compaction and recovery also matter. Prefix caching reuses eligible computation; it does not delete instructions, create semantic memory or free context-window capacity.

'''+picture('horizon','The actual horizon WebGL ray tracer lenses a page containing request, correction and evidence text, with its central shadow, character disk and orbiting/eaten letters. Capri moves around it. This artwork is not a context-occupancy measurement.')+'''
The distinction is between **selecting working inputs** and **preserving authority**. Review rereads the request and checks the patch against evidence. Exact active context occupancy stays **UNKNOWN** when the runtime cannot establish it. [Architecture](ARCHITECTURE.md) · [Benchmark accounting and unrun comparisons](docs/BENCHMARK_PROTOCOL.md).

<a id="quickstart"></a>

## Quickstart

'''+quick+'''## Afterimage

'''+picture('cat','The supplied moving scanline cat begins monochrome; full-body Capri arrives, a controlled color scan follows, and green beams track the actual eye positions. Same source time drives the actor and effects. No audio.')+'''
[Open the local interactive companion](docs/SOURCE_MATCH.md#local-companion) for the source-based effects, keyboard controls and motion player. GitHub shows images and native disclosures; scripts, canvas, custom body fonts and live WebGL do not execute in this README.

'''+picture('dots','The supplied rotating dotted loop and surrounding dot wave retain their original geometry and density. The central card carries the brief and evidence message. Source footage is composited rather than claimed as an original native simulation.')+'''
[Art studies and the optional elastic stack](docs/AFTERIMAGE.md) · [Complete static edition](docs/README_STATIC.md) · [Character reconstruction and source rights](docs/SOURCE_MATCH.md)

<a id="field-notes"></a>

## Field notes

'''+fields+'''
> [!IMPORTANT]
> **Experimental.** Current source includes V3 stopped-recovery work; native launch/recovery qualification and formal final review remain pending. Offline CI passed at the recorded base `5215986`; inspect the exact testing-commit result separately. The v4 comparison rows remain unrun. This presentation runs no models and changes no runtime/evaluation state. [Current status](docs/STATUS.md) · [Alpha readiness](docs/ALPHA_READINESS.md).

No source-bound product demo is shown. Character acting is authored fan-art reconstruction; five source panels use reference-footage composites. The shark and horizon effects use actual supplied executable source. [Assets, notices and provenance](docs/SOURCE_MATCH.md#sources-and-rights).

**Mani Marami Milani** · [Afterimage](docs/AFTERIMAGE.md) · [Art credits](docs/ASSETS.md) · [Design references](docs/DESIGN_REFERENCES.md)

Unofficial Capri-inspired fan project; unaffiliated with CD PROJEKT RED, TRIGGER or Netflix. Repository remains private. Code licensing, reference-footage permissions and underlying character-art redistribution rights remain distinct and unresolved where recorded. The approved banner and its original credits are retained; no blanket MIT licence is assigned to this media.
'''
 (ROOT/'README.md').write_text(root)
 static=root.replace('showcase/capri/hero.gif','showcase/capri/hero.png')
 static=re.sub(r'(source-match/exports/[^"\s]+)\.gif',r'\1.png',static)
 static=re.sub(r'((?:src|srcset|href)="|\]\()((?!https?:|#)[^"\s)]+)',lambda m:m[1]+'../'+m[2],static)
 (ROOT/'docs/README_STATIC.md').write_text('<!-- Generated by tools/build_capri_source_match_readme.py from the same canonical content. -->\n'+static)
 print('Root and full static README rebuilt from approved content',flush=True)
if __name__=='__main__':main()
