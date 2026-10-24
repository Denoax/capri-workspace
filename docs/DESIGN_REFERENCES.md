# Presentation research and adaptation

23 October 2026 · based on CAPRI `ae6361a488820263fbe12bcca08ac64e26dc4565`.

Mani approved the character-led hero direction and requested an artistic overhaul of the rest of the repository, including optional character art that does not explain the software. The original hero and implementation history remain the foundation. The project name stays **CAPRI**: changing a working slug would add link migration without strengthening the character identity. *Afterimage* names the visual appendix, not a second project or repository.

## Published references inspected

| Reference | What was inspected | Adaptation in CAPRI |
| --- | --- | --- |
| [Catppuccin](https://github.com/catppuccin/catppuccin) | Actual README source: centered compact navigation, theme-aware `picture` elements, social icon links, palette details and collapsed tables | Theme-aware chapter lettering, image links and expandable technical depth. Colors and graphics are CAPRI's own; no Catppuccin artwork copied. |
| [HyDE](https://github.com/HyDE-Project/HyDE) | README source and actual banner image: a coherent identity continuing through documentation links and sections | Display lettering and graphic chapters extend below the hero. HyDE's font, logo and palette are not reused. |
| [Gum](https://github.com/charmbracelet/gum) | README source and actual gum-pack illustration: a product with strong art direction followed by practical animated examples and usable commands | Art and utility alternate. The character triptych is explicitly artwork; it is never passed off as a terminal demonstration. |
| [Hyprland](https://github.com/hyprwm/Hyprland) | README source, linked header asset and concise project navigation | Keep the repository recognizable and useful around the artwork. The visual refresh does not require renaming the code or moving implementation directories. |

These are composition references, not evidence that a design produces stars or that all references are equally suited to this project. No layouts, logos or third-party UI code are imported. The inspected readmes were current during this research; their upstream branches can change.

## What GitHub can render

- [Collapsed sections](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections): native `details`/`summary`, with blank lines around Markdown content.
- [Diagrams](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams): a fenced Mermaid flowchart can live inside an expandable section. The default visual map is authored SVG, so reading the workflow does not depend on Mermaid loading.
- [Formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax): relative links, custom anchors, code blocks, tables, alerts and footnotes.
- Catppuccin's actual README supplies a working example of `picture` theme selection. GitHub's own body typography and page chrome stay native. There is no custom README JavaScript, iframe, dashboard UI, working tab state or font injection.

The finished composition uses image-link navigation, dark/light chapter images, a branching vector diagram, syntax-highlighted setup commands, collapsible implementation notes, a document-index table, optional Mermaid, one factual status alert, a credit footnote, an art interlude and a separately expandable poster. The static edition contains no embedded animated media. There are no externally hosted statistics, tracking widgets, generic badge farms or invented live values.

## Source-to-implementation record

- `showcase/capri/identity/nav-*.svg`: actual links styled with outlined Barlow lettering and the established hard-edged geometry.
- `chapter-*-dark.svg` / `chapter-*-light.svg`: one real section title, native-theme contrast; no eyebrows or footer slogans.
- `loop-map.svg`: documented role order, Thinker report, human decision and the held uncertainty branch. It describes architecture, not a successful live run.
- `afterimage.svg`: whole source-image boxes from source 19 at frames 12, 54 and 92. Reframing the same clip does not create three independent sources.
- `poster.svg`: an editorial composition, *Off the Grid*. The phrase is original display copy, not a Capri quote or software capability.
- Existing source 12 is used directly for the expression loop. No new character source, generated art, fabricated anatomy or complete standalone model is introduced.

The identity builder reads only already-selected character footage and the bundled OFL font. It writes only the identity graphics. The original V3 builder remains separate and the approved hero is not rebuilt by this change. Source image rights and the private visibility boundary remain documented in [ASSETS.md](ASSETS.md).


## Source-match presentation candidate

The approved first three-panel comic, Manrope/Inter typography and seven source treatments are implemented separately from the preserved banner and runtime. [Source-to-implementation, notices, acting and rebuild record](SOURCE_MATCH.md). New reference sources are registered separately; the original hero/source selection remains unchanged. Five panels are footage composites; sharks and horizon use actual supplied native source. Unresolved rights remain recorded and the repository stays private.

V3 uses the existing source-match references as lesson compositions, with literal project copy and deterministic assumed-input graphics. The rejected V2 stripped layout is excluded. [Story/source mapping](VISUAL_STORY.md).
