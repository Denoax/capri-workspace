"""Flat-folder moves through held directory FDs, with inode checks and undo.

No general file-reading tool: credential-bearing trees are never implicit inputs.
Linux renameat2(RENAME_NOREPLACE) avoids overwriting a concurrently created file.
"""
import ctypes
import os
from pathlib import Path
import secrets
import stat
import json
from .provider import atomic_private

from .broker import Denied

_libc = ctypes.CDLL(None, use_errno=True)
_libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
_libc.renameat2.restype = ctypes.c_int


def name(value):
    if not isinstance(value, str) or not value or value in (".", "..") or "/" in value or "\x00" in value or value.startswith("."):
        raise Denied("Expected a visible single filename")
    if len(value.encode()) > 240:
        raise Denied("Filename too long")
    return value


def rename_noreplace(srcfd, src, dstfd, dst):
    if _libc.renameat2(srcfd, os.fsencode(src), dstfd, os.fsencode(dst), 1):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


class Folder:
    def __init__(self, root, journal_directory=None):
        path = Path(root)
        if not path.is_absolute() or Path.home().is_relative_to(path) or path in (Path("/tmp"), Path("/var/tmp")) or (len(path.parts) > 1 and path.parts[1] in ("proc", "sys", "dev", "run", "etc", "usr")):
            raise Denied("Select a specific folder, not home or filesystem root")
        # Walk every component without following symlinks, keeping the resulting handle.
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in path.parts[1:]:
                if part in (".", "..") or part.startswith("."):
                    raise Denied("Parent traversal is not allowed")
                new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = new
            self.fd = fd
        except BaseException:
            os.close(fd)
            raise
        self.root = str(path)
        self.plans = {}
        self.undos = {}
        self.journal_directory = Path(journal_directory) if journal_directory else None
        if self.journal_directory:
            self.journal_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.recover()

    def persist(self, plan_id, moves):
        if self.journal_directory:
            atomic_private(self.journal_directory / (plan_id + ".json"),
                {"root": self.root, "directory": [os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino], "moves": moves})

    def recover(self):
        for path in self.journal_directory.glob("*.json"):
            record = json.loads(path.read_text())
            if record.get("root") != self.root or record.get("directory") != [os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino]:
                continue
            completed = []
            for move in record["moves"]:
                move["signature"] = tuple(move["signature"])
                try:
                    target = self.signature(move["to"])
                except (FileNotFoundError, Denied):
                    continue
                if target == move["signature"]:
                    completed.append(move)
            self.undos[path.stem] = completed

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def signature(self, filename):
        info = os.stat(name(filename), dir_fd=self.fd, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Denied("Only ordinary non-hardlinked files may be moved")
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    def stage(self):
        moves = []
        for filename in sorted(os.listdir(self.fd))[:500]:
            if filename.startswith((".", "images--", "documents--")):
                continue
            info = os.stat(filename, dir_fd=self.fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                continue
            suffix = Path(filename).suffix.lower()
            category = "images" if suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif") else "documents" if suffix in (".txt", ".pdf", ".md", ".odt") else None
            if category:
                moves.append({"from": filename, "to": category + "--" + filename,
                              "signature": self.signature(filename)})
        plan_id = secrets.token_hex(12)
        self.plans[plan_id] = moves
        return {"plan_id": plan_id, "root": self.root, "moves": moves,
                "note": "Flat reversible names; no recursive traversal, overwrite or deletion. Use /apply PLAN_ID after reviewing."}

    def apply(self, plan_id):
        if plan_id not in self.plans:
            raise Denied("Unknown staged plan")
        moves = self.plans.pop(plan_id)
        for move in moves:
            if self.signature(move["from"]) != move["signature"]:
                raise Denied("Staged source changed")
            try:
                os.stat(move["to"], dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise Denied("Destination exists")
        completed = []
        self.persist(plan_id, moves)
        # Renames never follow source links. A same-UID adversary replacing entries
        # concurrently remains inside the documented same-session trust boundary.
        try:
            for move in moves:
                if self.signature(move["from"]) != move["signature"]:
                    raise Denied("Source changed during application")
                rename_noreplace(self.fd, move["from"], self.fd, move["to"])
                completed.append(move)
        except BaseException:
            self.undos[plan_id] = completed
            raise
        self.undos[plan_id] = completed
        return {"moved": len(completed), "undo_id": plan_id, "moves": completed}

    def undo(self, plan_id):
        if plan_id not in self.undos:
            raise Denied("Unknown undo ID; undo is available in the original running session")
        moves = self.undos[plan_id]
        count = 0
        while moves:
            move = moves[-1]
            if self.signature(move["to"]) != move["signature"]:
                raise Denied("Moved file changed; refusing unsafe undo")
            rename_noreplace(self.fd, move["to"], self.fd, move["from"])
            moves.pop()
            self.persist(plan_id, moves)
            count += 1
        return {"restored": count}
