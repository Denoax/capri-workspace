import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
import uuid

from .confinement import argv, prepare_runtime
from .event_stream import EventStream, validate_stream
from .util import Rejected, atomic, digest, identity, now, redact, tree, write_json


def process_identity(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            return None
        return stat[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    # bwrap's private PID namespace kills descendants when its PID 1 exits.
    if process_identity(process.pid) is not None:
        raise Rejected("Process termination is not reconciled")


class Adapter:
    def __init__(self, store, config):
        self.store, self.config = store, config
        self.home = store.home

    def run(self, task, role, workspace, inputs, prompt, schema=None, resume=None, runtime=None, capability=None, timeout=180):
        if task:
            self.store.require_current(self.store.task(task)['owner'])
        binary = Path(self.config["codex_binary"]).resolve()
        if self.config.get("binary_sha256") and digest(binary.read_bytes()) != self.config["binary_sha256"]:
            raise Rejected("Pinned Codex binary changed; requalification required")
        aid = str(uuid.uuid4())
        output = self.home / "artifacts" / (task or "setup") / "attempts" / aid
        output.mkdir(parents=True, mode=0o700)
        runtime = Path(runtime or self.home / "runtime" / aid)
        prepare_runtime(runtime, role, capability)
        command = ["--no-daemon", "exec", "--strict-config", "--json", "--cd", "/workspace", "-o", "/codex-home/final.txt"]
        if schema:
            write_json(Path(inputs) / "response.schema.json", schema)
            command += ["--output-schema", "/inputs/response.schema.json"]
        lifecycle = EventStream(expected_thread=resume)
        if resume:
            uuid.UUID(resume)
            command += ["resume", resume]
        command += ["-"]
        socket = self.store.state / "intake.sock" if capability else None
        cmd = argv(self.config["codex_binary"], runtime, workspace, inputs, self.home / "controller", role, command, socket)
        atomic(output / "prompt.md", redact(prompt), exclusive=True)
        write_json(output / "launch.json", {"argv": cmd, "role": role, "time": now(), "resume": resume,
                   "requested_model": "gpt-6.1-sol", "effort": "high" if role == "reviewer" else "medium", "provider_model_confirmation": "NOT_EXPOSED_IN_EXEC_JSONL", "config_sha256": digest((runtime / "config.toml").read_bytes()), "controller_source_hash": identity(tree(self.home / "controller")), "context_occupancy": "UNKNOWN"})
        generation = self.store.task(task)["generation"] if task else 0
        with self.store.transaction():
            if task:
                self.store.require_current(self.store.task(task)['owner'])
            self.store.db.execute("INSERT INTO attempts(id,task,generation,role,status,output) VALUES(?,?,?,?,?,?)", (aid, task, generation, role, "SPAWN_INTENT", str(output)))
            self.store.event(task, "DISPATCH_INTENT", {"attempt": aid, "role": role, "output": str(output), "generation": generation})
        final_path = runtime / "final.txt"
        if final_path.exists():
            final_path.unlink()
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        start_id = process_identity(process.pid)
        with self.store.transaction():
            self.store.db.execute("UPDATE attempts SET status='RUNNING',pid=?,start_identity=? WHERE id=?", (process.pid, start_id, aid))
        process.stdin.write(prompt.encode())
        process.stdin.close()
        selector = selectors.DefaultSelector()
        streams = {"stdout": (output / "events.jsonl").open("wb"), "stderr": (output / "stderr.txt").open("wb")}
        buffers = {"stdout": b"", "stderr": b""}
        for name, pipe in [("stdout", process.stdout), ("stderr", process.stderr)]:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        started = time.monotonic()
        total = 0
        failure = None
        termination_uncertain = False
        tool_interactions = 0
        observed_thread = None
        execution_ack = role != "doer"
        expected_marker = "ACK:" + self.store.task(task)["content_hash"] if role == "doer" else None
        try:
            while selector.get_map():
                if time.monotonic() - started > timeout:
                    raise Rejected("Wall budget exceeded; process terminated; task requires reconciliation")
                for key, _ in selector.select(timeout=0.2):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    name = key.data
                    if not chunk:
                        selector.unregister(key.fileobj)
                        if buffers[name]:
                            fragment = buffers[name]
                            streams[name].write(redact(fragment.decode(errors="replace")).encode())
                            buffers[name] = b""
                            if name == "stdout":
                                lifecycle.feed_line(fragment)
                        continue
                    total += len(chunk)
                    if total > 32_000_000:
                        raise Rejected("Capture budget exceeded; coverage incomplete")
                    buffers[name] += chunk
                    while b"\n" in buffers[name]:
                        line, buffers[name] = buffers[name].split(b"\n", 1)
                        streams[name].write(redact(line.decode(errors="replace")).encode() + b"\n")
                        streams[name].flush()
                        os.fsync(streams[name].fileno())
                        if name == "stdout":
                            event = lifecycle.feed_line(line + b"\n")
                            if event["type"] == "thread.started":
                                observed_thread = lifecycle.thread
                                self.store.db.execute("UPDATE attempts SET thread=? WHERE id=?", (observed_thread, aid))
                            if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message" and expected_marker:
                                execution_ack = execution_ack or event["item"].get("text", "").startswith(expected_marker)
                            if event.get("type") == "item.started" and event.get("item", {}).get("type") in ("command_execution", "mcp_tool_call"):
                                if not execution_ack:
                                    raise Rejected("Execution attempted before exact packet marker ACK")
                                tool_interactions += 1
                                if tool_interactions > 12:
                                    raise Rejected("Exposed tool-interaction budget exceeded; checkpoint/rehydration required")
            process.wait(timeout=10)
        except BaseException as ex:
            failure = ex
        finally:
            if process.poll() is None:
                try:
                    terminate(process)
                except BaseException:
                    termination_uncertain = True
                    failure = Rejected("Process termination is not reconciled; effects uncertain")
            # Keep all bytes already read, including the rest of a rejected chunk.
            # Pipes may contain unread bytes after early termination: coverage is partial.
            for name, pending in buffers.items():
                if pending:
                    parts = pending.split(b"\n")
                    for part in parts[:-1]:
                        streams[name].write(redact(part.decode(errors="replace")).encode() + b"\n")
                    if parts[-1]:
                        streams[name].write(redact(parts[-1].decode(errors="replace")).encode())
            for stream in streams.values():
                stream.flush()
                os.fsync(stream.fileno())
                stream.close()
            selector.close()
            process.stdout.close()
            process.stderr.close()
        final = redact(final_path.read_text()) if final_path.exists() else None
        atomic(output / ("final.json" if schema else "final.md"), final or "")
        result = {"attempt": aid, "exit": process.returncode, "pid": process.pid, "start_identity": start_id, "duration_seconds": time.monotonic() - started,
                  "capture": str(output), "thread": observed_thread, "tool_interactions": tool_interactions, "coverage": "COMPLETE_FOR_OBSERVED_INTERFACE" if failure is None else "PARTIAL", "failure": str(failure) if failure else None,
                  "lifecycle": {"state": lifecycle.state, "line": lifecycle.line, "byte": lifecycle.offset,
                                "offset_basis": "ORIGINAL_OBSERVED_STDOUT_BYTES", "unknown_records": lifecycle.unknown_records},
                  "context_occupancy": "UNKNOWN"}
        try:
            if failure:
                raise failure
            lifecycle.finish(process.returncode, final)
            thread, events = validate_stream((output / "events.jsonl").read_bytes(), process.returncode, final, expected_thread=resume)
            if task:
                self.store.fence(task, generation)
            result["thread"] = thread
            result["events"] = len(events)
            result["status"] = "COMPLETED"
            response = json.loads(final) if schema else final
        except BaseException as ex:
            result["status"] = "DISPATCH_UNCERTAIN" if termination_uncertain else "FAILED"
            result["failure"] = str(ex)
            write_json(output / "receipt.json", result)
            with self.store.transaction():
                self.store.db.execute("UPDATE attempts SET status=?,result=? WHERE id=?", (result["status"], json.dumps(result), aid))
                self.store.event(task, "ROLE_FAILED", result)
            raise
        write_json(output / "receipt.json", result)
        with self.store.transaction():
            self.store.db.execute("UPDATE attempts SET status='COMPLETED',thread=?,result=? WHERE id=?", (thread, json.dumps(result), aid))
            if task:
                self.store.db.execute("INSERT OR IGNORE INTO sessions(id,owner,role,runtime) VALUES(?,?,?,?)", (thread, self.store.task(task)["owner"], role, str(runtime)))
            self.store.event(task, "ROLE_COMPLETED", result)
        return response, result
