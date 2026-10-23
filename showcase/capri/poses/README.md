# V8 pose source map

The three RGBA masters are supplied AI-assisted upper-body fan art, with near-opaque alpha normalized by the scene builder. They are not official model sheets, extracted anime footage or user-approved production assets.

The supplied [ASSET_RECORD.json](ASSET_RECORD.json) is retained verbatim as a handoff record. Its original `assets/pose-studies/` paths map to [references/](references/); its `references/character/` paths map to [original-references/](original-references/). Exact prompts, the corrected pointing study and original reference-frame hashes remain there. An earlier clipped pointing version was not supplied in this pack; none is fabricated or substituted.

[ANCHORS.json](ANCHORS.json) records the actual imported hashes, measured source-pixel landmarks, source dimensions and scene scales. [Alpha proof](alpha-proof.png) composites these masters on ink, paper and checkerboard. Fully transparent RGB is never interpreted as a matte color; black anatomy stays intact.

[Build and motion method](../../../docs/CAPRI_ACTOR.md) · [Scene builder](../../../tools/build_capri_scene.py)
