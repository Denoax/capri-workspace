# Character and display sources

This private repository follows Mani's supplied V3 composition. Actual Capri footage, eyes, jaw, magenta silhouette and long hands define the first image. The previous abstract graphics and the provisional V2 two-panel/head-sprite direction are not used. No generated media, synthetic substitute character or persistent face tearing is included.

## Selected footage

Approved pieces use sources 12/19; V5 selects 1/14/20 as recorded below. The collection contains overlapping scenes/crops; twenty downloaded files does not mean twenty unique scenes. Files 4 and 18 show D and file 6 is a meme; all are excluded from branding.

- **Hero — source 19, BluRei:** [original Tenor page](https://tenor.com/view/cyberpunk-2077-cyberpunk-cyberpunk-edgerunners-capri-gif-3999370720653516186). Actual 498×281 rendition, 120 frames, 4 seconds. Source acting and complete source-image box are retained beneath the specified diagonal composition. No uploader mark is deliberately erased. The full source is in [sources](../showcase/capri/sources/capri-19.gif).
- **Workflow — source 12, emdzejus:** [original Tenor page](https://tenor.com/view/cyberpunk-cyberpunk-edgerunners-cyberpunk-2077-capri-capricorn-gif-3649282024278917159). Actual 498×281 rendition, 11 frames, 1.1 seconds; the supplied representative still provides the eye/face edge. [Full source](../showcase/capri/sources/capri-12.gif).

Uploader credit identifies the upload, not ownership of the underlying anime. Character footage belongs to the relevant creators/rights holders. No asset-specific public software-brand redistribution grant is established. The consolidated repository stays private; unclear rights do not trigger a character-free substitute. No creator has been contacted.

## Composition and editable sources

[Hero SVG](../showcase/capri/hero.svg), [overlay SVG](../showcase/capri/hero-overlay.svg), [workflow SVG](../showcase/capri/workflow.svg) and [social SVG](../showcase/capri/social.svg) are editable. The masters are 1400×480, 1400×240 and 1280×640 respectively. The animated delivery is 1000×343, sampled at 12 fps over the original four-second source pace, with stable outlined title letters and a 96-color palette. Source imagery is enlarged in this composition; it is not a higher-resolution anime master. Static hero uses the supplied representative pose rather than animation frame zero.

**Barlow Condensed ExtraBold Italic**, copyright 2017 The Barlow Project Authors, is bundled unchanged with its [SIL Open Font License](../showcase/capri/fonts/OFL.txt). [Original typeface project](https://github.com/jpt/barlow). Display glyphs are already outlined in exported SVGs, so GitHub needs no custom font or CSS. Native Markdown retains GitHub's normal body and command typography. The font license is separate from anime-image rights and the pending code-license choice.

No standalone model or rig is claimed. The earlier incomplete cropped-head experiment is preserved privately rather than shipped as a complete pose.

## Rebuild

Use Pillow 12.3.0 and the system `rsvg-convert` executable. Outlined SVGs are the editable composition source; source footage and the OFL/font files are included.

```sh
python tools/build_capri_presentation.py
python tools/check_capri_presentation.py
```

The builder has no collector, live-state or network side effects. It does not install fonts or change controller dependencies. [BUILD.json](../showcase/capri/BUILD.json) records the actual export recipe; [SOURCES.json](../showcase/capri/SOURCES.json) preserves attribution and reuse limits. [Static README](README_STATIC.md) is the useful disabled-animation alternative. Preview play/pause JavaScript does not run in GitHub Markdown.

## V4 repository identity

The V4 README adds [graphic navigation and chapters](../showcase/capri/identity), a branching role map, an [Afterimage art page](AFTERIMAGE.md), a staggered triptych and an optional *Off the Grid* poster. They reuse sources 12 and 19 above; no new character source or permission grant is introduced. The original hero bytes remain untouched.

Whole source-image boxes are retained in the new still compositions. Source 19 frames 12, 54 and 92 form the triptych; frame 54 forms the poster. Source 12 frame 5 is the diagram/chapter expression. The original footage remains available for comparison. The stills are encoded as embedded JPEGs inside the SVGs to keep payload small; display lettering is outlined from the existing Barlow font. *Off the Grid* is original editorial copy, not a show quote or product claim.

```sh
python tools/build_capri_identity.py
python tools/check_capri_presentation.py
```

The identity builder requires Pillow and fontTools in a media-only environment. It does not alter controller dependency files, start models or replace the V3 hero builder. See [presentation references](DESIGN_REFERENCES.md) for the inspected design sources and [identity BUILD.json](../showcase/capri/identity/BUILD.json) for export details.

## V5 Afterimage

V5 builds on approved main `beac62ac9223a01ae90c9e8380bb7805d9c97a94`. The hero, identity navigation, chapter graphics, role maps, triptych and poster are preserved byte-for-byte. Only sources 1, 14 and 20 are added. Complete selected GIFs, uploader links and SHA256s are in [SOURCES.json](../showcase/capri/SOURCES.json).

| Source / uploader | Actual selected frames | Adaptation |
| --- | --- | --- |
| 1 · kiraGIFtendency | Frame 97, 4050 ms; 443×498 original | Asymmetric portrait, full source box and outlined CAPRI lettering. An upper-body crop, not a complete body. |
| 14 · emdzejus | Frame 0 for the still; all 43 frames, 0–4300 ms for motion; 498×281 original | Complete source box, with a manual hand-only foreground layer crossing an authored frame. No full-body sprite. |
| 20 · Strawhat131331 | Frame 101, 3370 ms; 498×281 original | Environmental movement study, including the other figure and industrial scene. |

Sources 3 and 22 were inspected as decoded sequences but not selected. The source-14/19 material overlaps in gestures; these uploads are not presented as newly discovered independent scenes. Stills and motion retain their complete source-image boxes and original marks. Uploader attribution does not clear underlying anime rights.

The interlude is **640×421, 5300 ms**: original 4300 ms acting, 400 ms extra opening hold, 200 ms extra closing hold, one 80 ms image-bound ink cut, then 320 ms on the opening pose. The title stays fixed. A shared 96-color palette avoids per-frame palette changes. The PNG uses the same first pose and composition. No optical flow or synthetic character frames are used. The root embeds only its unchanged hero; the new loop is on Afterimage.

The full-figure matte experiment damaged dark limbs and was rejected. The final composition retains the original image and uses only a small hand foreground layer. [Coordinates and timing](../showcase/capri/afterimage/COMPOSITION.json) · [Export manifest](../showcase/capri/afterimage/BUILD.json).

### Build the expansion

Use a separate media environment and the system `rsvg-convert` executable:

```sh
python3 -m venv .venv-media
. .venv-media/bin/activate
python -m pip install -r requirements-media.txt
python tools/build_capri_afterimage.py
python tools/check_capri_presentation.py
```

Media requirements pin Pillow 12.3.0 and fontTools 4.60.1. The V5 builder writes only `showcase/capri/afterimage`; it does not rebuild approved graphics or alter runtime dependencies, configuration, CI or locks. `COMPOSITION.json` records frame/mask/timing choices; static SVG masters use the existing OFL glyphs and have PNG alternatives. [Still README](README_STATIC.md) and [still Afterimage](AFTERIMAGE_STATIC.md) embed no GIFs.

The optional STL typography object is omitted because authenticated hosted viewer inspection is unavailable to this candidate. No character model, rig or rotatable hosted result is claimed. Public anime redistribution and the code license remain unresolved; private review does not clear them.

## V6 character guide

The root explanation uses whole source-frame insets: source 1/frame 97 (opening/Thinker), source 14/frame 0 (hands beside the handoff), and source 12/frame 5 (review). The existing selected-source hashes and uploader credits remain in [SOURCES.json](../showcase/capri/SOURCES.json). Insets retain the complete source boxes and are never mirrored or used as a purported complete cutout rig. No character frames, missing anatomy or visual media were generated.

[Editable outlined SVGs, delivery media and build hashes](../showcase/capri/explainer/BUILD.json) are built by [build_capri_explainer.py](../tools/build_capri_explainer.py). Desktop and portrait guides each run for 16 seconds, with 3.6-second reading holds and 0.4-second moves. One shared palette per guide avoids palette pumping. The complete static comic contains every beat. Speech is original educational copy, not canon dialogue.

Barlow Regular adds a readable speech face alongside the existing Barlow Condensed display face. Its source is [Google Fonts' Barlow directory](https://github.com/google/fonts/tree/main/ofl/barlow); copyright 2017 The Barlow Project Authors. Both are covered by the bundled [SIL OFL notice](../showcase/capri/fonts/OFL.txt). Underlying anime redistribution rights remain unverified.

Rebuild V6 in the same separate media environment with `python tools/build_capri_explainer.py`, then run `python tools/check_capri_presentation.py`. No network or runtime session is used by the builder.

## V7 transparent actor and quantitative lesson

V7 replaces rectangular character insets with the [transparent actor and alpha masters](CAPRI_ACTOR.md), preserving the panel/hero direction. The supplied edited pose is explicitly recorded as an AI edit, never compared with original-footage hashes as if identical. Original source integrity checks remain. Hand-layer articulation keeps face identity fixed and is reported as authored 2D motion. [Recipe and build record](../showcase/capri/actor/ANIMATION.json).

[Worked numeric lesson](CONTEXT_BUDGET.md) uses original outlined SVG, an editable six-call scenario and an offline calculator. Every chart labels the counts as assumptions, not CAPRI usage; cache caveats remain visible. Runtime evaluation, profiles and dependencies are unchanged.


## V8 composition candidate — 23 October 2026

V8 preserves the approved hero and all earlier source/master assets. Three supplied AI-assisted upper-body studies now drive a single editorial stage, compact tail-free dialogue and a packet with an anchor-derived leader. No new generated imagery, runtime/fixture/CI/lock changes, public release or human acceptance is implied. [Pose provenance and build](CAPRI_ACTOR.md). Earlier V7 root panels remain in `showcase/capri/explainer/` and Git history; they are retired from the root.

[Source-to-implementation record](DESIGN_REFERENCES.md#v8-composition-candidate--23-october-2026).
