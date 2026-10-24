"""Small exact owner command grammar. No model or retrieved-content classifier grants power."""
import re
import shlex
from .broker import Denied

HELP = """Capri's own local conversation. Native actions come from explicit owner commands:
/apps • /open audio-settings|code|firefox|thunar|calculator • /windows • /focus 0xADDRESS
/players • /player NAME • /media play|pause|play-pause|next|previous|stop
/volume 40 • /folder /absolute/path • /organize • /apply PLAN_ID • /undo PLAN_ID
/work /absolute/project -- /usr/bin/python3 -m unittest
/remember correction • /memories • /forget ID • /export • /reset CONFIRM
/signin • /models • /model ID • /logout • /stop
Ordinary chat needs a connected provider. Offline test mode is explicitly labeled.
File organization stages flat name changes for review. Work jobs are read-only, 30s, no network.
"""


def parse(text):
    normalized = text.strip()
    quick = {"pause my music": ("media.control", {"command": "pause"}),
             "play my music": ("media.control", {"command": "play"})}
    phrase = normalized.lower().removeprefix("capri, ").rstrip(".!?")
    if phrase in quick:
        return quick[phrase]
    match = re.fullmatch(r"(?:open |/open )(audio-settings|code|firefox|thunar|calculator)", phrase)
    if match:
        return "desktop.open", {"app": match[1]}
    if normalized.startswith("/volume "):
        value = normalized[8:]
        if not re.fullmatch(r"\d{1,3}", value):
            raise Denied("Use /volume INTEGER from 0 to 100")
        return "audio.adjust", {"percent": int(value)}
    for prefix, kind, key in (("/media ", "media.control", "command"), ("/focus ", "desktop.focus", "address"),
                              ("/apply ", "files.apply", "plan_id"), ("/undo ", "files.undo", "plan_id")):
        if normalized.startswith(prefix):
            return kind, {key: normalized[len(prefix):]}
    if normalized == "/media-status":
        return "media.status", {}
    if normalized == "/organize":
        return "files.stage", {}
    if normalized.startswith("/work "):
        tokens = shlex.split(normalized[6:])
        if len(tokens) < 3 or tokens[1] != "--":
            raise Denied("Use /work /absolute/root -- /usr/bin/EXEC exact arguments")
        return "work.run", {"root": tokens[0], "argv": tokens[2:]}
    return None
