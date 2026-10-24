# Capri desktop V2

Native Quickshell/Qt Quick presence, speech bubbles and conversation, with a Python coordinator. V2 preserves the inherited character art and the direct ChatGPT conversation adapter. It never starts the separate three-role runtime or changes the root showcase.

The interaction study is a reference, not the application. Offline responses and provider fixtures are labelled separately from real connected-model evidence.

## Setup

Target host: Arch/Hyprland, Quickshell 0.3.1, Qt 6.12, Python 3.11+, systemd user manager and bubblewrap. Native session/browser helpers need python-dbus/python-gobject. Input-idle needs ext-idle-notify v2, wayland-scanner, a C compiler and wayland-client. Existing gio, playerctl, wpctl and pw-play provide typed desktop actions and sound. No root daemon or global Codex changes are required.

Reuse the installed isolated Python environment and pinned assets. For a fresh setup:

```sh
CAPRI_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/capri"
python3 -m venv "$CAPRI_DATA_DIR/venv"
"$CAPRI_DATA_DIR/venv/bin/python" -m pip install --require-hashes -r requirements.lock
python3 tools/import_assets.py /path/to/CAPRI_DESKTOP_COMPANION_V1 "$CAPRI_DATA_DIR/assets"
python3 tools/build_input_regions.py "$CAPRI_DATA_DIR/assets"
python3 launcher.py run --screen OUTPUT_NAME
```

The work engine requires the exact Codex binary in [engine-pin.json](engine-pin.json). It checks SHA-256, uses a separate private profile and Capri's own account, and does not read another Codex auth store. An existing matching binary may be reused without its settings. Conversation remains available if work qualification is unavailable.

The V2 installer adopts only unchanged, manifest-registered V1 launch files. Preserve the running draft and verify the source before switching:

```sh
python3 tools/install_v2.py --baseline /verified/v1/companion --baseline-sha VERIFIED_V1_SHA --sha VERIFIED_V2_SHA
capri run
capri status
capri summon
capri stop
capri hide
capri quit
capri versions
```

`--autostart` enables the user graphical-session unit after host qualification. It does not prove reboot or suspend behavior. The protected supervisor selects immutable source versions, retains a last-known-good version and performs one bounded crash rollback. A changed installation file is preserved rather than overwritten by uninstall.

## Conversation and tasks

Click the actor or Reply for quick input. Open conversation retains full selectable output, search, history scrolling and drafts across collapse/restart. Settings contain account/model, cadence, quiet hours, DND, snooze, pin/roam, reduced motion, mute/volume, selected projects, mail and maintenance. Escape preserves the composer. Native Stop and `capri stop` revoke pending authority even when the conversation is closed.

- **Chat** uses the original direct conversation adapter. Pasted commands remain conversation data.
- **Task** uses the pinned Codex stdio engine. Select exact project directories and optional typed desktop tools once in Settings. A native task grants up to 30 minutes, 64 actions and 24 inference requests. File contents and tool results inside that scope can reach the selected model. A project root is not automatically free of secrets.
- **Commands** preserves the deterministic V1 grammar: `/help`, `/apps`, `/open`, `/windows`, `/focus`, `/players`, `/player`, `/media`, `/volume`, `/folder`, `/organize`, `/apply`, `/undo`, `/work`, memory/export/reset and account controls. Its legacy `/work` is read-only; Task mode supports scoped writes.

Task commands receive selected read/write directory handles, isolated mount/PID/network namespaces, no credentials/desktop sockets or inherited secret FDs, a clean environment, resource limits and bounded output. Ordinary commands run for at most 30 seconds, within the task's remaining deadline. General network access, arbitrary GUI input, privilege escalation and live Capri/updater writes are unavailable. Extra exact directories or typed desktop tools pause for a concrete native decision. No repeated approval is needed for ordinary actions within the current task.

Tasks have separate private journals/checkpoints. Duplicate IDs cannot repeat effects. Interruption records uncertain effects; resume requires native owner input and inspection, with no automatic mutation replay. Account/model/session changes and lock, Stop or UI loss revoke task leases. Model prose, files, mail and memories cannot create authority.

## Initiative and selected sources

Local animation requires no model call. Read-only Wayland idle notifications wait for ten seconds without input; they do not capture keystrokes. The scheduler coalesces useful events, debounces for 30 seconds, persists hourly/daily budgets and three-hour topic cooldowns, and respects DND/fullscreen/quiet/snooze/pause. Missing idle or desktop DND signals suppress unsolicited delivery. A timer without useful context does nothing.

Selected project observation subscribes to top-level save events without reading filenames or contents. Chosen event metadata may be shared only when explicitly enabled. Actual recognized build/test tool results retain local evidence. Natural-pause check-ins require real prior task activity. Requested replies remain separate from unsolicited budgets. Clock jumps do not reset rolling limits. Quiet hours use an editable IANA timezone, initially America/Edmonton.

## Gmail and maintenance

Gmail needs its own official **Desktop app** OAuth registration and interactive consent. The chat's connector supplies no token to this application. Metadata uses `gmail.metadata`; plain-text summaries use `gmail.readonly`. Both are restricted scopes. Labels filter app requests, not Google's account-wide permission. No send/modify scope is requested. See [Google scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) and [desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app).

Polling is account-bound, read-only, at most 20 messages per poll with a 15-minute interval, jitter, deduplication and backoff. HTML, remote images and attachments stay inert. Raw plain-text bodies live only in an expiring in-memory cache; selected cloud excerpts require explicit setup consent. Unavailable account setup does not block other features.

Stage an improvement creates a source-only isolated candidate and selects it as the work scope. Give Task mode a specific improvement. Verify proposal runs bounded offline checks; Review shows the exact patch/digest and remaining host checks. Installing self-authored executable code requires native approval of the same tested bytes. Bounded appearance/cadence data reject code, paths, hooks and unknown properties. No owner-established automatic release trust channel is configured; CI green or a self-created key cannot supply that trust.

## Rollback, removal and evidence

```sh
capri quit
capri rollback
capri run
# Or remove V2 launch registration and restore the exact prior V1 registration:
python3 tools/install_v2.py --uninstall
```

Rollback/removal retain private accounts, history, drafts, assets and version/source history. Stop the active service before a manual rollback. Current qualification belongs to the source-bound local review report and [capability notes](docs/CAPABILITIES.md); a build or fixture is not human motion approval. Physical lock/suspend, fractional DPI, hotplug, uninterrupted playback and valid resource samples require their own evidence.

```sh
CAPRI_HOST_INTEGRATION=1 "$CAPRI_DATA_DIR/venv/bin/python" -B -m unittest discover -s tests -v
```
