# Source-matched CAPRI presentation

The current V3 composition and rebuild entry point are documented in [Visual story](VISUAL_STORY.md). All source-match masters, original exports and the [preserved original player](../showcase/capri/source-match/companion/source-match.html) remain available. The older rebuild sequence below targets the historical edition.

This private testing candidate uses the approved first Handoff comic and seven supplied source treatments. The original banner remains byte-identical. The comic keeps three staggered full-body scenes and upright **Manrope 500 / Inter 400–500** typography, with ordinary native links and explanations around the media. GitHub body typography remains GitHub's own.

## Local companion

Open [the self-contained companion](../showcase/capri/source-match/companion/index.html) from a local checkout or the portable review ZIP. This is a self-contained local folder: fonts and reference plates use embedded data, while the adjacent `actor-data.js` supplies the embedded character layers. Both files travel together; no account, original absolute path or server is needed for playback. Splitting data preserves the runtime checkout’s existing 8 MB per-file source-snapshot limit. GitHub's file page shows source, not a live website. The local review includes a separate direct playable link. No public deployment is authorized.

Each scene has real Play/Pause, Replay and Time controls. Comic buttons open actual briefs and pass the correction. Sharks support pointer splashes and the keyboard-equivalent ripple button; horizon supports drag/tap and a keyboard tilt button. Offscreen scenes and hidden documents pause rendering/decoding. Reduced motion starts on complete still states; [the static README](README_STATIC.md) requires no motion or JavaScript.

One scene timeline drives actor poses, packet anchors and phase. For footage composites, actual source video time drives the overlays and cat eye beams; explicit source seeks are checked. Full-size review exposed drift in the supplied 129 eye priors. The new editable 258-sample eye map measures actual decoded pupil shapes after removing thin scanlines, then applies a bounded local refinement. Closed/undetected eyes suppress the beams; the original priors remain preserved. The same renderer creates the GIFs and posters. Native worlds remain unbounded during live playback; exported excerpts use a deliberate short dark bridge at their nonperiodic world boundary.

## Character masters and acting

[Three full-body RGBA/alpha masters, thirty lossless layers, masks and rig keys](../showcase/capri/source-match/actor) are derived from the supplied Plan/Build/Review fan-art studies. Original studies and exact generation prompts remain under [immutable source assets](../showcase/capri/source-match/source/assets/characters). No new generation is used by this implementation.

Pose-specific eye, mouth, shoulder/elbow, hip/knee and gesture anchors replace the prototype's Plan-only pivots. A common apparent eye span calibrates the camera; sprites are not independently fit to their bounds. Head, torso, upper/lower arms and thighs/shins have separate rigid transforms. Anticipation, gesture, hold and recovery remain editable. Independent blink overlays use each pose's actual eye centers. Limb lengths stay fixed; no rubber-sheet mesh warp is applied.

Mask review found stray anatomy left in the torso/head defaults. Measured anatomical envelopes and nearest-envelope completion assign those original pixels correctly. Small overlaps and joint colors sampled from each master close exposed cutout seams. Full alpha remains editable. [Transparent animated actor GIF](../showcase/capri/source-match/exports/actor-wide.gif), [lossless RGBA animation](../showcase/capri/source-match/exports/actor-rgba.png), [RGB master](../showcase/capri/source-match/exports/actor-rgb.png) and [alpha master](../showcase/capri/source-match/exports/actor-alpha.png) share the 9.6-second three-pose timeline. The GIF uses a fixed palette, explicit full frames and disposal 2; the checks compare every decoded alpha mask with its lossless source. Brief empty reveals separate the faces. These repairs are authored reconstruction, not evidence of unseen official anatomy or exact anime acting. [Actual source clips and decoded samples](../showcase/capri/source-match/source/research/anime).

## Sources and rights

| Treatment | Source retained | Adaptation and status |
| :--- | :--- | :--- |
| ASCII sharks | stackedlol's actual swimming geometry, articulated spines/fins, depth, fish and wakes | Native factory with deterministic export seed, Capri palette and scoped brief. No explicit licence in the supplied source snapshot. |
| Horizon | Siddharth Meena's actual WebGL 2 ray tracer, central shadow, lensed page text and eaten letters | Native source with project text/colour and character overlay. MIT notice retained verbatim. |
| Reaching hands | causasui's framed hand contact and ASCII interruptions | Recorded footage composite; packet follows the measured contact, with Capri beneath. |
| Skull/sword/rain | YUDHO's skull, vertical sword, stippling and diagonal rain | Recorded footage composite with retained working brief. |
| Scanline cat | loseva_pro's moving cat and horizontal trails | Recorded footage composite, coordinated arrival/colour scan and source-time eye beams. |
| Dotted loop/wave | Maxim Kuznetsov's loop, central card and surrounding wave | Recorded footage composite with actual project copy. |
| Elastic stack | Supplied 1-23 / Grok Bot stacking motion | Optional companion/art scene; branded ending excluded, source forward/reverse closure disclosed. |

[Exact source URLs, creators and hashes](../showcase/capri/source-match/source/research/inspora/SELECTED_SOURCES.json) · [Original source/code/character/font notices](../showcase/capri/source-match/source/SOURCES.md) · [Input source catalog](../showcase/capri/source-match/source/SOURCE_CATALOG.json).

Five panels are **reference-footage composites**, not claims of native source implementation. Their redistribution permissions and underlying character-art rights remain unresolved. Design approval is not a creator licence. The repository remains private; no creator is contacted and no blanket MIT licence is assigned. The horizon notice, all three OFL notices and the original banner/source credits remain separate. Character-art generation permission remains scoped to Capri cutouts/repairs, not UI, backgrounds, diagrams or benchmark evidence.

## Rebuild and verify

The exact input payload is preserved under [source/](../showcase/capri/source-match/source) and [source-parts/](../showcase/capri/source-match/source-parts). Three original reference files exceed the unchanged runtime snapshot limit; their bytes are stored in 4 MB lossless chunks, with original hashes and piece hashes in [SOURCE_STORAGE.json](../showcase/capri/source-match/SOURCE_STORAGE.json). The original manifest and all other input files remain byte-identical. Materialize the complete original kit **outside the runtime checkout**, then run its unchanged read-only verifier. The supplied ZIP, previous commit and private originals remain preserved. New derived files live beside the input storage. Media tooling is separate from runtime requirements/locks: Python, Pillow, NumPy, websockets, Chromium and FFmpeg. The recorded media environment and export receipts identify actual versions; software rendering is not GPU performance qualification.

```sh
python3 tools/materialize_capri_source.py --output ../capri-original-input
python3 ../capri-original-input/tools/verify_bundle.py
python3 tools/build_capri_source_match_actor.py
python3 tools/build_capri_source_match_plates.py
python3 tools/build_capri_source_match.py
python3 tools/build_capri_source_match_readme.py
python3 tools/export_capri_source_match.py --evidence /your/task-private/media-output
python3 tools/build_capri_source_match_manifest.py
python3 tools/check_capri_presentation.py
```

Set `CAPRI_CHROMIUM` to an installed Chromium executable when its location differs. The exporter starts only an owned loopback server, uses a fresh isolated browser profile and stops both afterward. It samples shared scene data; it does not launch CAPRI models, recovery or benchmarks. Original native-source builders remain supplied for provenance; no Node installation is needed to run the prepared companion factories.

## Evidence boundaries

Rain retains its 0.5-second source loop with a deliberate held Review reading pose; hands uses a 50 FPS export, and the longer comic/takeover/native excerpts use a 25 FPS fallback. Those rates do not increase the original footage cadence. The optional transparent actor preserves antialiased alpha in its lossless masters; GIF alpha is thresholded at 128.

The review records decoded durations, distinct complete states, active cadence, source-frame cadence, bytes, alpha bounds and actual browser checks separately. GIF frame count is not source acting. Export success, selected frames and a video recording are not proof that continuous motion feels smooth. Hosted private GitHub review, physical devices, native qualification and human visual acceptance remain separate checks. [Current runtime status](STATUS.md) and [benchmark protocol](BENCHMARK_PROTOCOL.md) are preserved.
