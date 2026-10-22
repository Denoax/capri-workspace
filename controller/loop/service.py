import json
import os
from pathlib import Path
import secrets
import socket
import socketserver
import struct
import threading
import time

from .engine import Engine
from .store import Store
from .util import NeedsInput, Rejected, canonical, digest, now, safe_path


def capability(store, owner, scope):
    token = secrets.token_urlsafe(32)
    store.db.execute("INSERT INTO capabilities(token_hash,owner,scope) VALUES(?,?,?)", (digest(token.encode()), owner, json.dumps(scope)))
    return token


def request(socket_path, token, operation, arguments):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(25)
        connection.connect(str(socket_path))
        connection.sendall(canonical({"capability": token, "operation": operation, "arguments": arguments}) + b"\n")
        with connection.makefile("rb") as reader:
            return json.loads(reader.readline(1_000_001))


def handle(store, config, packet):
    if not isinstance(packet, dict) or set(packet) != {"capability", "operation", "arguments"} or not isinstance(packet["arguments"], dict):
        raise Rejected("Malformed scoped request")
    cap = store.db.execute("SELECT * FROM capabilities WHERE token_hash=? AND enabled=1", (digest(packet["capability"].encode()),)).fetchone()
    if not cap:
        raise Rejected("Invalid or revoked capability")
    scope = json.loads(cap["scope"])
    op, args = packet["operation"], packet["arguments"]
    engine = Engine(store, config)
    if op == "submit_task":
        store.require_current(cap['owner'])
        if set(args) != {"proposal"}:
            raise Rejected("Unknown submit field; origin cannot be supplied by a model")
        result = engine.submit(args["proposal"], scope["repo"], scope["request"], cap["owner"], scope["key"])
    elif op in ("request_status", "read_artifact"):
        if set(args) != ({"task"} if op == "request_status" else {"task", "path"}):
            raise Rejected("Unknown artifact/status argument")
        t = store.task(args["task"])
        if t["owner"] != cap["owner"]:
            raise Rejected("Task belongs to a different Thinker owner")
        if op == "request_status":
            result = engine.result(t["id"], cap["owner"])
        else:
            path = safe_path(store.home / "artifacts" / t["id"], args["path"])
            if not path.is_file() or path.stat().st_size > 100000:
                raise Rejected("Artifact missing or exceeds read budget")
            result = {"text": path.read_text(), "sha256": digest(path.read_bytes())}
    elif op == "ask_human":
        if set(args) != {"question"} or not isinstance(args["question"], str) or not 0 < len(args["question"]) <= 4000:
            raise Rejected("Invalid question")
        revision = int(scope['request'].get('lineage', {}).get('revision', 1))
        result = store.ask_question(cap['owner'], scope['key'], revision, args['question'])
        result = {**result, 'answer_status': result['status'], 'status': 'NEEDS_INPUT'}
    else:
        raise Rejected("Operation is not available to model roles")
    with store.transaction():
        store.event(None, "SCOPED_TOOL", {"owner": cap["owner"], "operation": op, "arguments": args, "result": result})
    return {"ok": True, "origin": "CONTROLLER_DATA_NOT_HUMAN", "result": result}


def serve(home, config, stop=None):
    stop = stop or threading.Event()
    store = Store(home)
    with store.lock("service"):
        socket_path = store.state / "intake.sock"
        if socket_path.exists():
            socket_path.unlink()

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                uid = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                connection_store = Store(home)
                try:
                    if uid != os.getuid():
                        raise Rejected("Peer uid mismatch")
                    raw = self.rfile.readline(1_000_001)
                    if len(raw) > 1_000_000 or not raw.endswith(b"\n"):
                        raise Rejected("Request exceeds framing budget")
                    result = handle(connection_store, config, json.loads(raw))
                except Exception as ex:
                    result = {"ok": False, "error": str(ex), "origin": "CONTROLLER_DATA_NOT_HUMAN"}
                finally:
                    connection_store.close()
                self.wfile.write(canonical(result) + b"\n")

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True

        server = Server(str(socket_path), Handler)
        os.chmod(socket_path, 0o600)
        server.timeout = 0.25
        listener = threading.Thread(target=lambda: _listen(server, stop), daemon=True)
        listener.start()
        with store.transaction():
            store.event(None, "CONTROLLER_STARTED", {"pid": os.getpid(), "time": now(), "queue_route": "DISABLED", "app_server": "NOT_USED"})
        try:
            recover(store)
            while not stop.wait(0.25):
                rows = store.db.execute("SELECT id FROM tasks WHERE state='READY' ORDER BY rowid LIMIT 1").fetchall()
                for row in rows:
                    try:
                        Engine(store, config).run(row["id"])
                    except NeedsInput:
                        # The durable hold already owns its NOTE; this is not an error loop.
                        pass
                    except Exception as ex:
                        with store.transaction():
                            store.event(row["id"], "SCHEDULER_ERROR", {"error": str(ex)})
                try:
                    Engine(store, config).notes.replay()
                except (OSError, Rejected) as ex:
                    # Preserve pending projection; no completed-gate claim is made.
                    print("Projection pending: " + str(ex), flush=True)
        finally:
            stop.set()
            listener.join(timeout=3)
            server.server_close()
            socket_path.unlink(missing_ok=True)
            store.close()


def _listen(server, stop):
    while not stop.is_set():
        server.handle_request()


def recover(store):
    """Uncertain side effects are fenced, never replayed as a second writer."""
    from .adapter import process_identity
    for row in store.db.execute("SELECT * FROM attempts WHERE status IN ('SPAWN_INTENT','RUNNING')").fetchall():
        observed = process_identity(row["pid"]) if row["pid"] else None
        with store.transaction():
            store.db.execute("UPDATE attempts SET status='DISPATCH_UNCERTAIN' WHERE id=?", (row["id"],))
            store.event(row["task"], "DISPATCH_UNCERTAIN", {"attempt": row["id"], "pid": row["pid"], "saved_start": row["start_identity"], "observed_start": observed,
                "next_action": "Verify old namespace exited; preserve candidate/capture; require explicit scoped recovery before a new attempt"})
        if row["task"]:
            t = store.task(row["task"])
            if t["state"] not in ("AWAITING_HUMAN", "REPORTING", "DISPATCH_UNCERTAIN"):
                store.transition(t["id"], t["state"], "DISPATCH_UNCERTAIN")
