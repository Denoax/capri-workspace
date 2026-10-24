# CAPRI visual story

The V4 presentation refines V3's geometry and request inspection. The product definition, approved hero, three full-body poses, all seven source-reference families and canonical input illustration remain. The horizon graph and shark brief now have independent landscape frames. Reaching hands/checking and retained requirements/coordination are matched portraits. The original compact elastic stack closes toward offline setup.

## Local companion

Open [the companion](../showcase/capri/source-match/companion/index.html) locally, keeping adjacent `actor-data.js`. Fonts and source footage are embedded. A modern browser needs no account, server or original machine path. GitHub displays media and links rather than executing this player. The [single-column static/mobile edition](README_STATIC.md) carries the complete meaning without JavaScript or motion. [Preserved historical source player](../showcase/capri/source-match/companion/source-match.html).

Request selection changes mathematical inspection state and exact integer readouts. It never resets, seeks or replays the native horizon engine, or changes its play/pause state. A short guide transition emphasizes the selected existing row; intermediate marker positions are not measured requests. Reduced motion switches immediately. Native scene play/pause, replay and time seeking still own art time. Deterministic exports explicitly sample their scene clocks and graph emphasis together. This separation preserves reproducible capture without making ordinary selection replay hundreds of native renders.

The additional-input control selects precomputed rows. Keyboard/touch controls, native disclosures, source-error/static fallback, WebGL fallback and hidden/offscreen pause remain. Live paints skip graph DOM mutations; graph nodes and geometry are cached, and only the visible chart changes when mathematical state changes.

## One frame contract

[format.json](../showcase/capri/story/format.json) is the geometry authority. It defines 1200×675 landscape and 600×900 portrait families, insets, gutters, type hierarchy, source proportions, placements, portrait pairs and the single 768px mobile breakpoint. The existing 1000×343 hero is the byte-preserved header exception. The builder, CSS compiler, live scaling, exporter, Markdown builder and validator consume that contract.

Fixed artboards are recomposed, then uniformly scaled into a reserved frame. Canvas/source proportions are preserved. Native controls and longer explanations remain outside the artwork. The companion truly stacks portrait pairs at the breakpoint. GitHub's native tables retain two columns; readable Markdown carries every essential rule/number, with full portraits and the separate single-column static route. Viewport media queries do not measure GitHub's content-column width.

[Konata's pinned README](https://github.com/Denoax/konata-hyprland-dotfiles/blob/a9f433ad9cf5b870ee18ceed72d7200f402008e8/README.md) supplies the formatting reference: full-column images, equal paired frames and native captions. Its four inspected screenshots are 1600×900. CAPRI's 600×900 portrait family is an authored adaptation, not Konata's screenshot geometry. CAPRI keeps its own palette, fonts, source art and explanation.

## Canonical inputs and source continuity

[story.json](../showcase/capri/story/story.json) refers to the unchanged [six-call assumptions](../showcase/capri/source-match/source/assets/data/context-budget.json). `tools/capri_context_budget.py` supplies Markdown, SVG geometry and controls through the [model projection](../showcase/capri/story/model-results.json). The 180k/90k/60k totals, curated alternative, 60k+H sensitivity and 30k additional-input break-even remain illustrative inputs, not measured savings, active occupancy or equal-quality evidence. Fixture A retains the authoritative correction and compatible rules.

The hero, thirty cutout layers, masks, pose keys, RGBA/RGB/alpha masters, original factories, source footage and provenance remain retrievable. Original V3 output is recoverable at commit `6a5d0b3746c49cd5da058b3d458497e267edc449`; unused historical variants are identified separately in the build manifest. Active filenames state their actual orientation.

[Source/rights record](SOURCE_MATCH.md#sources-and-rights) · [Current composition identity](../showcase/capri/story/SOURCE_RECORD.json) · [Creator catalog](../showcase/capri/source-match/source/SOURCE_CATALOG.json). MIT/OFL notices and unresolved shark/footage/character rights remain unchanged; keep private. No new generated art or product telemetry is used.

## Rebuild and verification

Use the recorded media environment (Python, Pillow, NumPy, websockets), FFmpeg and Chromium. Set `CAPRI_CHROMIUM` if needed. No runtime dependency, lock, controller or CI policy change is required.

```sh
python3 tools/build_capri_story.py
python3 tools/export_capri_story.py --evidence /your/task-private/media-evidence
python3 tools/build_capri_story_readme.py
python3 tools/build_capri_source_match_manifest.py
python3 tools/check_capri_presentation.py
python3 tools/check_capri_graph_browser.py --evidence /your/task-private/graph-check
```

All files remain below the unchanged 8MB checkout snapshot bound. Original large references use verified lossless chunks and materialize outside the runtime checkout. Native-horizon frames can vary bytewise between clean renders; source/data/geometry, semantic checks and exact exported identities are reported separately.

Performance evidence distinguishes graph-only JavaScript work, selection-to-two-rAF presentation proxies, running-effect frame intervals and actual encoded playback. RAF intervals are not GPU timings. Software Chromium is not physical GPU/device qualification. Build checks and screenshots do not establish uninterrupted perceived smoothness or human visual approval. Current [native status](STATUS.md) and [benchmark protocol](BENCHMARK_PROTOCOL.md) remain authoritative; model comparisons stay unrun.
