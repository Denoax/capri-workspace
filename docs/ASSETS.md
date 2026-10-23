# Character and display sources

This private candidate follows Mani's supplied V3 composition. Actual Capri footage, eyes, jaw, magenta silhouette and long hands define the first image. The previous abstract graphics and the provisional V2 two-panel/head-sprite direction are not used. No generated media, synthetic substitute character or persistent face tearing is included.

## Selected footage

Only two sources from the larger research collection are shipped here. The collection contains overlapping scenes/crops; twenty downloaded files does not mean twenty unique scenes. Files 4 and 18 show D and file 6 is a meme; all are excluded from branding.

- **Hero — source 19, BluRei:** [original Tenor page](https://tenor.com/view/cyberpunk-2077-cyberpunk-cyberpunk-edgerunners-capri-gif-3999370720653516186). Actual 498×281 rendition, 120 frames, 4 seconds. Source acting and complete source-image box are retained beneath the specified diagonal composition. No uploader mark is deliberately erased. The full source is in [sources](../showcase/capri/sources/capri-19.gif).
- **Workflow — source 12, emdzejus:** [original Tenor page](https://tenor.com/view/cyberpunk-cyberpunk-edgerunners-cyberpunk-2077-capri-capricorn-gif-3649282024278917159). Actual 498×281 rendition, 11 frames, 1.1 seconds; the supplied representative still provides the eye/face edge. [Full source](../showcase/capri/sources/capri-12.gif).

Uploader credit identifies the upload, not ownership of the underlying anime. Character footage belongs to the relevant creators/rights holders. No asset-specific public software-brand redistribution grant is established. This completed character-led candidate stays private for review; unclear rights do not trigger a character-free substitute. No creator has been contacted.

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
