# Capri's transparent actor

[Back to the guide](../README.md#the-loop) · [Full art record](ASSETS.md).

<img src="../showcase/capri/actor/actor.gif" width="562" alt="Transparent upper-body Capri actor with authored left/right hand gestures. Green face, blue eyes, angular black limbs and magenta speckled forms. Original source crop remains.">

[Static alpha pose](../showcase/capri/actor/actor.png) · [48-frame full-alpha PNG/APNG master](../showcase/capri/actor/actor-rgba.png) · [Separate animated RGB master](../showcase/capri/actor/actor-rgb.png) · [Separate animated alpha master](../showcase/capri/actor/actor-alpha.png) · [Body layer](../showcase/capri/actor/body.png) · [Left palm](../showcase/capri/actor/left_palm.png) · [Right palm](../showcase/capri/actor/right_palm.png) · [Editable recipe](../showcase/capri/actor/ANIMATION.json).

## Provenance and method

V7 explicitly authorized AI assistance for this asset. The handoff supplied an AI-edited cutout from source 14/frame 0 with source 20/frame 101 as an identity reference. The [unaltered candidate and original edit record](../showcase/capri/actor/references/ASSET_RECORD.json) and [exact supplied prompt](../showcase/capri/actor/references/CUTOUT_PROMPT.md) remain separate from the original footage's [source hashes and credits](../showcase/capri/SOURCES.json).

CPU source-mask propagation and manual source-pixel mask trials were inspected and rejected for room contamination or gaps in black anatomy. The final actor uses the explicitly permitted alternative: the supplied edited pose with coherent source-guided hand animation. RGB and alpha are separately editable APNG masters, and each articulated layer has a grayscale mask beside it. Recombine RGB with its paired alpha; the RGB master alone is an opaque color plane. Body/face/hair pixels stay fixed; the separate palms make restrained rotations at original-pixel wrist overlaps. This is authored 2D articulation, not original anime acting sampled at 24 FPS or independent per-frame AI generation. No new generative frames, face reconstruction or missing anatomy are invented.

The edited pose is not source-pixel-identical. Its original upper-body crop remains, including cut top/bottom forms. Padding prevents additional hand clipping during rotation; it is not a complete body or official rig. Upscaling in the handoff does not create an original HD source. Underlying anime redistribution rights remain unresolved.

## Timing and transparency

Standalone actor: **48 distinct decoded frames over 2,000 ms**, 24 samples/s, using rounded cumulative centisecond timestamps (40/50 ms delays). The full-alpha APNG master preserves soft edges; GIF uses reserved transparent palette index 0 and explicit disposal 2. Every decoded GIF alpha mask is compared with the alpha master to detect retained hands/trails. Black character pixels stay opaque.

The integrated 16-second guides retain four 3.5-second reading intervals and 0.5-second transitions. Each reading interval contains a quiet two-second authored gesture followed by a 1.5-second still. Active position travel uses 12 distinct samples over 500 ms, approximately 24 samples/s; the stationary Reviewer→report transition is not counted as position travel. Travel keeps one pointing pose so arrival does not reset a moving hand phase. The actor and path cadence are recorded separately. The approved 12 FPS banner is unchanged and is not called 60 FPS.

[Actual frame delays, uniqueness, transforms and bytes](../showcase/capri/actor/BUILD.json) · [Guide build](../showcase/capri/explainer/BUILD.json) · [Ink, paper and checkerboard still proof](../showcase/capri/actor/matte-proof.png). The checkerboard is a proof backdrop, never baked into the transparent GIF.

The timing/disposal rules follow the [GIF89a specification](https://www.w3.org/Graphics/GIF/spec-gif89a.txt) and [Pillow GIF documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html). Mechanical checks, screenshots and recordings do not award continuous perceptual or human visual approval. Hosted GitHub behavior must be distinguished from local previews.

## Rebuild the editable assets

Use the existing separate media environment (`requirements-media.txt`) and system `rsvg-convert`:

```sh
python tools/build_capri_actor.py
python tools/build_capri_explainer.py
python tools/build_capri_numbers.py
python tools/check_capri_presentation.py
```

No controller, native sessions, paid trials, runtime dependencies or model budgets are involved. Local preview controls are review features; GitHub Markdown retains the GIF and complete static/native-text alternatives.
