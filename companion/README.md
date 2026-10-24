# Capri desktop companion

A native Quickshell/Qt Quick character and a separate Python coordinator for a local conversation named **Capri**. This is an additive testing candidate. It does not start the repository's three-role runtime or modify its controller, README, showcase or approved art.

The companion has articulated local animation, a native composer, private SQLite history and editable memory, a deterministic authority broker, and typed native adapters. ChatGPT inference requires Capri's own successful official sign-in. **Offline test mode is not a connected model.**

## Requirements and setup

Target: Arch Linux / Hyprland, Quickshell 0.3.1 and Qt 6.12. The machine must provide Python 3.11+, python-dbus, python-gobject, python-pillow (asset geometry preparation), bubblewrap, systemd user services, gio, playerctl and wpctl. No root daemon, global model change or model download is required. The work runner fails closed without its isolation prerequisites.

From this directory:

```sh
CAPRI_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/capri"
python3 -m venv "$CAPRI_DATA_DIR/venv"
"$CAPRI_DATA_DIR/venv/bin/python" -m pip install -r requirements.lock
python3 tools/import_assets.py /path/to/CAPRI_DESKTOP_COMPANION_V1 "$CAPRI_DATA_DIR/assets"
python3 tools/build_input_regions.py "$CAPRI_DATA_DIR/assets"
python3 launcher.py run --screen OUTPUT_NAME
```

Keep the virtual environment and imported assets outside the Git source tree; the existing controller intentionally rejects symlink-bearing source trees. Run asset preparation with the system Python that provides Pillow. Import accepts only the existing data files pinned in `assets-manifest.json`; it never loads character hooks, scripts, QML or extensions. Character media are intentionally excluded from Git. See [provenance](docs/PROVENANCE.md).

For a user launcher and optional, initially disabled user unit:

```sh
python3 tools/install.py
capri run
capri summon
capri stop
capri hide
capri status
capri quit
```

The launcher supervises both processes. Quit waits for the old service lock before returning. There is one core/socket owner; starting a duplicate fails. The graphical session must supply a current Wayland environment. Autostart is **off**. The generated `capri-companion.service` is optional; `--autostart` is a deliberate installer opt-in. Graphical-session restart/autostart is not qualified merely by generating a unit.

## Using the companion

Click **Talk** or the actor to open the composer; drag the actor to place it. Right-click the actor or click **Stop** to revoke current authority. The size slider and **Quiet** control adjust local presentation. Hidden/locked actors stop their animation clock. A disconnected or unqualified session cannot execute commands. Local idle never requests a cloud turn.

**Chat** treats input, including pasted command-shaped text, as conversation data. Select **Commands** deliberately for typed computer actions. Settings/help buttons invoke narrow trusted operations. A model reply never becomes a command or permission.

Useful commands in Commands mode:

```text
/apps
/open audio-settings
/windows
/focus 0xWINDOW_ADDRESS
/players
/player spotify
/media-status
/media pause
/media play
/volume 40
/folder /absolute/selected/folder
/organize
/apply PLAN_ID
/undo PLAN_ID
/work /absolute/project -- /usr/bin/python3 -B -m unittest -v
/remember Preferred project name is Silver
/memories
/forget MEMORY_ID
/export
/reset CONFIRM
```

Only reviewed desktop IDs can launch; `/apps` reports actual installation. Media controls require an explicitly selected current MPRIS player. Volume is an integer from 0 to 100. File organization stages flat `documents--` / `images--` name changes, requires explicit apply, never overwrites, and keeps a private undo manifest. It does not recursively reorganize or delete documents. Undo checks recorded identity and remains available after restart when the same folder is selected.

Work jobs receive the selected project read-only at `/work`, isolated PID/network/mount namespaces, no home or desktop sockets, clean environment, a private `/tmp`, 512 MiB memory, 32 tasks, a CPU quota, 30-second runtime and 1 MiB output limit. A pidfd supervisor ends the job if its exact core dies, including a hard crash. Commands are exact argv, not shell interpolation. Builds that require project writes or network are unsupported in this version. Selecting a project makes its contents visible to its test code; do not select a root containing secrets that the job should not read.

## ChatGPT and privacy

Use **Settings → Continue with ChatGPT**. Capri uses its own dynamic registration, PKCE/state/nonce, validated ID token, protected account record, serialized refresh, account model discovery and the public streamed Responses API with `store:false`. The browser callback is temporary and bound only to `127.0.0.1`. Existing Codex credentials, browser cookies and private ChatGPT endpoints are never used. No paid fallback exists.

ChatGPT account eligibility and completed inference must be verified separately. An identity callback, a model list and a completed turn are distinct outcomes. The native UI displays only discovered models. Saved account models are refreshed without blocking native startup, and an unavailable selected model requires an explicit new choice. The default brain is conversational; native task authority uses the explicit command grammar, not model planning or autonomous function execution.

State is under the app's XDG config/state/runtime directories with owner-only permissions. Provider/account partitions do not automatically share history. Model selection is saved per account. Memory is preference data and cannot grant authority. Context is bounded by character counts; exact token occupancy and account pricing are not claimed. Exports are deliberate private files. Recognizable token/authorization URL shapes are redacted; redaction cannot identify every possible secret a user might type.

## Removal and rollback

Stop the running companion, then remove only unchanged installer-owned files:

```sh
capri quit
python3 tools/install.py --uninstall
```

Uninstall preserves conversation, credentials, exports, assets, source and unrelated files. Changed installation files are preserved for inspection. It does not delete personal data. To roll back, stop this candidate and keep using the original repository/runtime; `main` was not changed. No source checkout or user history needs resetting.

## Checks and review limits

```sh
CAPRI_HOST_INTEGRATION=1 "$CAPRI_DATA_DIR/venv/bin/python" -B -m unittest discover -s tests -v
```

Host tests exercise actual isolation denials; provider fixtures remain distinct from account outcomes. See [security](docs/SECURITY.md) for boundaries and [capabilities](docs/CAPABILITIES.md) for qualified versus pending features. Real screen/GUI automation, voice, networked/writable jobs and autonomous model tool planning are disabled or unsupported. This candidate needs human artistic review and does not imply integration or release approval.
