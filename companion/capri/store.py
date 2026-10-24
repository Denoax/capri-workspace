"""Private local transcript and durable, non-replaying action journal."""
import json
import os
from pathlib import Path
import sqlite3
import time
from .redact import redact


class Store:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_uid != os.getuid():
            raise ValueError("State directory must be owned and not a symlink")
        directory.chmod(0o700)
        self.db = sqlite3.connect(directory / "capri.sqlite")
        (directory / "capri.sqlite").chmod(0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS turns(id INTEGER PRIMARY KEY, partition TEXT, role TEXT,
             text TEXT, status TEXT, created REAL);
          CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, partition TEXT,
             text TEXT, source_turn INTEGER, created REAL);
          CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY, epoch TEXT, kind TEXT,
             status TEXT, detail TEXT, created REAL);
        """)
        # A crash never replays an action whose effect may have happened.
        self.db.execute("UPDATE actions SET status='EFFECT_UNKNOWN' WHERE status IN ('RUNNING','VERIFYING')")
        self.db.execute("UPDATE actions SET status='CANCELLED' WHERE status='AUTHORIZED'")
        self.db.commit()

    def turn(self, partition, role, text, status="completed"):
        with self.db:
            cursor = self.db.execute("INSERT INTO turns VALUES(NULL,?,?,?,?,?)",
                                     (partition, role, redact(text)[:64000], status, time.time()))
        return cursor.lastrowid

    def history(self, partition, limit=60):
        rows = self.db.execute("SELECT id,role,text,status FROM turns WHERE partition=? ORDER BY id DESC LIMIT ?",
                               (partition, limit)).fetchall()
        return [dict(zip(("id", "role", "text", "status"), row)) for row in reversed(rows)]

    def remember(self, partition, text, source):
        with self.db:
            self.db.execute("INSERT INTO memories VALUES(NULL,?,?,?,?)", (partition, redact(text)[:2000], source, time.time()))

    def memories(self, partition):
        return [dict(zip(("id", "text", "source_turn"), r)) for r in self.db.execute(
            "SELECT id,text,source_turn FROM memories WHERE partition=? ORDER BY id DESC LIMIT 40", (partition,))]

    def forget(self, partition, memory_id):
        with self.db:
            self.db.execute("DELETE FROM memories WHERE partition=? AND id=?", (partition, memory_id))

    def reset(self, partition):
        with self.db:
            self.db.execute("DELETE FROM turns WHERE partition=?", (partition,))
            self.db.execute("DELETE FROM memories WHERE partition=?", (partition,))

    def journal(self, action_id, epoch, kind, status, detail=""):
        with self.db:
            self.db.execute("INSERT INTO actions VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,detail=excluded.detail",
                            (action_id, epoch, kind, status, detail[:2000], time.time()))

    def action(self, action_id):
        return self.db.execute("SELECT status,detail FROM actions WHERE id=?", (action_id,)).fetchone()

    def export(self, partition):
        return json.dumps({"conversation": "Capri", "partition": partition,
                           "turns": self.history(partition, 10000), "memories": self.memories(partition)}, indent=2)
