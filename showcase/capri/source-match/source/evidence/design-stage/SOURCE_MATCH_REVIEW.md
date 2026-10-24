> Historical design-stage record. The user subsequently approved the Codex implementation handoff and ZIP. Current authority is CODEX_PROMPT.md; earlier no-ZIP gates in this record are satisfied by that approval. This does not turn earlier unverified checks into passes.

# Capri source-match review drafts

The user approved the visual direction and explicitly requested much closer, essentially one-to-one reference use, with Capri layered on top. The user also explicitly said not to make a ZIP yet. This is a draft-only iteration. No repository modification, branch push, merge or Codex handoff ZIP occurs here. The existing banner and first Handoff comic remain preserved.

## Reference use

| Reference | Basis used in this draft | Adaptation |
| --- | --- | --- |
| [ASCII sharks](https://www.inspora.design/posts/shark-ascii-animation) | Creator's actual [TypeScript implementation](https://github.com/stackedlol/ascii-sharks) | Original World and AsciiRenderer geometry, boids, sharks, wake and splash behavior. Types stripped and modules scoped for embedding. Capri palette, brief overlay and jointed actor added. |
| [Black hole](https://www.inspora.design/posts/black-hole-mp4) | Creator's actual [horizon implementation](https://github.com/SiddDevZ/horizon) | Original ray tracing, glyph matching, lensing and particle eating. Stage, palette, brief text and embedding controls adapted. Full MIT notice retained in the embedded factory. |
| [I will survive](https://www.inspora.design/posts/i-will-survive) | Selected original video from the linked post | Original skull, sword and diagonal rain retained, recoloured. Jointed Capri and an expandable retained brief layered over it. Context-selection metaphor, not an automatic filtering or security guarantee. |
| [Cat hero](https://www.inspora.design/posts/hero-section) | Selected original scanline-cat recording | Cat itself retained. Crop widened to retain its body through the turn. A monochrome-to-Capri scan, actor entrance and tracked eye beams are added. |
| [1-40](https://www.inspora.design/posts/1-40) | Selected original dotted-loop and wave recording | Original card proportions, moving loop and surrounding dot wave retained. Original card text covered by project copy. A compact interlude, not an approved banner replacement. |
| [1-23](https://www.inspora.design/posts/1-23) | First 5.4 seconds of the selected elastic-stack recording | Original stack motion recoloured. Forward/reverse closure avoids the unrelated branded end frame and creates a local loop. |
| [2-8](https://www.inspora.design/posts/2-8) | Selected original reaching-hands recording | Original hand geometry, contact sequence and ASCII interruptions retained. Colours, a current-correction label and jointed Capri added. |

The five video-backed panels are reference-footage composites. They are not claimed to be newly implemented native replacements for those videos. Their creator processes and redistribution licences remain unverified. Keep them identified as reference composites in any later handoff; resolve usable release assets/source before treating them as distributable production assets. No source media was fetched from a paywall or authenticated account.

Shark source was publicly published by stackedlol, whose original post links the repository. The inspected repository has no explicit licence file; public source alone is not a blanket redistribution licence. This record does not label it MIT. The horizon project is MIT, copyright 2026 Siddharth Meena, and its notice is retained. Original video credits: stacked, siddharth, YUDHO, loseva_pro, Maxim Kuznetsov, Grok Bot and causasui respectively. Original post and selected-media records remain in the prior inspora research folder.

## Character animation

The prior whole-image sinusoidal hover is superseded in these new panels by a ten-part full-body cutout rig. It has separate torso, head, upper arms, forearms, thighs and shins; angular poses, anticipation, short holds, recovery and two blink states. Every part uses a rigid transform, preserving its shape and length. The global camera stays fixed across the pose sequence. Root motion is authored as a keyframed path for the black-hole scene.

The model is the existing authorized full-body fan-art reconstruction. The anime clips, especially source20, informed the study of pose changes and holds. The angles and loop closure are independently authored. This does not establish exact reproduction of the anime's anatomy, expression changes or acting. Seam quality and exact source fidelity still need visual refinement. The rejected flexible-warp experiment is not embedded in either delivered draft.

The loop is authored at 30 pose samples per second over 2.8 seconds. That is a timeline specification, not a measured browser frame rate. The new rig is directly rendered from component textures; intermediate atlases are not required for either preview. Final GIF exports have not been substituted into the repository.

## Verification and remaining review

- Both fragments have literal markup, unique IDs, no external data requests and less than 1 MB per fragment.
- JavaScript syntax is checked after data/source embedding.
- Sampled rig transforms have unit scale and determinant one within floating-point precision. Independent forearm travel relative to the torso is checked, establishing articulation beyond rigid whole-image movement.
- The cat overlay has 129 tracked eye samples with manual keyframe calibration. Nine decoded sample frames were inspected. This does not certify uninterrupted beam alignment.
- Source videos are decoded and transcribed to preview media at their original temporal speed; resampling video to 30 FPS does not add new character acting.
- Black-hole GPU execution, responsive browser output, live interaction and continuous perceptual smoothness remain unverified. Earlier local browser-preview access was blocked; no workaround is attempted. Syntax and decoded-frame checks are not presented as browser or motion approval.

The preview controls support motion pause, replay, shark ripples and disk tilt; native expanders carry briefs. GitHub README delivery later requires rendered media and GitHub-native interactions. Do not imply that JavaScript, WebGL or these companion-preview interactions execute inside GitHub Markdown.

## Next design work

Preserve the selected first-comic layout and upright typography. Use these source-matched panels as the visual direction. Continue refining full-body anatomy, expressions and source-specific acting; do not report exact anime fidelity until actual comparisons support it. Keep the existing numeric example labelled as assumed six-call input, not measured CAPRI savings. No ZIP until the user explicitly requests it.
