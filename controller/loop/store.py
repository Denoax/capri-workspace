import contextlib
import fcntl
import json
from pathlib import Path
import sqlite3
import uuid

from .util import NeedsInput, Rejected, canonical, identity, now


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
 id TEXT PRIMARY KEY, logical_key TEXT UNIQUE NOT NULL, content_hash TEXT NOT NULL,
 revision INTEGER NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
 generation INTEGER NOT NULL DEFAULT 1, owner TEXT NOT NULL, packet TEXT NOT NULL,
 candidate TEXT, seal TEXT, review TEXT, outcome TEXT, decision TEXT);
CREATE TABLE IF NOT EXISTS events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, kind TEXT NOT NULL,
 time TEXT NOT NULL, data TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS immutable_event_update BEFORE UPDATE ON events
 BEGIN SELECT RAISE(ABORT,'Append-only events'); END;
CREATE TRIGGER IF NOT EXISTS immutable_event_delete BEFORE DELETE ON events
 BEGIN SELECT RAISE(ABORT,'Append-only events'); END;
CREATE TABLE IF NOT EXISTS outbox(
 id TEXT PRIMARY KEY, task TEXT, kind TEXT NOT NULL, logical_key TEXT UNIQUE NOT NULL,
 payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', receipt TEXT);
CREATE TABLE IF NOT EXISTS attempts(
 id TEXT PRIMARY KEY, task TEXT REFERENCES tasks(id), generation INTEGER NOT NULL,
 role TEXT NOT NULL, status TEXT NOT NULL, pid INTEGER, start_identity TEXT,
 thread TEXT, output TEXT NOT NULL, result TEXT);
CREATE TABLE IF NOT EXISTS sessions(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, role TEXT NOT NULL, runtime TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS objects(
 sha256 TEXT PRIMARY KEY, path TEXT NOT NULL, size INTEGER NOT NULL, origin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(
 id TEXT PRIMARY KEY, task TEXT NOT NULL REFERENCES tasks(id), time TEXT NOT NULL,
 action TEXT NOT NULL, binding TEXT NOT NULL, origin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS capabilities(
 token_hash TEXT PRIMARY KEY, owner TEXT NOT NULL, scope TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS human_inputs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, time TEXT NOT NULL,
 text TEXT NOT NULL, origin TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING');
CREATE TABLE IF NOT EXISTS managed_notes(
 path TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
"""


class Store:
    def __init__(self, home):
        self.home = Path(home)
        self.state = self.home / "state"
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.state / "workflow.sqlite3", timeout=15, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 2:
            self.db.close()
            raise Rejected("Unsupported newer database migration; never downgrade state")
        self.db.executescript(SCHEMA)
        self._migrate(version)

    def _migrate(self, version):
        # DDL and conservative event import share one rollback boundary.
        with self.transaction():
            self.db.execute("CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY, owner TEXT NOT NULL, scope_key TEXT NOT NULL, task TEXT REFERENCES tasks(id), revision INTEGER NOT NULL, packet_hash TEXT, text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', answer_id TEXT, requires_recontract INTEGER NOT NULL DEFAULT 0, event INTEGER UNIQUE NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS question_answers(id TEXT PRIMARY KEY, question TEXT NOT NULL REFERENCES questions(id), text TEXT NOT NULL, origin TEXT NOT NULL, source_ref TEXT NOT NULL, binding TEXT NOT NULL, event INTEGER UNIQUE NOT NULL)")
            columns = {r['name'] for r in self.db.execute("PRAGMA table_info(decisions)")}
            for column in ('operation_id', 'result', 'request_hash'):
                if column not in columns:
                    self.db.execute('ALTER TABLE decisions ADD COLUMN ' + column + ' TEXT')
            self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS decision_operation ON decisions(operation_id)")
            if version < 2:
                for row in self.db.execute("SELECT seq,task,data FROM events WHERE kind='QUESTION'").fetchall():
                    data = json.loads(row['data'])
                    owner = data.get('owner')
                    if not isinstance(owner, str) or not owner:
                        raise Rejected('Legacy question has no owner; migration requires explicit recovery')
                    task = self.db.execute("SELECT * FROM tasks WHERE owner=? ORDER BY rowid DESC LIMIT 1", (owner,)).fetchone()
                    scope = self.db.execute("SELECT scope FROM capabilities WHERE owner=? ORDER BY rowid DESC LIMIT 1", (owner,)).fetchone()
                    scope = json.loads(scope['scope']) if scope else {}
                    key = task['logical_key'] if task else scope.get('key', 'legacy:' + owner)
                    revision = task['revision'] if task else int(scope.get('request', {}).get('lineage', {}).get('revision', 1))
                    self.db.execute("INSERT OR IGNORE INTO questions(id,owner,scope_key,task,revision,packet_hash,text,event) VALUES(?,?,?,?,?,?,?,?)", ('legacy:' + str(row['seq']), owner, key, task['id'] if task else None, revision, task['content_hash'] if task else None, data.get('question', 'Legacy unanswered question; inspect original event'), row['seq']))
                self.db.execute("PRAGMA user_version=2")
            self._hold_ready_in_transaction()

    def questions(self, owner, blocking=False):
        sql = "SELECT * FROM questions WHERE owner=?"
        if blocking:
            sql += " AND (status='PENDING' OR requires_recontract=1)"
        return [dict(r) for r in self.db.execute(sql + " ORDER BY event", (owner,))]

    def _hold_ready_in_transaction(self, tid=None):
        """Question, hold, state event and NOTE intent share one commit."""
        if not self.db.in_transaction:
            raise Rejected('Hold requires an active transaction')
        sql = "SELECT id,owner,version FROM tasks WHERE state='READY'"
        rows = self.db.execute(sql + (' AND id=?' if tid else ''), (tid,) if tid else ()).fetchall()
        for row in rows:
            pending = self.db.execute("SELECT id FROM human_inputs WHERE owner=? AND status='PENDING' LIMIT 1", (row['owner'],)).fetchone()
            if pending or self.questions(row['owner'], blocking=True):
                self.transition_in_transaction(row['id'], 'READY', 'NEEDS_INPUT', expected_version=row['version'])
                self.db.execute("UPDATE outbox SET status='HELD' WHERE task=? AND kind='DISPATCH' AND status='PENDING'", (row['id'],))

    def hold_ready(self, tid):
        with self.transaction():
            self._hold_ready_in_transaction(tid)
        return self.task(tid)

    def recontract_receipt(self, tid):
        rows = self.db.execute("SELECT data FROM events WHERE task=? AND kind='HUMAN_RECONTRACT'", (tid,)).fetchall()
        if len(rows) > 1:
            raise Rejected('Multiple re-contract receipts require explicit reconciliation')
        return json.loads(rows[0]['data']).get('result') if rows else None

    def require_current(self, owner):
        task = self.db.execute("SELECT state FROM tasks WHERE owner=? ORDER BY rowid DESC LIMIT 1", (owner,)).fetchone()
        if task and task['state'] in ('SUPERSEDED', 'ACCEPTED', 'REJECTED', 'CANCELED'):
            raise Rejected('Owner scope is inactive; stale revision cannot dispatch')
        if self.db.execute("SELECT id FROM human_inputs WHERE owner=? AND status='PENDING' LIMIT 1", (owner,)).fetchone():
            raise NeedsInput('Actual human correction is pending; dependent work requires re-contract')
        if self.questions(owner, blocking=True):
            raise NeedsInput('Material question is unanswered or changes a frozen revision; dependent work is held')

    def ask_question(self, owner, scope_key, revision, text):
        with self.transaction():
            task = self.db.execute("SELECT * FROM tasks WHERE owner=? AND logical_key=? ORDER BY rowid DESC LIMIT 1", (owner, scope_key)).fetchone()
            if task and task['state'] in ('SUPERSEDED', 'ACCEPTED', 'REJECTED', 'CANCELED'):
                raise Rejected('Question scope is no longer current')
            if task and task['revision'] != revision:
                raise Rejected('Question revision is stale')
            existing = self.db.execute("SELECT id FROM questions WHERE owner=? AND scope_key=? AND revision=? AND text=? AND status='PENDING'", (owner, scope_key, revision, text)).fetchone()
            if existing:
                if task:
                    self._hold_ready_in_transaction(task['id'])
                return self.question(existing['id'])
            qid = str(uuid.uuid4())
            binding = {'question_id': qid, 'owner': owner, 'scope_key': scope_key, 'task_id': task['id'] if task else None, 'revision': revision, 'packet_hash': task['content_hash'] if task else None}
            event = self.event(binding['task_id'], 'QUESTION', {**binding, 'question': text, 'answer': 'PENDING_HUMAN'})
            self.db.execute("INSERT INTO questions(id,owner,scope_key,task,revision,packet_hash,text,event) VALUES(?,?,?,?,?,?,?,?)", (qid, owner, scope_key, binding['task_id'], revision, binding['packet_hash'], text, event))
            if task:
                self._hold_ready_in_transaction(task['id'])
        return self.question(qid)

    def question(self, qid):
        row = self.db.execute('SELECT * FROM questions WHERE id=?', (qid,)).fetchone()
        if not row:
            raise Rejected('Unknown question')
        q = dict(row)
        return {'question_id': q['id'], 'owner': q['owner'], 'scope_key': q['scope_key'], 'task_id': q['task'], 'revision': q['revision'], 'packet_hash': q['packet_hash'], 'question': q['text'], 'status': q['status'], 'answer_id': q['answer_id'], 'requires_recontract': bool(q['requires_recontract']), 'event': q['event']}

    def answer_question(self, *, question_id, owner, scope_key, task_id, revision, packet_hash, text, origin, source_ref):
        # Only trusted transport callers invoke this. There is deliberately no model RPC.
        if origin not in ('FOREGROUND_HUMAN_STDIN', 'ACTUAL_USER_ANSWER_FORWARDED_FROM_SETUP_CHAT') or not isinstance(source_ref, str) or not source_ref or not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise Rejected('Answer requires actual captured human transport and source reference')
        binding = dict(question_id=question_id, owner=owner, scope_key=scope_key, task_id=task_id, revision=revision, packet_hash=packet_hash)
        aid = identity({**binding, 'text': text, 'origin': origin, 'source_ref': source_ref})
        with self.transaction():
            q = self.question(question_id)
            if any(q[k] != v for k, v in binding.items()):
                raise Rejected('Question answer owner/task/revision binding is stale')
            if task_id:
                task = self.task(task_id)
                if task['owner'] != owner or task['revision'] != revision or task['content_hash'] != packet_hash or task['state'] in ('SUPERSEDED', 'ACCEPTED', 'REJECTED', 'CANCELED'):
                    raise Rejected('Question answer targets an inactive revision')
            elif self.db.execute('SELECT id FROM tasks WHERE owner=? AND logical_key=?', (owner, scope_key)).fetchone():
                raise Rejected('Pre-freeze question answer binding is stale')
            if q['answer_id'] == aid:
                if task_id:
                    self._hold_ready_in_transaction(task_id)
                return {**q, 'answer': text, 'origin': origin, 'source_ref': source_ref}
            if self.db.execute('SELECT id FROM question_answers WHERE id=?', (aid,)).fetchone():
                raise Rejected('An older answer cannot replace a newer correction')
            event = self.event(task_id, 'HUMAN_ANSWER', {**binding, 'answer': text, 'origin': origin, 'source_ref': source_ref, 'supersedes': q['answer_id']})
            self.db.execute('INSERT INTO question_answers(id,question,text,origin,source_ref,binding,event) VALUES(?,?,?,?,?,?,?)', (aid, question_id, text, origin, source_ref, canonical(binding).decode(), event))
            self.db.execute("UPDATE questions SET status='ANSWERED',answer_id=?,requires_recontract=? WHERE id=?", (aid, int(task_id is not None), question_id))
            if task_id:
                self._hold_ready_in_transaction(task_id)
        return {**self.question(question_id), 'answer': text, 'origin': origin, 'source_ref': source_ref}

    def human_answers(self, owner):
        return [dict(r) for r in self.db.execute("SELECT q.id AS question_id,q.text AS question,a.text AS answer,a.origin,a.source_ref,a.event,a.binding FROM questions q JOIN question_answers a ON a.question=q.id WHERE q.owner=? ORDER BY a.event", (owner,))]

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    @contextlib.contextmanager
    def lock(self, name="scheduler"):
        with (self.state / f"{name}.lock").open("a+") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise Rejected(f"An active owner holds {name}") from e
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def event(self, task, kind, data):
        encoded = canonical(data).decode()
        cursor = self.db.execute("INSERT INTO events(task,kind,time,data) VALUES(?,?,?,?)", (task, kind, now(), encoded))
        eid = str(cursor.lastrowid)
        self.db.execute("INSERT INTO outbox(id,task,kind,logical_key,payload) VALUES(?,?,?,?,?)",
                        (str(uuid.uuid4()), task, "NOTE", "note:" + eid, canonical({"seq": int(eid), "kind": kind, "data": data}).decode()))
        return int(eid)

    def task(self, task):
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task,)).fetchone()
        if not row:
            raise Rejected("Unknown task")
        result = dict(row)
        result["packet"] = json.loads(result["packet"])
        return result

    def create(self, key, packet, owner):
        content = identity(packet)
        with self.transaction():
            self.require_current(owner)
            if len(json.dumps(packet).encode()) > 60000:
                raise Rejected('Complete frozen contract exceeds byte budget')
            lineage = packet.get('lineage', {})
            inherited_answers = []
            if lineage.get('recontract_operation'):
                saved = self.recontract_receipt(lineage['parent_task'])
                if 'full_core_lineage' in lineage:
                    from .native_lineage import resolve_native_lineage
                    lineage = resolve_native_lineage(self.home, lineage, saved)
                if not saved or saved['lineage'] != lineage or lineage['successor_owner'] != owner:
                    raise Rejected('Successor does not match the exact prepared re-contract')
                parent = self.task(lineage['parent_task'])
                if parent['state'] != 'SUPERSEDED':
                    raise Rejected('Re-contract parent is not superseded')
                if packet.get('task_revision') != lineage['revision'] or packet.get('source') != parent['packet']['source']:
                    raise Rejected('Successor revision/source differs from the prepared lineage')
                prior = self.db.execute('SELECT logical_key FROM tasks WHERE owner=?', (owner,)).fetchone()
                if prior and prior['logical_key'] != key:
                    raise Rejected('A re-contract has only one bound successor')
                inherited_answers = lineage['human_answers']
            expected_answers = inherited_answers + self.human_answers(owner)
            if expected_answers and packet.get('request', {}).get('human_answers') != expected_answers:
                raise Rejected('Frozen request must preserve exact captured human answers')
            revision = int(packet.get('task_revision', 1))
            if self.db.execute('SELECT id FROM questions WHERE owner=? AND scope_key=? AND task IS NULL AND revision!=?', (owner, key, revision)).fetchone():
                raise Rejected('Question revision differs from the proposed freeze')
            old = self.db.execute("SELECT id,content_hash,owner FROM tasks WHERE logical_key=?", (key,)).fetchone()
            if old:
                if old['owner'] != owner or old["content_hash"] != content:
                    raise Rejected("Logical key conflicts with frozen content")
                return self.task(old["id"])
            blocked = self.db.execute("SELECT id FROM tasks WHERE state NOT IN ('REJECTED','ACCEPTED','CANCELED','SUPERSEDED')").fetchone()
            if blocked:
                raise Rejected("Existing cycle or human gate blocks new task: " + blocked["id"])
            tid = str(uuid.uuid4())
            self.db.execute("INSERT INTO tasks(id,logical_key,content_hash,revision,state,owner,packet) VALUES(?,?,?,?,'READY',?,?)", (tid, key, content, int(packet.get("task_revision", 1)), owner, canonical(packet).decode()))
            self.db.execute("UPDATE questions SET task=?,packet_hash=? WHERE owner=? AND scope_key=? AND task IS NULL", (tid, content, owner, key))
            self.event(tid, "TASK_FROZEN", {"packet": packet, "packet_hash": content, "owner": owner})
            self.db.execute("INSERT INTO outbox(id,task,kind,logical_key,payload) VALUES(?,?,'DISPATCH',?,?)", (str(uuid.uuid4()), tid, "dispatch:" + tid, canonical({"generation": 1, "packet_hash": content}).decode()))
        return self.task(tid)

    def transition_in_transaction(self, tid, expected, target, expected_version=None, **fields):
        """Compose a version-checked transition into the caller's transaction."""
        if not self.db.in_transaction:
            raise Rejected('Transition requires an active transaction')
        permitted = {"candidate", "seal", "review", "outcome", "decision"}
        if not set(fields) <= permitted:
            raise Rejected("Unknown state field")
        t = self.task(tid)
        if t['state'] != expected or (expected_version is not None and t['version'] != expected_version):
            raise Rejected('State/version conflict')
        if target in ('DOER_RUNNING', 'CANDIDATE_SEALED', 'REVIEWER_RUNNING', 'REVIEW_SEALED', 'REPORTING', 'AWAITING_HUMAN'):
            self.require_current(t['owner'])
        values = [target, t['version'] + 1] + list(fields.values()) + [tid, t['version']]
        sql = 'UPDATE tasks SET state=?,version=?' + ''.join(',' + k + '=?' for k in fields) + ' WHERE id=? AND version=?'
        if self.db.execute(sql, values).rowcount != 1:
            raise Rejected('State version conflict')
        self.event(tid, 'STATE', {'from': expected, 'to': target, 'version': t['version'] + 1, **fields})
        return self.task(tid)

    def transition(self, tid, expected, target, **fields):
        with self.transaction():
            result = self.transition_in_transaction(tid, expected, target, **fields)
        return result

    def fence(self, task, generation):
        if self.task(task)["generation"] != generation:
            raise Rejected("Stale attempt generation")

    def close(self):
        self.db.close()
