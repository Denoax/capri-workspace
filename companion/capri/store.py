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

    def migrate_v2(self):
        """Additive schema: V1 transcript, credentials and correction rows stay intact."""
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS app_state(partition TEXT, key TEXT, value TEXT,
             PRIMARY KEY(partition,key));
          CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, partition TEXT, objective TEXT,
             status TEXT, lease TEXT, thread TEXT, checkpoint TEXT, created REAL, updated REAL);
          CREATE TABLE IF NOT EXISTS task_events(id INTEGER PRIMARY KEY, task TEXT,
             kind TEXT, detail TEXT, created REAL);
          CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, source TEXT, topic TEXT,
             kind TEXT, payload TEXT, created REAL, status TEXT);
          CREATE TABLE IF NOT EXISTS directives(id TEXT PRIMARY KEY, partition TEXT,
             revision INTEGER, value TEXT, enabled INTEGER);
          CREATE TABLE IF NOT EXISTS notices(id TEXT PRIMARY KEY, topic TEXT, kind TEXT,
             text TEXT, why TEXT, status TEXT, created REAL);
          CREATE TABLE IF NOT EXISTS counters(bucket TEXT PRIMARY KEY, value INTEGER);
        """)
        self.db.execute("UPDATE tasks SET status='interrupted' WHERE status IN ('running','queued')")
        self.db.execute("PRAGMA user_version=2")
        self.db.commit()

    def value(self, partition, key, default=None):
        row = self.db.execute("SELECT value FROM app_state WHERE partition=? AND key=?", (partition,key)).fetchone()
        return json.loads(row[0]) if row else default

    def set_value(self, partition, key, value):
        encoded = json.dumps(value, ensure_ascii=True)
        if len(encoded) > 128000:
            raise ValueError("App state value exceeds 128 KiB")
        with self.db:
            self.db.execute("INSERT INTO app_state VALUES(?,?,?) ON CONFLICT(partition,key) DO UPDATE SET value=excluded.value", (partition,key,encoded))

    def draft(self, partition):
        return self.value(partition, "draft", "")

    def save_draft(self, partition, text):
        if not isinstance(text,str) or len(text)>16000:
            raise ValueError("Draft exceeds 16 KiB")
        # A private draft is never an implicit model request or authority event.
        self.set_value(partition,"draft",text)

    def create_task(self, task, partition, objective, lease):
        now=time.time()
        with self.db:
            self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)", (task,partition,redact(objective),"queued",json.dumps(lease),"", "{}",now,now))

    def task_event(self, task, kind, detail):
        with self.db:
            self.db.execute("INSERT INTO task_events VALUES(NULL,?,?,?,?)",(task,kind,redact(detail)[:16000],time.time()))

    def update_task(self, task, **fields):
        if not fields or not set(fields)<= {"status","thread","checkpoint"}:
            raise ValueError("Unknown task state")
        with self.db:
            for key,value in fields.items():
                self.db.execute("UPDATE tasks SET "+key+"=?,updated=? WHERE id=?",(value,time.time(),task))

    def tasks(self, partition, limit=20):
        rows=self.db.execute("SELECT id,objective,status,thread,checkpoint,updated FROM tasks WHERE partition=? ORDER BY created DESC LIMIT ?",(partition,limit)).fetchall()
        return [dict(zip(("id","objective","status","thread","checkpoint","updated"),r)) for r in rows]
