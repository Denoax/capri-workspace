# Preview and source rebuild

The supplied previews are complete review pages with fonts, model parts and required media embedded. Open preview/INDEX.html. No original ChatGPT workspace, remote account or Node installation is needed to open them. Browser WebGL 2 is needed for the live black-hole renderer; its provided still fallback is not proof of GPU execution. A normal modern browser can show the media-backed scenes. These pages have not been browser-qualified in this packaging environment.

If the browser requires HTTP for local media, the implementing Codex worker can run:

```sh
python3 tools/serve_preview.py
```

It binds only 127.0.0.1 and prints the exact local preview URL. It does not open a browser or publish a site. The user should not need to type commands for the worker.

## Verify before implementation

```sh
python3 tools/verify_bundle.py
```

This stdlib-only check verifies the payload against MANIFEST.json. The bundle is the immutable input. Keep derived experiments in build/ and copy implementation assets into the isolated Git worktree; do not modify the packet and then report its original hash as verified.

## Rebuild the standalone exports

```sh
python3 tools/build_preview_exports.py
```

The exporter reads design/approved/, uses the frozen helper and assets under tools/vendor/visualize/, and embeds all three bundled font families. It writes preview/*.html. There is no fetch, hotlinked required media or machine-specific path. Browser/font differences still require visual inspection. The exported documents may exceed the inline-fragment size limit because they contain their font binaries; the original approved fragments remain unchanged.

## Optional editable source builders

Precompiled native factories, component textures, rig JSON and compositing clips are already supplied. A missing optional build tool does not prevent the worker from opening the previews or using those assets. Use a separate media environment when rebuilding. Do not edit controller dependency locks, install globally or change OS/browser settings to satisfy a media tool.

BUILD_ENVIRONMENT.json records the actual packaging environment. tools/requirements-media.txt contains its Python media versions. One local environment option is:

```sh
python3 -m venv build/.venv-media
build/.venv-media/bin/python -m pip install -r tools/requirements-media.txt
build/.venv-media/bin/python tools/rebuild_jointed_actor.py
build/.venv-media/bin/python tools/export_rig_layers.py
build/.venv-media/bin/python tools/prepare_reference_plates.py
```

The jointed builder derives Plan's masks, component transforms and diagnostic motion exports from assets/characters/masters/plan.png and the editable keys. The layer exporter writes build/rig/rig-assets.json. The native actor's blink overlays live in native/actor-rig.js; the diagnostic WebP/atlases are not a complete replacement for that renderer. Refine Build/Review using their own anatomy and anchors. The rejected flexible-warp experiment is not a dependency.

The reference-plate builder needs system ffmpeg with libx264. It reads the bundled full reference recordings, preserves their source pace, applies the recorded crops/encodes and uses the forward/reverse stack closure. The cat calibration uses manually identified key positions plus local dark-eye refinement, writing build/reference-plates/CAT_EYES.json. Inspect beam alignment across actual playback after any video/crop/timing change.

To regenerate the prepared effect factories from the frozen TypeScript/ES-module subset:

```sh
node tools/rebuild_source_factories.mjs
```

This optional builder uses Node 24's type-stripping transform and writes build/native/. The already supplied native/*.js runs without Node in the standalone previews. The frozen upstream subset is complete for this adapter build; it is not presented as a full upstream checkout with all original demo UI files.

No optional builder mutates the CAPRI controller, invokes models, authenticates, pushes a branch or merges code. For final GIFs and static assets, render the refined implementation from its shared scene clock and follow specs/ACTING_AND_EXPORT.md. Do not treat the old diagnostic exports as final animation approval.
