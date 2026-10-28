# Character acting, scene timing and exported media

## What exists and what remains

The packet contains three complete RGBA fan-art studies: Plan, Build and Review. The present ten-part rig animates the Plan master using independently transformed head, torso, upper arms, forearms, thighs and shins. It adds two authored blink states. Its 2.8-second motion keys and fixed camera are editable. This is a reconstructed cutout rig and an authored acting study, not an official model, source-extracted full rig or exact anime animation.

The first flexible-warp experiment produced distorted limbs and is intentionally excluded. Do not recreate the rubbery deformation. The old whole-sprite hover is only part of the preserved first-comic layout reference; it is not the requested final acting standard.

## Refine the model and poses

Inspect the original anime clips in research/anime/originals, particularly source20's full-body movement and source19's expressive acting. The source has cropped/occluded areas; those are not proof of unseen official anatomy. Compare actual source frames to the reconstructed models at intended display size.

At least three full-body poses must differ in silhouette, torso/head attitude, arm arrangement and expression. A mirror, crop, colour change or wrist phase does not count. Build/Review have their own masters; do not reuse Plan's mask and pivot coordinates blindly.

Preserve sharp green face regions, expressive eyes, angular grin, jagged magenta hair, black/magenta limbs, green leg accents and slender proportions. Refine weak anatomy, face articulation and cutout seams within the user's character-art permission. Keep true alpha and editable RGB/alpha masters. No permanent rectangular crop, missing hair tip or cut-off finger/foot.

## Animation contract

- Establish pose-specific eye-line, head-size, mouth, chest, shoulder/elbow, hip/knee and gesture-tip anchors. Use one calibrated character camera and apparent head scale across poses. Do not auto-fit each sprite to its own bounds.
- Animate torso, head, arms, fingers/hands where meaningful, legs and face independently. Use anticipation, a decisive gesture, follow-through, a short readable hold and recovery. Global sinusoidal translation/rotation is not sufficient.
- Preserve limb lengths and silhouette. Repair gaps and overlap order at joints. Do not hide a broken joint by smearing the entire character.
- Maintain one scene clock for the actor, callout, phase, packet and hand endpoints. Anchor packet travel to the actual moving hand, not an arbitrary box corner.
- Pose transitions need appropriate source-supported in-betweens or an intentional brief occlusion/reveal. Avoid changing apparent body scale, ghosting two incompatible faces, uncontrolled crossfades or random glitch cuts.
- The user wants the anime's acting. Compare key poses, expression, spacing and timing against the source. Do not label a reconstruction exact unless the comparisons support that claim. Refine what is possible and record the remaining fidelity limit without inventing a studio asset.

The supplied actor samples poses at 30 Hz. For the refined live renderer, continuous interpolation may render at display cadence while intentional anime holds remain holds. Keep the keyframes editable; do not bake the only source into a GIF.

## Source effects and compositing

Use the real shark simulation and horizon renderer. Their prepared factories are usable without Node or a build step in the previews. The source folder and portable source-builder are provided to support deeper integration.

The five plate-based panels retain recorded source motion. Raising the encoded rate or repeating frames does not create new source acting. The cat has 129 manually calibrated/refined eye-anchor samples; refine alignment at intervening frames and through the full turn. Preserve natural whole-cat bounds. Its colour scan and beams must use the same video time. Cover unrelated source UI copy deliberately, as the provided prototype does; do not leave a floating fragment of the original heading.

Keep the skull and sword together with rain. Keep the dotted loop and surrounding wave. Preserve the reaching-hands choreography and contact location. Only the elastic stack's branded ending was removed in the supplied local loop.

## GIF and companion delivery

Author an editable scene at display cadence and prefer a **50 FPS GIF target with exact 20 ms frame delays** for the flagship continuous travel/takeover sequences where the result and payload support it. A **25 FPS, 40 ms** edition is an acceptable measured fallback when it retains visual quality. Do not force nominal 30 FPS into uneven GIF delays and call that smooth. Do not inflate frame counts with duplicates as proof of better animation.

For GitHub deliver high-quality GIFs plus intentional static images. Preserve source pace. Use one scene render path for companion, static exports and animation. Prefer a fixed palette and correct disposal for transparent actor GIFs; inspect them on ink, paper and checkerboard. Keep lossless/RGBA masters and efficient WebP/MP4 companion editions alongside GIF derivatives where useful.

GIF size is a measured tradeoff. Start with a short meaningful loop at its actual README display size. Optimise palette, duration, spatial detail and duplication before discarding the source's appearance. Keep root loading practical; record file sizes and actual display geometry. Do not silently turn every requested moving scene into a still.

Unbounded live simulations do not require an artificial periodic world reset. Their GIF excerpts do need a clean authored loop seam or a deliberate hidden bridge. Do not use an unexplained teleport, clipped model or backwards animal movement to cover a bad seam. The hands/rain/dots have source loop behaviour; inspect their actual encoded resets. Recheck the cat takeover and model handoffs in uninterrupted playback.

## Inspection

Inspect desktop and portrait, every pose change, loop seam, pause/resume, replay and reduced-motion initial state. Keep important captions stable while they are read. Pause/halt off-screen scenes and document visibility to avoid decoding and rendering every panel unnecessarily. Keyboard equivalents must exist for meaningful pointer-only interactions.

Watch actual normal-speed playback for at least two complete story/actor loops. Sampled frames, an export completing, a recording being produced or a nominal FPS value do not prove perceived smoothness. Record precisely what was watched and what remains unverified. Do not certify physical display behaviour, Safari or a device that was not tested.

