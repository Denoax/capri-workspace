# Character and display sources

This private repository follows Mani's supplied V3 composition. Actual Capri footage, eyes, jaw, magenta silhouette and long hands define the first image. The previous abstract graphics and the provisional V2 two-panel/head-sprite direction are not used. No generated media, synthetic substitute character or persistent face tearing is included.

## Selected footage

Only two sources from the larger research collection are shipped here. The collection contains overlapping scenes/crops; twenty downloaded files does not mean twenty unique scenes. Files 4 and 18 show D and file 6 is a meme; all are excluded from branding.

- **Hero — source 19, BluRei:** [original Tenor page](https://tenor.com/view/cyberpunk-2077-cyberpunk-cyberpunk-edgerunners-capri-gif-3999370720653516186). Actual 498×281 rendition, 120 frames, 4 seconds. Source acting and complete source-image box are retained beneath the specified diagonal composition. No uploader mark is deliberately erased. The full source is in [sources](../showcase/capri/sources/capri-19.gif).
- **Workflow — source 12, emdzejus:** [original Tenor page](https://tenor.com/view/cyberpunk-cyberpunk-edgerunners-cyberpunk-2077-capri-capricorn-gif-3649282024278917159). Actual 498×281 rendition, 11 frames, 1.1 seconds; the supplied representative still provides the eye/face edge. [Full source](../showcase/capri/sources/capri-12.gif).

Uploader credit identifies the upload, not ownership of the underlying anime. Character footage belongs to the relevant creators/rights holders. No asset-specific public software-brand redistribution grant is established. The consolidated repository stays private; unclear rights do not trigger a character-free substitute. No creator has been contacted.

## Composition and editable sources

[Hero SVG](../showcase/capri/hero.svg), [overlay SVG](../showcase/capri/hero-overlay.svg), [workflow SVG](../showcase/capri/workflow.svg) and [social SVG](../showcase/capri/social.svg) are editable. The masters are 1400×480, 1400×240 and 1280×640 respectively. The animated delivery is 1000×343, sampled at 12 fps over the original four-second source pace, with stable outlined title letters and a 96-color palette. Source imagery is enlarged in this composition; it is not a higher-resolution anime master. Static hero uses the supplied representative pose rather than animation frame zero.

**Barlow Condensed ExtraBold Italic**, copyright 2017 The Barlow Project Authors, is bundled unchanged with its [SIL Open Font License](../showcase/capri/fonts/OFL.txt). [Original typeface project](https://github.com/jpt/barlow). Display glyphs are already outlined in exported SVGs, so GitHub needs no custom font or CSS. Native Markdown retains GitHub's normal body and command typography. The font license is separate from anime-image rights and the pending code-license choice.

No standalone model or rig is claimed. The earlier incomplete cropped-head experiment is preserved privately rather than shipped as a complete pose.

## Rebuild

Install the media-only packages with `python -m pip install -r requirements-media.txt` and provide the system `rsvg-convert` executable. Outlined SVGs are the editable composition source; source footage and the OFL/font files are included.

```sh
python tools/build_capri_presentation.py
python tools/check_capri_presentation.py
```

The builder has no collector, live-state or network side effects. It does not install fonts or change controller dependencies. [BUILD.json](../showcase/capri/BUILD.json) records the actual export recipe; [SOURCES.json](../showcase/capri/SOURCES.json) preserves attribution and reuse limits. [Static README](README_STATIC.md) is the useful disabled-animation alternative. Preview play/pause JavaScript does not run in GitHub Markdown.

## V4 repository identity

The V4 README adds [graphic navigation and chapters](../showcase/capri/identity), a branching role map, an [Afterimage art page](AFTERIMAGE.md), a staggered triptych and an optional *Off the Grid* poster. They reuse sources 12 and 19 above; no new character source or permission grant is introduced. The V4 pass retained the original hero bytes. V8 later adds one in-art subtitle; its unmodified input is pinned in sources/hero-v7/.

Whole source-image boxes are retained in the new still compositions. Source 19 frames 12, 54 and 92 form the triptych; frame 54 forms the poster. Source 12 frame 5 is the diagram/chapter expression. The original footage remains available for comparison. The stills are encoded as embedded JPEGs inside the SVGs to keep payload small; display lettering is outlined from the existing Barlow font. *Off the Grid* is original editorial copy, not a show quote or product claim.

```sh
python tools/build_capri_identity.py
python tools/check_capri_presentation.py
```

The identity builder requires Pillow and fontTools in a media-only environment. It does not alter controller dependency files or start models. The current hero-only derivative builder is documented in [V8 build notes](VISUAL_STORY.md). See [presentation references](DESIGN_REFERENCES.md) for the inspected design sources and [identity BUILD.json](../showcase/capri/identity/BUILD.json) for export details.


## Source-match presentation candidate

The approved first three-panel comic, Manrope/Inter typography and seven source treatments are implemented separately from the preserved banner and runtime. [Source-to-implementation, notices, acting and rebuild record](SOURCE_MATCH.md). New reference sources are registered separately; the original hero/source selection remains unchanged. Five panels are footage composites; sharks and horizon use actual supplied native source. Unresolved rights remain recorded and the repository stays private.

The [V3 story record](VISUAL_STORY.md) connects the preserved assets to the current explanatory compositions; no new generated media is used.

## Compact format V5

The original hero/source records remain. Six480×640 portrait compositions reuse the three-pose rig, native sharks/horizon and credited hands/dots/cat footage. A separate480×540 deterministic graph retains the canonical inputs. Rain and stack use small480×320 root vignettes; their source lessons remain interactive. `showcase/capri/story/format.json` defines numeric display caps and fixed uniform placements, and `SOURCE_RECORD.json` maps root/companion roles. The thin `accent.svg` is independently authored CAPRI geometry informed by published separator roles; it contains no third-party art. Source masks, anatomy, originals and notices are unchanged; keep private.


V6 annotated sizing adds marked panel/graph-wide/support-wide derivatives from the same editable source. Original V5 portrait/mobile and unmarked handoff/checking, hero and accent files retain their byte identities. Screenshot authority/hashes and explicit root/mobile mapping are recorded in story/format.json and SOURCE_RECORD.json; no new generated visual media or source assets.


V7 derives the handoff/checking panel+portrait variants and restores original-paced rain/stack GIFs for both support layouts. separator.gif/png and identity.svg/identity-mobile.svg are independently authored by build_capri_separator.py/capri_story_identity.py from the user motion contract and supplied fonts. Original footage, masters/rig/masks, hero, notices and unaffected V6 exports are retained. No generated-media source added.
