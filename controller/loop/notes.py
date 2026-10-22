import json
from pathlib import Path

from .util import Rejected, atomic, digest, redact, safe_path, write_json


class Notes:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)
        if self.root.is_symlink():
            raise Rejected("Notes root is a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        if (self.root / ".obsidian").exists():
            raise Rejected("Use an ordinary notes folder, not a conflicting vault configuration")

    def managed(self, relative, data):
        path = safe_path(self.root, relative)
        encoded = data.encode() if isinstance(data, str) else data
        key = str(path)
        previous = self.store.db.execute("SELECT sha256 FROM managed_notes WHERE path=?", (key,)).fetchone()
        if path.exists():
            actual = digest(path.read_bytes())
            if (previous and previous["sha256"] != actual) or (not previous and actual != digest(encoded)):
                raise Rejected("User-edited/unowned generated note preserved: " + key)
        atomic(path, encoded)
        self.store.db.execute("INSERT INTO managed_notes(path,sha256) VALUES(?,?) ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256", (key, digest(encoded)))

    def replay(self):
        with self.store.lock("notes"):
            rows = self.store.db.execute("SELECT * FROM outbox WHERE kind='NOTE' AND status='PENDING' ORDER BY rowid").fetchall()
            for row in rows:
                payload = json.loads(row["payload"])
                data = "# " + payload["kind"] + "\n\n```json\n" + redact(json.dumps(payload, indent=2)) + "\n```\n"
                rel = f"System/Events/{payload['seq']:08d}.md"
                path = safe_path(self.root, rel)
                atomic(path, data, exclusive=True)
                with self.store.transaction():
                    self.store.db.execute("UPDATE outbox SET status='DELIVERED',receipt=? WHERE id=?", (json.dumps({"path": str(path), "sha256": digest(path.read_bytes())}), row["id"]))
            self.index()
        return len(rows)

    def attach(self, source, origin):
        source = Path(source)
        if source.is_symlink() or not source.is_file():
            raise Rejected("Invalid evidence attachment")
        data = source.read_bytes()
        # Text is redacted before attachment; binary packages must already be sanitized.
        if source.suffix in (".json", ".jsonl", ".txt", ".md", ".patch", ".py", ".toml"):
            data = redact(data.decode(errors="strict")).encode()
        sha = digest(data)
        name = sha + source.suffix
        path = safe_path(self.root, "Attachments/" + name)
        atomic(path, data, exclusive=True)
        self.store.db.execute("INSERT OR IGNORE INTO objects(sha256,path,size,origin) VALUES(?,?,?,?)", (sha, str(path), len(data), origin))
        return {"sha256": sha, "path": str(path), "bytes": len(data)}

    def index(self):
        tasks = self.store.db.execute("SELECT id,state,review,outcome FROM tasks ORDER BY rowid").fetchall()
        sessions = self.store.db.execute("SELECT id,role,owner FROM sessions ORDER BY rowid").fetchall()
        lines = ["# Codex workflow V3", "", "Ordinary Markdown folder in Mani Work Chronicle. SQLite is authoritative.", "", "[Setup and operation](System/SETUP.md)", "", "## Cycles", ""]
        for t in tasks:
            lines.append(f"- [{t['id']}](Cycles/{t['id']}/CONTRACT.md): {t['state']} / {t['outcome'] or 'pending'}")
        lines += ["", "## Actual sessions", ""]
        for s in sessions:
            lines.append(f"- {s['role']}: `{s['id']}` (owner `{s['owner']}`)")
        lines += ["", "[Observable event index](System/EVENTS.md)", "", "Private model reasoning and undocumented provider events are outside capture. Native TUI/IDE capture is unqualified.", ""]
        self.managed("00_HOME.md", "\n".join(lines))
        events = self.store.db.execute("SELECT seq,kind FROM events ORDER BY seq").fetchall()
        self.managed("System/EVENTS.md", "# Events\n\n" + "\n".join(f"- [{r['seq']}: {r['kind']}](Events/{r['seq']:08d}.md)" for r in events) + "\n")

    def reconcile(self):
        pending = self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='NOTE' AND status!='DELIVERED'").fetchone()[0]
        errors = []
        for row in self.store.db.execute("SELECT receipt FROM outbox WHERE kind='NOTE' AND status='DELIVERED'"):
            receipt = json.loads(row[0])
            p = Path(receipt["path"])
            if not p.is_file() or digest(p.read_bytes()) != receipt["sha256"]:
                errors.append(str(p))
        for row in self.store.db.execute("SELECT * FROM objects"):
            p = Path(row["path"])
            if not p.is_file() or digest(p.read_bytes()) != row["sha256"]:
                errors.append(str(p))
        if pending or errors:
            raise Rejected("Projection incomplete/conflicting: " + json.dumps({"pending": pending, "errors": errors}))
        return {"pending": 0, "events": self.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], "attachments": self.store.db.execute("SELECT COUNT(*) FROM objects").fetchone()[0]}
