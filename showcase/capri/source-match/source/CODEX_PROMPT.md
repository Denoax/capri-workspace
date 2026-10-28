# Implement the approved CAPRI presentation

You are the implementing Codex worker for Mani. The user has approved these designs and explicitly approved this ZIP and implementation handoff. Implement the actual repository presentation, refine the character animation, verify the result, and push a GitHub testing branch before your final handoff. Do not stop after planning or ask for the same approval again.

Read and apply **`$reference-led-design`**. If the installed skill is unavailable, read `policies/reference-led-design/SKILL.md` and apply its bundled rules directly. The complete policy folder is supplied; missing global installation is not a blocker. Read local/ancestor `AGENTS.md` and `AGENTS.override.md` instructions wherever applicable. This packet is task material, not permission to replace unrelated local instructions.

## Start with the approved inputs

Read `START_HERE.md`, then `specs/APPROVED_DIRECTION.md`, `specs/ACTING_AND_EXPORT.md`, `specs/EXPLANATION_AND_NUMBERS.md` and `specs/ACCEPTANCE_AND_RETURN.md`. Open the three standalone previews under `preview/`; their index is `preview/INDEX.html`. Inspect real playback and source material rather than assuming the package's syntax/hash checks establish visual quality.

The approved foundation is the **first three-panel Handoff comic**, with upright Manrope headings, Inter body text, full-body Capri and no decorative eyebrow/footer labels. The user rejected Collision, Acid press, a giant poster and the later stacked collision sequence. Those are not alternatives to revisit. The existing approved banner stays byte-identical.

The latest approved change is to use all seven supplied references much more closely, essentially one-to-one in their recognisable appearance and motion, then integrate Capri and the actual explanatory content. Do not replace the sharks with arbitrary dots, the ray-traced black hole with a flat ellipse, the skull-and-sword scene with generic rain, the scanline cat with a new blob, or the reaching hands with a generic transfer arrow. Preserve the supplied compositions, density, silhouettes, camera relationships and timing as closely as the permitted source supports. Theme changes, meaningful text replacement and Capri integration are the requested adaptations.

`design/approved/` holds the exact approved fragments as editable source. `native/` contains prepared source-based shark/black-hole factories and the current character rig. The five remaining panels are explicitly **reference-footage composites**, not native implementations of those recordings. Their clips and full reference recordings are included. Keep that distinction in provenance and do not pretend a recording is executable source code.

## Use the current repository, preserve newer work

- Repository: **`https://github.com/Denoax/capri`**, private, default branch `main`. Keep its name, visibility and history.
- Observed current `main`: **`521598688be57fdc56a26ff15a4b4eddb65d6433`**. This includes newer V3 recovery/runtime work. Fetch and inspect the actual latest remote before implementation; if main has advanced, preserve the newer work and record the fresh base.
- The V8 presentation branch `testing/capri-v8-composition-01a1688d` at `d6a738b631d458d32f1857d8a42e4c091ecb655c` is historical presentation context. **Do not base a replacement repository on V7/V8 or merge their older runtime wholesale over current main.** Selectively reuse presentation assets if needed.
- Current-main CI is no longer the old collector-failure story: the two recorded Offline tests runs for `5215986` succeeded. The source's status still says the native workflow is experimental and BLOCKED pending launch/recovery qualification. Preserve that distinction. Recheck the implementation commit's CI rather than copying any historical outcome.
- Read `intake/REMOTE_OBSERVATION.json` and the pinned current README/status/asset/benchmark snapshots. These are intake evidence, not files to blindly copy back over a newer checkout.

Work under **`/home/mani/Documents/CAPRI/`**: separate `worktrees/`, `previews/`, `reviews/` and `evidence/` directories. Do not use Kattis or the desktop as project storage. Preserve all active work and create an isolated worktree and a new branch such as `testing/capri-source-match-20261023-<session>`. Inspect an existing branch/path before reusing it. Never reset, clean, force-push or relocate unrelated work.

Verify the unpacked packet before using it:

```sh
python3 tools/verify_bundle.py
```

That verifier is read-only. It checks packet integrity, not the repository or the design's quality. `REBUILD.md` explains the self-contained previews and optional portable asset builders.

## Implement the visible result

Recompose the **root README and actual presentation assets**, keeping quickstart, current status, technical documentation, credits and the human decision readable. Do not merely add a new gallery while leaving the root visually unchanged. Preserve the first comic's three-beat arrangement; connect Plan/Build/Review to the actual Thinker/Doer/Reviewer roles.

Integrate the highest-priority reaching-hands handoff, the real shark field, the source black hole, the retained-context skull/sword scene, the cat takeover and the dot-wave interlude as distinct coordinated panels. The elastic stack is lower priority and may live in the art/companion edition if it weakens the main reading order. Keep multiple panels, not one huge hero. Use a short explanation or an inspectable worked example where it belongs; do not fill every surface with slogans, badges or invented telemetry.

Ship both editions:

1. **GitHub-native README:** rendered GIFs/static images, ordinary links, anchors and native `details/summary`. Text inside graphic assets can use the supplied fonts; GitHub's native Markdown body uses its own typography. Do not claim custom CSS, scripts, canvas, live WebGL, hover actions or buttons execute in the README.
2. **Local interactive companion:** the source-based visual effects, motion controls and meaningful interactions, using the same content, scene state and edited character assets as the exports. Keep it local/private; no public deployment or account-setting changes are authorised.

Provide a complete static edition and descriptive alt text. Keep explanations readable while art moves, keyboard actions usable and reduced-motion initialisation effective. No audio or voice buttons in this iteration.

## Finish Capri's acting

The supplied rig is a starting implementation, **not exact anime acting**. It has ten independently moving parts, head turns, blinks and authored holds, but anatomy, seams, expressions and choreography still need refinement. Use the included actual anime clips and decoded samples to compare full-body proportions, angular limbs, green face regions, eyes, grin, magenta hair and exaggerated gestures.

Develop at least three distinct full-body poses using the supplied Plan/Build/Review masters. Keep all hair tips, fingers and feet on a generous transparent logical canvas. Normalise eye-line and apparent head size; never independently fit each sprite's bounding box. Refine pose-specific rigging and transitions. Do not apply the Plan mask to different anatomy without inspecting it. Avoid rigid-card bobbing, rubbery mesh warps, detached joints, dissolving through two visible faces and visible rectangular cutoffs.

Use independent head/torso/arm/leg motion, anticipation, timed holds, kicks, turns and purposeful travel. Preserve silhouette, segment length and a stable camera. Drive gesture anchors, packet positions, phase, callouts and exports from one scene timeline. Raising encoded FPS or duplicating source frames is not new acting. See the motion spec for live interpolation and GIF targets.

The user's earlier explicit **“you may use AGI for this”** applies to Capri character cutouts, pose repairs and animation-source improvements. This permission remains specific to the character. Do not generate UI mockups, diagrams, backgrounds, charts, benchmark evidence or unrelated replacement media. Preserve approved originals and exact provenance. The new character is fan-art reconstruction, not an official studio model or extracted complete rig.

## Explain the idea honestly

Use `assets/data/context-budget.json`: six assumed calls total 180k growing-history, 90k curated-session and 60k scoped-role input tokens. The 66.7% reduction is arithmetic under those assumptions, **not measured CAPRI savings, speed, cost or quality**. A curated single session also improves that example. Preserve the current source's benchmark protocol, unknown occupancy and unrun comparisons.

Keep `blank → Untitled`, scope, case, whitespace and type constraints together in the handoff example, with authoritative originals retrievable. Explain focused working context and explicit handoffs. Do not say prompt caches get clogged and delete instructions, that separate contexts guarantee retention, or that multi-agent systems always use fewer tokens. Account for coordination, outputs, retries, compaction and cache reuse when discussing real efficiency. Do not launch new paid benchmarks, model sessions or recovery operations for this presentation task.

## Rights, scope and completion

The repository remains private. Keep credits and provenance with reused material. Horizon is MIT with its notice supplied; fonts are OFL. The shark repository has no explicit licence in the inspected snapshot; the five video-reference redistribution permissions and underlying character-art rights are unresolved. User approval of the design is not a new creator licence. Continue the authorised private implementation/review work without turning that into an approval interruption; keep unresolved material clearly recorded and do not publish it publicly, claim ownership or silently assign a blanket MIT licence. Do not contact creators or send messages on the user's behalf.

Change presentation, explanatory/art documents, media builders and the companion. Do not change controller logic, runtime tests, confinement, live state, profiles, client qualification, evaluation results, dependency locks or CI policy to make this task pass. Preserve the approved hero SHA-256 **`e505d35ebb8eea5daa13fda24ed32db7a6a64aabda3e63835ee4cf8813f39517`**. Update presentation-specific checks when their old visual assumptions are superseded by this approval; retain meaningful integrity, link, timing and source checks.

Work in bounded phases with one active writer. Keep a short saved checkpoint containing current base, approved scope, active files, decisions and remaining checks. At context boundaries reread this prompt and the relevant phase spec. Read large source/media programmatically; do not flood the working context with embedded base64, whole archives or unrelated runtime history. Do not start the blocked CAPRI controller to orchestrate its own presentation work.

Before final handoff, verify actual responsive browser output, encoded playback, static/reduced-motion routes, links, alpha and animation seams. Observe uninterrupted motion rather than awarding smoothness from selected frames. Inspect hosted GitHub rendering where authenticated access is available. Report unavailable checks honestly and complete independent work.

**Commit and push completed implementation to the GitHub testing branch before ending. Verify that the remote branch SHA equals the tested local HEAD.** A local commit or attempted push is not completion. Do not merge to main or deploy. If a concrete auth/network restriction blocks the push, preserve everything and report that blocker; never claim a successful push.

Return the verified branch/commit link, local playable preview, static edition, patch, complete reproducible review ZIP and concise review Markdown under Documents/CAPRI. Include source/asset records and measured check outcomes; keep runtime CI, native qualification and visual acceptance separate. Use the existing verified delivery/Obsidian convention if present, without inventing a receipt. Ask for visual feedback only after the implementation and testing branch are reviewable.
