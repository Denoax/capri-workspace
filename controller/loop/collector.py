import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

from .util import Rejected, atomic, digest, identity, now, redact, safe_path, tree, write_json


def check_command(repo, argv, directory, timeout=60):
    """No auth, controller, original checkout, sockets, or network in a test process."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    before = tree(repo)
    cmd = ["/usr/bin/bwrap", "--die-with-parent", "--new-session", "--unshare-all", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
           "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib", "/lib64", "--ro-bind", "/etc", "/etc", "--proc", "/proc", "--dev", "/dev",
           "--tmpfs", "/tmp", "--bind", str(Path(repo).resolve()), "/workspace", "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
           "--setenv", "HOME", "/tmp", "--setenv", "PYTHONDONTWRITEBYTECODE", "1", "--chdir", "/workspace", *argv]
    started = now()
    clock = time.monotonic()
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    timed_out = False
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        from .adapter import terminate
        timed_out = True
        terminate(process)
        out, err = process.communicate()
    out, err = redact(out.decode(errors="replace")), redact(err.decode(errors="replace"))
    atomic(directory / "stdout.txt", out)
    atomic(directory / "stderr.txt", err)
    after = tree(repo)
    result = {"argv": argv, "confinement_argv": cmd, "cwd": "/workspace", "host_checkout": str(repo), "start": started, "end": now(),
              "duration_seconds": time.monotonic() - clock, "exit": process.returncode, "timeout": timed_out,
              "source_before": identity(before), "source_after": identity(after), "source_unchanged": before == after,
              "stdout_sha256": digest(out.encode()), "stderr_sha256": digest(err.encode()),
              "skip_detected": bool(re.search(r"(?:skipped[= :]+[1-9]|[1-9]\d* skipped|\bSKIP(?:PED)?\b)", out + err, re.I)), "origin": "TRUSTED_RUNNER", "directory": str(directory)}
    write_json(directory / "command.json", result)
    return result


def assess_check(spec, baseline, candidate):
    if not baseline or not candidate or candidate["timeout"] or not candidate["source_unchanged"] or candidate["skip_detected"]:
        return "UNVERIFIED"
    if candidate["exit"] != spec["expected_exit"]:
        return "FAIL"
    if spec["baseline_must_fail"] and (baseline["exit"] == spec["expected_exit"] or baseline["timeout"] or not baseline["source_unchanged"]):
        return "UNVERIFIED"
    return "PASS"


def seal_zip(destination, roots, metadata):
    """Explicit roots only; reject symlinks and never include runtime/auth/state."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    objects = {}
    for prefix, root in roots.items():
        for p in sorted(Path(root).rglob("*")):
            rel = p.relative_to(root)
            if ".git" in rel.parts or "__pycache__" in rel.parts:
                continue
            if p.is_symlink():
                raise Rejected("Symlink in review evidence")
            if p.is_file():
                name = str(Path(prefix) / rel)
                if any(v in rel.parts for v in ("auth.json", "workflow.sqlite3", "intake.sock")):
                    raise Rejected("Private state in archive")
                data = p.read_bytes()
                objects[name] = data
    manifest = {"schema_version": 1, "metadata": metadata, "files": {p: {"sha256": digest(b), "bytes": len(b)} for p, b in objects.items()}}
    objects["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    fd, temp = tempfile.mkstemp(dir=destination.parent, prefix=".zip-pending-")
    os.close(fd)
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(objects.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 10, 20, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100600 << 16
                z.writestr(info, data)
        verify_zip(temp)
        with open(temp, "rb") as f:
            os.fsync(f.fileno())
        os.link(temp, destination)
    finally:
        os.unlink(temp)
    return {"path": str(destination), "sha256": digest(destination.read_bytes()), "bytes": destination.stat().st_size, "manifest": manifest}


def verify_zip(path, expected=None, extract=None):
    path = Path(path)
    if expected and digest(path.read_bytes()) != expected:
        raise Rejected("ZIP hash mismatch")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or len(names) > 10000:
            raise Rejected("Duplicate or oversized archive inventory")
        for item in z.infolist():
            safe_path(Path(extract or "/tmp/zip-validation"), item.filename)
            if item.external_attr >> 16 & 0o170000 == 0o120000 or item.file_size > 64_000_000:
                raise Rejected("Unsafe archive member")
        manifest = json.loads(z.read("MANIFEST.json"))
        if set(names) != set(manifest["files"]) | {"MANIFEST.json"}:
            raise Rejected("Archive allowlist mismatch")
        for name, spec in manifest["files"].items():
            data = z.read(name)
            if len(data) != spec["bytes"] or digest(data) != spec["sha256"]:
                raise Rejected("Archive member identity mismatch")
            if extract:
                atomic(safe_path(extract, name), data, exclusive=True)
        if extract:
            atomic(safe_path(extract, "MANIFEST.json"), z.read("MANIFEST.json"), exclusive=True)
    return manifest
