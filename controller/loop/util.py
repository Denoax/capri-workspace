import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone


class Rejected(ValueError):
    pass


class NeedsInput(Rejected):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return digest(canonical(value))


def redact(text):
    def plain(value):
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
        value = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED_API_KEY]", value)
        return re.sub(r"(?i)((?:api[_-]?key|access_token|refresh_token|secret|password)\s*[=:]\s*)[^\s,;\"}]+", r"\1[REDACTED]", value)
    def scrub(value):
        if isinstance(value, dict):
            return {k: "[REDACTED]" if re.fullmatch(r"api[_-]?key|access_token|refresh_token|secret|password|authorization", k, re.I) else scrub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        return plain(value) if isinstance(value, str) else value
    if text.lstrip().startswith(("{", "[")):
        try:
            return json.dumps(scrub(json.loads(text)), ensure_ascii=False)
        except ValueError:
            pass
    return plain(text)


def safe_path(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(p in ("..", ".") for p in rel.parts):
        raise Rejected("Unsafe relative path")
    candidate = root / rel
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise Rejected("Symlink not permitted")
    if not candidate.resolve().is_relative_to(root):
        raise Rejected("Path escaped its root")
    return candidate


def atomic(path, data, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode()
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if exclusive:
            try:
                os.link(temp, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise Rejected(f"Existing content conflict: {path}")
        else:
            os.replace(temp, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, obj, exclusive=False):
    atomic(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n", exclusive)


def tree(root):
    result = {}
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root)
        if ".git" in rel.parts or "__pycache__" in rel.parts:
            continue
        if p.is_symlink():
            raise Rejected(f"Symlink source unsupported: {rel}")
        if p.is_file():
            if p.stat().st_size > 8_000_000:
                raise Rejected("Source file exceeds bounded snapshot limit")
            result[str(rel)] = {"sha256": digest(p.read_bytes()), "mode": p.stat().st_mode & 0o777}
    return result
