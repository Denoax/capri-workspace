"""Fixed native adapters; arbitrary code is admitted only to the confined runner."""
import asyncio
import json
import os
from pathlib import Path
import re
import signal
import time

from .broker import Denied, exact_keys
from .files import Folder

# Code-owned allowlist. Desktop entries are trusted installed software, never model paths.
APPLICATIONS = {
    "audio-settings": ("/usr/share/applications/org.pulseaudio.pavucontrol.desktop", ("org.pulseaudio.pavucontrol", "pavucontrol")),
    "code": ("/usr/share/applications/com.microsoft.VSCode.desktop", ("code",)),
    "firefox": ("/usr/share/applications/firefox.desktop", ("firefox", "org.mozilla.firefox")),
    "thunar": ("/usr/share/applications/thunar.desktop", ("thunar",)),
    "calculator": ("/usr/share/applications/org.gnome.Calculator.desktop", ("org.gnome.Calculator",)),
}
MEDIA_COMMANDS = {"play", "pause", "play-pause", "next", "previous", "stop"}


class Adapters:
    def __init__(self):
        self.children = set()
        self.folder = None
        self.player = None
        self.sandbox_ready = False

    def stop(self):
        for proc in tuple(self.children):
            if proc.returncode is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    async def command(self, argv, timeout=12, env=None):
        proc = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE,
                   stderr=asyncio.subprocess.STDOUT, env=env, close_fds=True, start_new_session=True,
                   limit=1024 * 1024)
        self.children.add(proc)
        output = bytearray()
        try:
            async with asyncio.timeout(timeout):
                while chunk := await proc.stdout.read(8192):
                    output.extend(chunk)
                    if len(output) > 1024 * 1024:
                        raise Denied("Output exceeded 1 MiB; operation stopped")
                await proc.wait()
            text = output.decode(errors="replace")
            if proc.returncode:
                raise Denied(f"Native command failed ({proc.returncode}): {text[:600]}")
            return text.strip()
        finally:
            if proc.returncode is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await proc.wait()
            self.children.discard(proc)

    def validate(self, kind, args):
        schemas = {"desktop.open": ("app",), "desktop.focus": ("address",),
                   "media.control": ("command",), "media.status": (), "audio.adjust": ("percent",),
                   "files.stage": (), "files.apply": ("plan_id",), "files.undo": ("plan_id",),
                   "work.run": ("root", "argv")}
        if not isinstance(kind, str) or kind not in schemas:
            raise Denied("Unsupported action family")
        exact_keys(args, schemas[kind])
        if kind == "desktop.open" and args["app"] not in APPLICATIONS:
            raise Denied("Application is not in the reviewed native allowlist")
        if kind == "desktop.focus" and not re.fullmatch(r"0x[0-9a-f]{1,16}", str(args["address"])):
            raise Denied("Invalid window address")
        if kind == "media.control" and args["command"] not in MEDIA_COMMANDS:
            raise Denied("Invalid media operation")
        if kind.startswith("media.") and not self.player:
            raise Denied("Select an available MPRIS player first with /player NAME")
        if kind == "audio.adjust" and (type(args["percent"]) is not int or not 0 <= args["percent"] <= 100):
            raise Denied("Volume must be an integer from 0 to 100")
        if kind.startswith("files.") and not self.folder:
            raise Denied("Select a folder explicitly with /folder ABSOLUTE_PATH")
        if kind in ("files.apply", "files.undo") and not re.fullmatch("[0-9a-f]{24}", str(args["plan_id"])):
            raise Denied("Invalid plan ID")
        if kind == "work.run":
            if not self.sandbox_ready:
                raise Denied("Confined runner has not passed host qualification")
            argv = args["argv"]
            if not isinstance(argv, list) or not 1 <= len(argv) <= 40 or not all(isinstance(a, str) and len(a) < 4096 and '\0' not in a for a in argv):
                raise Denied("Expected bounded exact argv")
            if not argv[0].startswith("/usr/bin/") or Path(argv[0]).name != argv[0][9:]:
                raise Denied("Use an exact executable in /usr/bin")
            folder = Folder(args["root"])
            folder.close()

    def sandbox_argv(self, root, argv):
        return ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/tmp",
                "--setenv", "LANG", "C.UTF-8", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
                "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib", "/lib64",
                "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--ro-bind", root, "/work", "--chdir", "/work", "--", *argv]

    async def qualify_sandbox(self):
        code = "import os,socket; assert not os.path.exists('/home'); assert not os.path.exists('/run/user'); s=socket.socket();\ntry:s.connect(('1.1.1.1',443))\nexcept OSError:pass\nelse:raise AssertionError('network escaped')\nprint('isolation-denials-pass')"
        try:
            import tempfile
            with tempfile.TemporaryDirectory(prefix="capri-isolation-") as probe:
                result = await self.command(self.sandbox_argv(probe, ["/usr/bin/python3", "-c", code]))
            self.sandbox_ready = result == "isolation-denials-pass"
            return result
        except (OSError, Denied) as error:
            self.sandbox_ready = False
            return "BLOCKED: " + str(error)

    async def players(self):
        try:
            return (await self.command(["/usr/bin/playerctl", "--list-all"])).splitlines()
        except (FileNotFoundError, Denied):
            return []

    async def clients(self):
        rows = json.loads(await self.command(["/usr/bin/hyprctl", "-j", "clients"]))
        return [{"address": row["address"], "class": row["class"], "pid": row["pid"]} for row in rows]

    async def run(self, kind, args):
        self.validate(kind, args)
        if kind == "desktop.open":
            path, classes = APPLICATIONS[args["app"]]
            if not Path(path).is_file():
                raise Denied("Approved application is not installed")
            # Desktop applications may retain inherited stdout after gio exits.
            # Await the launcher process, never EOF on the application's pipes.
            proc = await asyncio.create_subprocess_exec("/usr/bin/gio", "launch", path,
                     stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                     close_fds=True, start_new_session=True)
            self.children.add(proc)
            try:
                async with asyncio.timeout(10):
                    code = await proc.wait()
                if code:
                    raise Denied(f"Desktop launcher failed ({code})")
            finally:
                if proc.returncode is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    await proc.wait()
                self.children.discard(proc)
            async with asyncio.timeout(10):
                while True:
                    found = [row for row in await self.clients() if row["class"].lower() in [c.lower() for c in classes]]
                    if found:
                        return {"opened": args["app"], "windows": found}
                    await asyncio.sleep(0.2)
        if kind == "desktop.focus":
            if not any(r["address"] == args["address"] for r in await self.clients()):
                raise Denied("Target window no longer exists")
            await self.command(["/usr/bin/hyprctl", "dispatch", "focuswindow", "address:" + args["address"]])
            row = json.loads(await self.command(["/usr/bin/hyprctl", "-j", "activewindow"]))
            if row.get("address") != args["address"]:
                raise Denied("Focus verification failed")
            return {"focused": args["address"]}
        if kind.startswith("media."):
            if self.player not in await self.players():
                raise Denied("Selected player disappeared")
            if kind == "media.control":
                await self.command(["/usr/bin/playerctl", "--player", self.player, args["command"]])
            status = await self.command(["/usr/bin/playerctl", "--player", self.player, "status"])
            desired = {"pause": "Paused", "play": "Playing", "stop": "Stopped"}.get(args.get("command"))
            deadline = time.monotonic() + 3
            while desired and status != desired:
                if time.monotonic() >= deadline:
                    raise Denied("Player did not reach requested state within 3 seconds")
                await asyncio.sleep(0.1)
                status = await self.command(["/usr/bin/playerctl", "--player", self.player, "status"])
            return {"player": self.player, "status": status}
        if kind == "audio.adjust":
            await self.command(["/usr/bin/wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", str(args["percent"] / 100)])
            result = await self.command(["/usr/bin/wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
            match = re.search(r"Volume: ([0-9.]+)", result)
            if not match or abs(float(match[1]) - args["percent"] / 100) > 0.015:
                raise Denied("Audio verification failed")
            return {"percent": args["percent"], "verified": result}
        if kind == "files.stage":
            return self.folder.stage()
        if kind == "files.apply":
            return self.folder.apply(args["plan_id"])
        if kind == "files.undo":
            return self.folder.undo(args["plan_id"])
        if kind == "work.run":
            import secrets
            unit = "capri-job-" + secrets.token_hex(8)
            command = ["/usr/bin/systemd-run", "--user", "--quiet", "--wait", "--pipe", "--collect",
                       "--unit=" + unit, "-p", "MemoryMax=512M", "-p", "TasksMax=32",
                       "-p", "CPUQuota=100%", "-p", "RuntimeMaxSec=30s", *self.sandbox_argv(args["root"], args["argv"])]
            finished = False
            try:
                text = await self.command(command, timeout=35)
                finished = True
            finally:
                if not finished:
                    cleanup = await asyncio.create_subprocess_exec("/usr/bin/systemctl", "--user", "stop", unit + ".service",
                              stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                    code = await cleanup.wait()
                    if code not in (0, 5):
                        raise Denied("Job unit cleanup failed; inspect the private runtime journal")
            return {"exit_code": 0, "output": text[:20000], "network": "isolated", "project": "read-only"}
        raise Denied("No adapter")
