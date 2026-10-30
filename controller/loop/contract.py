import json
import hashlib
from pathlib import Path
import subprocess
import re

from .util import Rejected, digest, identity, tree


def git(repo, *args):
    r = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args], capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise Rejected("Git operation failed: " + r.stderr)
    return r.stdout if '-z' in args else r.stdout.strip()


def source(repo):
    repo = Path(repo).resolve()
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise Rejected("Dirty original source; preserve it and resolve before intake")
    if (repo / ".gitmodules").exists() or (repo / ".gitattributes").exists():
        raise Rejected("Submodule/LFS/attribute qualification required before this repository")
    files = tree(repo)
    committed = {}
    for record in git(repo, 'ls-tree', '-r', '-z', '--full-tree', 'HEAD').split('\0'):
        if not record:
            continue
        header, name = record.split('\t', 1)
        mode, kind, object_id = header.split()
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise Rejected('Non-regular Git source needs explicit qualification')
        committed[name] = object_id
    tracked = set(committed)
    extra, missing = set(files) - tracked, tracked - set(files)
    if extra or missing:
        raise Rejected('Original source differs from committed file inventory; preserve and qualify private/ignored extras before intake')
    algorithm = git(repo, 'rev-parse', '--show-object-format')
    if algorithm not in ('sha1', 'sha256'):
        raise Rejected('Unsupported Git object identity')
    for name, record in files.items():
        data = (repo / name).read_bytes()
        object_id = hashlib.new(algorithm, b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if object_id != committed[name] or digest(data) != record['sha256']:
            raise Rejected('Original source bytes differ from the committed inventory')
    for name in files:
        if ".codex" in Path(name).parts or Path(name).name in (".env", ".env.local", ".npmrc", ".git-credentials"):
            raise Rejected("Source contains executable configuration or private inputs needing explicit qualification: " + name)
    return {"repo": str(repo), "head": git(repo, "rev-parse", "HEAD"), "git_tree": git(repo, "rev-parse", "HEAD^{tree}"), "files": files, "source_hash": identity(files)}


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or not set(value) <= set(required) | set(optional):
        raise Rejected("Missing or unknown contract fields")


def relative(name):
    if not isinstance(name, str):
        raise Rejected("Scoped path must be text")
    p = Path(name)
    if not isinstance(name, str) or not name or p.is_absolute() or any(x in ("..", ".git", ".codex", ".agents") for x in p.parts):
        raise Rejected("Invalid scoped source path")
    return name


def record_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
        raise Rejected("Invalid record ID")
    return value


def validate(proposal, repo, request, instruction_files):
    proposal = json.loads(json.dumps(proposal))
    fields(proposal, ("schema_version", "title", "requirements", "allowed_paths", "steps", "checks"))
    if proposal["schema_version"] != 1 or not isinstance(proposal["title"], str):
        raise Rejected("Unsupported task schema")
    for key in ("requirements", "allowed_paths", "steps", "checks"):
        if not isinstance(proposal[key], list) or not 0 < len(proposal[key]) <= 64:
            raise Rejected("Empty or oversized task field: " + key)
    allowed = [relative(p) for p in proposal["allowed_paths"]]
    ids = set()
    for requirement in proposal["requirements"]:
        fields(requirement, ("id", "text", "origin", "check_ids"), ("verification",))
        record_id(requirement["id"])
        if requirement["id"] in ids or not requirement["text"] or not isinstance(requirement["check_ids"], list):
            raise Rejected("Invalid requirement ledger")
        ids.add(requirement["id"])
        requirement.setdefault("verification", "command" if requirement["check_ids"] else "review")
        if requirement["verification"] not in ("command", "review", "human"):
            raise Rejected("Unsupported requirement verification type")
    check_ids = set()
    for check in proposal["checks"]:
        fields(check, ("id", "argv", "required", "expected_exit", "baseline_must_fail", "requirement_ids"))
        record_id(check["id"])
        if check["id"] in check_ids or not isinstance(check["required"], bool) or not isinstance(check["expected_exit"], int) or not isinstance(check["baseline_must_fail"], bool):
            raise Rejected("Invalid check")
        if not isinstance(check["argv"], list) or not check["argv"] or any(not isinstance(v, str) or len(v) > 2048 or "\0" in v for v in check["argv"]):
            raise Rejected("Invalid argv")
        if not set(check["requirement_ids"]) <= ids:
            raise Rejected("Check has unknown requirement")
        check_ids.add(check["id"])
    for requirement in proposal["requirements"]:
        if (requirement["verification"] == "command" and not requirement["check_ids"]) or not set(requirement["check_ids"]) <= check_ids:
            raise Rejected("Requirement lacks known acceptance checks")
    if len(proposal["steps"]) > 3:
        raise Rejected("Decompose task: more than three bounded steps")
    for step in proposal["steps"]:
        fields(step, ("id", "goal", "allowed_paths"))
        record_id(step["id"])
        if not set(step["allowed_paths"]) <= set(allowed) or not step["goal"]:
            raise Rejected("Step expands task scope")
    frozen = {**proposal, "request": request, "source": source(repo), "instructions": instruction_files,
              "limits": {"step_wall_seconds": 240, "max_tool_interactions": 12, "max_prompt_bytes": 60000, "context_occupancy": "UNKNOWN"},
              "non_goals": ["Original source edits", "publication", "human acceptance", "next task", "visual media generation"]}
    frozen["requirements_hash"] = identity(proposal["requirements"])
    frozen["instructions_hash"] = identity(instruction_files)
    if len(json.dumps(frozen).encode()) > 60000:
        raise Rejected("Contract exceeds byte budget; decompose without dropping requirements")
    return frozen
