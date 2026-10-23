import copy
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.adapter import process_identity, terminate, validate_stream
from loop.collector import assess_check, check_command, seal_zip, verify_zip,unittest_evidence
from loop.contract import record_id, validate
from loop.engine import Engine
from loop.notes import Notes
from loop.service import capability, handle, recover
from loop.store import Store
from loop.util import Rejected, atomic, digest, identity, redact, safe_path, tree


def proposal():
    return {"schema_version": 1, "title": "Fixture", "requirements": [{"id": "R1", "text": "Fix the observed defect", "origin": "human fixture", "check_ids": ["C1"]}],
            "allowed_paths": ["module.py"], "steps": [{"id": "S1", "goal": "Fix defect", "allowed_paths": ["module.py"]}],
            "checks": [{"id": "C1", "argv": ["python3", "-m", "unittest"], "required": True, "expected_exit": 0, "baseline_must_fail": True, "requirement_ids": ["R1"]}]}


class IsolatedCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.config = {"notes": str(self.root / "notes"), "authorized_repositories": [], "codex_binary": "/bin/false"}

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def make(self):
        return self.store.create("key", {"requirements": ["frozen"]}, "owner")


class StateTests(IsolatedCase):
    def test_newer_database_is_never_silently_downgraded(self):
        self.store.db.execute("PRAGMA user_version=99")
        with self.assertRaises(Rejected):
            Store(self.root)
        self.assertEqual(99, self.store.db.execute("PRAGMA user_version").fetchone()[0])

    def test_duplicate_submission_has_one_dispatch_F01(self):
        first = self.make()
        self.assertEqual(first["id"], self.make()["id"])
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='DISPATCH'").fetchone()[0])

    def test_conflicting_duplicate_rejected_without_mutation_F02(self):
        self.make()
        with self.assertRaises(Rejected):
            self.store.create("key", {"requirements": ["changed"]}, "owner")
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def test_transaction_rolls_back_event_and_projection_F03(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.store.event(None, "TEST", {})
                raise RuntimeError()
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def test_events_cannot_be_rewritten(self):
        self.make()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("UPDATE events SET kind='FORGED'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("DELETE FROM events")

    def test_single_owner_lock_blocks_second_owner_F35(self):
        second = Store(self.root)
        try:
            with self.store.lock("same-session"):
                with self.assertRaises(Rejected):
                    with second.lock("same-session"):
                        pass
        finally:
            second.close()

    def test_state_version_and_stale_generation_fence_F07(self):
        t = self.make()
        self.store.transition(t["id"], "READY", "DOER_RUNNING")
        with self.assertRaises(Rejected):
            self.store.transition(t["id"], "READY", "DOER_RUNNING")
        self.store.db.execute("UPDATE tasks SET generation=2 WHERE id=?", (t["id"],))
        with self.assertRaises(Rejected):
            self.store.fence(t["id"], 1)

    def test_human_gate_survives_new_store_and_no_dispatch_F24(self):
        t = self.make()
        self.store.transition(t["id"], "READY", "AWAITING_HUMAN")
        other = Store(self.root)
        try:
            recover(other)
            self.assertEqual("AWAITING_HUMAN", other.task(t["id"])["state"])
            with self.assertRaises(Rejected):
                Engine(other, self.config).run(t["id"])
            with self.assertRaises(Rejected):
                other.create("next", {"task": "next"}, "owner")
        finally:
            other.close()

    def test_crash_before_spawn_with_ready_intent_is_preserved_F03(self):
        t = self.make()
        recover(self.store)
        self.assertEqual("READY", self.store.task(t["id"])["state"])
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='DISPATCH'").fetchone()[0])

    def test_spawn_without_receipt_is_uncertain_never_redispatched_F04_F40(self):
        t = self.make()
        self.store.transition(t["id"], "READY", "DOER_RUNNING")
        self.store.db.execute("INSERT INTO attempts(id,task,generation,role,status,pid,start_identity,output) VALUES('a',?,1,'doer','RUNNING',?,'not-current','capture')", (t["id"], os.getpid()))
        recover(self.store)
        self.assertEqual("DISPATCH_UNCERTAIN", self.store.task(t["id"])["state"])
        with self.assertRaises(Rejected):
            Engine(self.store, self.config).run(t["id"])

    def test_pid_reuse_reconciliation_fences_without_signaling_other_process_F40(self):
        from loop.cli import reconcile_attempt
        t = self.make()
        self.store.transition(t["id"], "READY", "DISPATCH_UNCERTAIN")
        self.store.db.execute("INSERT INTO attempts(id,task,generation,role,status,pid,start_identity,output) VALUES('lost',?,1,'doer','DISPATCH_UNCERTAIN',?,'different-start','capture')", (t["id"], os.getpid()))
        with patch("loop.cli.os.killpg") as group_signal, patch("loop.cli.signal.pidfd_send_signal") as exact_signal:
            result = reconcile_attempt(self.store, "lost")
        group_signal.assert_not_called()
        exact_signal.assert_not_called()
        self.assertEqual("FENCED", result["status"])
        self.assertEqual("BLOCKED", self.store.task(t["id"])["state"])
        self.assertEqual(2, self.store.task(t["id"])["generation"])
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0])


class CapabilityTests(IsolatedCase):
    def test_role_receipt_cannot_add_a_human_actor_field_F23(self):
        t = {"content_hash": "packet", "packet": {"source": {"source_hash": "source"}, "instructions_hash": "instructions", "requirements_hash": "requirements", "requirements": [{"id": "R1"}]}}
        receipt = {"packet_hash": "packet", "source_hash": "source", "instructions_hash": "instructions", "requirements_hash": "requirements", "requirement_ids": ["R1"], "status": "ACK", "summary": "Observed receipt"}
        engine = Engine(self.store, self.config)
        engine.ack(t, receipt)
        with self.assertRaises(Rejected):
            engine.ack(t, {**receipt, "actor": "human"})

    def test_busy_human_correction_blocks_stale_dispatch_and_report_F25(self):
        t = self.make()
        self.store.db.execute("INSERT INTO human_inputs(owner,time,text,origin) VALUES('owner','now','Preserve new correction','ACTUAL_TEST_FIXTURE')")
        engine = Engine(self.store, self.config)
        with self.assertRaises(Rejected):
            engine.require_current(t)
        result = engine.result(t["id"], "owner")
        self.assertEqual("NEEDS_INPUT", result["state"])
        self.assertNotIn("package", result)

    def packet(self, op, args):
        token = capability(self.store, "owner", {"repo": "/not-authorized", "request": {"text": "exact human request"}, "key": "key"})
        return {"capability": token, "operation": op, "arguments": args}

    def test_forged_capability_cannot_authorize(self):
        with self.assertRaises(Rejected):
            handle(self.store, self.config, {"capability": "fake", "operation": "submit_task", "arguments": {}})

    def test_no_role_accept_or_dispatch_endpoint_F16_F23_F34(self):
        for op in ("accept", "decide", "dispatch", "next"):
            with self.subTest(op=op), self.assertRaises(Rejected):
                handle(self.store, self.config, self.packet(op, {"actor": "human"}))

    def test_model_actor_cannot_replace_transport_origin_F23(self):
        with self.assertRaises(Rejected):
            handle(self.store, self.config, self.packet("submit_task", {"proposal": proposal(), "actor": "human"}))

    def test_repository_must_be_human_registered(self):
        with self.assertRaises(Rejected):
            handle(self.store, self.config, self.packet("submit_task", {"proposal": proposal()}))

    def test_wrong_owner_cannot_receive_result(self):
        t = self.make()
        with self.assertRaises(Rejected):
            Engine(self.store, self.config).result(t["id"], "different-thinker")

    def test_read_artifact_cannot_escape_F22(self):
        t = self.make()
        with self.assertRaises(Rejected):
            handle(self.store, self.config, self.packet("read_artifact", {"task": t["id"], "path": "../../secret"}))

    def test_unknown_answer_stays_pending_human(self):
        answer = handle(self.store, self.config, self.packet("ask_human", {"question": "Blank name behavior?"}))
        self.assertEqual("NEEDS_INPUT", answer["result"]["status"])
        self.assertIn("PENDING_HUMAN", self.store.db.execute("SELECT data FROM events WHERE kind='QUESTION'").fetchone()[0])

    def test_human_decision_without_controlling_tty_is_rejected_F16(self):
        from loop.cli import require_human_tty
        with patch("loop.cli.open", side_effect=OSError("No controlling terminal")):
            with self.assertRaises(Rejected):
                require_human_tty()


class ContractTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "fixtures/repo"
        self.repo.mkdir(parents=True)
        (self.repo / "module.py").write_text("value=1\n")
        for cmd in [["git", "init", "-q", str(self.repo)], ["git", "-C", str(self.repo), "add", "."],
                    ["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "-qm", "Baseline"]]:
            subprocess.run(cmd, check=True, capture_output=True)
        self.config["authorized_repositories"] = [str(self.repo)]

    def test_noncommand_constraint_requires_review_without_fabricated_command(self):
        p = proposal()
        p["requirements"].append({"id": "R2", "text": "No publication", "origin": "actual constraint", "check_ids": []})
        packet = validate(p, self.repo, {"text": "original"}, [])
        self.assertEqual("review", packet["requirements"][1]["verification"])
        p["requirements"][1]["verification"] = "command"
        with self.assertRaises(Rejected):
            validate(p, self.repo, {"text": "original"}, [])

    def test_source_and_instruction_drift_invalidate_frozen_preflight_F13_F44(self):
        engine = Engine(self.store, self.config)
        receipt = engine.submit(proposal(), self.repo, {"text": "Fix observed defect"}, "owner", "frozen")
        t = self.store.task(receipt["task"])
        engine.verify_inputs(t)
        (self.repo / "module.py").write_text("value=2\n")
        with self.assertRaises(Rejected):
            engine.verify_inputs(t)

    def test_recontract_preserves_old_packet_and_links_exact_new_correction(self):
        from loop.cli import prepare_recontract
        engine = Engine(self.store, self.config)
        receipt = engine.submit(proposal(), self.repo, {"text": "Exact original request"}, "owner", "frozen")
        tid = receipt["task"]
        packet_file = self.root / "artifacts" / tid / "packet.json"
        frozen_bytes = packet_file.read_bytes()
        with self.assertRaises(Rejected):
            prepare_recontract(self.store, engine, tid, "Cannot bypass a ready writer")
        self.store.transition(tid, "READY", "NEEDS_INPUT")
        repo, text, lineage = prepare_recontract(self.store, engine, tid, "Preserve the explicit Guest behavior")
        self.assertEqual(frozen_bytes, packet_file.read_bytes())
        self.assertEqual(2, lineage["revision"])
        self.assertEqual("Exact original request", lineage["preserved_request"]["text"])
        self.assertIn("Preserve the explicit Guest behavior", text)
        self.assertEqual("SUPERSEDED", self.store.task(tid)["state"])
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def test_arbitrary_source_config_requires_explicit_qualification_F41(self):
        (self.repo / ".codex").mkdir()
        (self.repo / ".codex/config.toml").write_text('sandbox_mode="danger-full-access"\n')
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "-qm", "Untrusted configuration"], check=True)
        with self.assertRaises(Rejected):
            validate(proposal(), self.repo, {"text": "request"}, [])


class StreamTests(unittest.TestCase):
    def test_pinned_exporter_retains_visible_records_and_excludes_reasoning(self):
        from export_setup_session import export
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thread = "00000000-0000-4000-8000-000000000001"
            events = [{"type": "session_meta", "payload": {"id": thread, "cli_version": "0.162.0-alpha.17.2"}},
                      {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "exact request"}]}},
                      {"type": "response_item", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "privileged"}]}},
                      {"type": "response_item", "payload": {"type": "reasoning", "text": "private"}}]
            source = root / "session.jsonl"
            source.write_text("".join(json.dumps(e) + "\n" for e in events))
            before = source.read_bytes()
            report = export(source, thread, root / "export")
            self.assertEqual(before, source.read_bytes())
            self.assertEqual(1, report["visible_records"])
            visible = (root / "export/visible.jsonl").read_text()
            self.assertIn("exact request", visible)
            self.assertNotIn("privileged", visible)
            self.assertNotIn("private", visible)
            with self.assertRaises(Rejected):
                export(source, "00000000-0000-4000-8000-000000000002", root / "wrong")

    def stream(self, *extra):
        return b"\n".join(json.dumps(v).encode() for v in ({"type": "thread.started", "thread_id": "0197d81b-6a51-7000-8000-000000000001"}, {"type": "turn.started"}, *extra, {"type": "turn.completed"})) + b"\n"

    def test_real_terminal_contract_not_exit_alone_F39(self):
        self.assertEqual("0197d81b-6a51-7000-8000-000000000001", validate_stream(self.stream(), 0, "final")[0])
        for raw, code, final in [(b"", 0, "stale"), (self.stream(), 1, "final"), (self.stream(), 0, None), (self.stream()[:-1], 0, "final")]:
            with self.subTest(raw=raw, code=code), self.assertRaises(Rejected):
                validate_stream(raw, code, final)

    def test_unknown_events_retained_without_inventing_error(self):
        _, events = validate_stream(self.stream({"type": "new.event", "data": 3}), 0, "final")
        self.assertIn({"type": "new.event", "data": 3}, events)

    def test_error_or_conflicting_thread_blocks_success_F39(self):
        for e in [{"type": "error"}, {"type": "turn.failed"}, {"type": "item.completed", "item": {"type": "error"}}, {"type": "thread.started", "thread_id": "wrong"}]:
            with self.subTest(e=e), self.assertRaises(Rejected):
                validate_stream(self.stream(e), 0, "final")

    def test_malformed_capture_is_not_pass_F10(self):
        with self.assertRaises(Rejected):
            validate_stream(self.stream() + b"not-json\n", 0, "final")


class EvidenceTests(IsolatedCase):
    def test_valid_archive_for_another_task_cannot_be_delivered(self):
        t = self.make()
        src = self.root / "source"
        src.mkdir()
        (src / "file.py").write_text("value=1\n")
        package = seal_zip(self.root / "wrong-task.zip", {"source": src}, {"task": "another-task", "packet_hash": t["content_hash"], "candidate": "candidate"})
        self.store.transition(t["id"], "READY", "REPORTING", review=json.dumps({k: package[k] for k in ("path", "sha256", "bytes")}), seal=json.dumps({"commit": "candidate", "files": {}}))
        with self.assertRaisesRegex(Rejected, "different task"):
            Engine(self.store, self.config).result(t["id"], "owner")

    def test_valid_archive_with_wrong_source_cannot_be_delivered(self):
        t = self.make()
        src = self.root / "source"
        src.mkdir()
        (src / "file.py").write_text("value=1\n")
        package = seal_zip(self.root / "wrong-source.zip", {"evidence/candidate-source": src}, {"task": t["id"], "packet_hash": t["content_hash"], "candidate": "candidate"})
        self.store.transition(t["id"], "READY", "REPORTING", review=json.dumps({k: package[k] for k in ("path", "sha256", "bytes")}), seal=json.dumps({"commit": "candidate", "files": {"file.py": {"sha256": "wrong"}}}))
        with self.assertRaisesRegex(Rejected, "Archived source"):
            Engine(self.store, self.config).result(t["id"], "owner")

    def test_managed_index_preserves_later_human_edits(self):
        notes = Notes(self.store, self.config["notes"])
        notes.replay()
        p = notes.root / "00_HOME.md"
        p.write_text(p.read_text() + "\nHuman addition\n")
        with self.assertRaises(Rejected):
            notes.replay()
        self.assertIn("Human addition", p.read_text())

    def test_path_traversal_symlink_and_absolute_rejected_F22(self):
        (self.root / "link").symlink_to("/tmp", target_is_directory=True)
        for p in ("../file", "/file", "link/file"):
            with self.subTest(p=p), self.assertRaises(Rejected):
                safe_path(self.root, p)

    def test_projection_conflict_keeps_pending_and_replays_F20(self):
        self.make()
        notes = Notes(self.store, self.config["notes"])
        target = notes.root / "System/Events/00000001.md"
        target.parent.mkdir(parents=True)
        target.write_text("human note wins")
        with self.assertRaises(Rejected):
            notes.replay()
        self.assertEqual("human note wins", target.read_text())
        target.rename(target.with_suffix(".human.md"))
        notes.replay()
        count = notes.reconcile()["events"]
        notes.replay()
        self.assertEqual(count, notes.reconcile()["events"])

    def test_projection_io_failure_keeps_pending_F20_F21(self):
        self.make()
        notes = Notes(self.store, self.config["notes"])
        with patch("loop.notes.atomic", side_effect=OSError("Disk full")):
            with self.assertRaises(OSError):
                notes.replay()
        self.assertGreater(self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='NOTE' AND status='PENDING'").fetchone()[0], 0)
        notes.replay()
        notes.reconcile()

    def test_note_or_attachment_tampering_blocks_completion_F14(self):
        self.make()
        notes = Notes(self.store, self.config["notes"])
        notes.replay()
        p = self.root / "evidence.txt"
        p.write_text("proof")
        attachment = notes.attach(p, "TRUSTED_FIXTURE")
        Path(attachment["path"]).write_text("changed")
        with self.assertRaises(Rejected):
            notes.reconcile()

    def test_atomic_exclusive_write_preserves_human_file_F21(self):
        p = self.root / "human.md"
        atomic(p, "human", exclusive=True)
        with self.assertRaises(Rejected):
            atomic(p, "agent", exclusive=True)
        self.assertEqual("human", p.read_text())

    def test_secret_redacted_before_projection_F29(self):
        secret = "fixture-private-value-12345"
        p = self.root / "output.txt"
        p.write_text("secret=" + secret + "\nBearer ABCDEFGHIJKLMNO\nsk-12345678901234567890")
        notes = Notes(self.store, self.config["notes"])
        attached = notes.attach(p, "SECRET_FIXTURE")
        text = Path(attached["path"]).read_text()
        self.assertNotIn(secret, text)
        self.assertNotIn("ABCDEFGHIJKLMNO", text)
        self.assertNotIn("sk-123", text)

    def test_redacted_json_preserves_event_framing(self):
        value = {"type": "item.completed", "item": {"secret": "fixture-secret", "text": "secret=fixture-value"}}
        redacted = json.loads(redact(json.dumps(value)))
        self.assertEqual("item.completed", redacted["type"])
        self.assertEqual("[REDACTED]", redacted["item"]["secret"])
        self.assertNotIn("fixture-value", redacted["item"]["text"])

    def test_zip_manifest_and_whole_archive_tamper_rejected_F30(self):
        src = self.root / "source"
        src.mkdir()
        (src / "module.py").write_text("value=3\n")
        package = seal_zip(self.root / "review.zip", {"source": src}, {"source": "frozen"})
        extracted = self.root / "extracted"
        verify_zip(package["path"], package["sha256"], extracted)
        self.assertEqual("value=3\n", (extracted / "source/module.py").read_text())
        with zipfile.ZipFile(package["path"], "a") as z:
            z.writestr("unexpected.txt", "extra")
        with self.assertRaises(Rejected):
            verify_zip(package["path"], package["sha256"])
        with self.assertRaises(Rejected):
            verify_zip(package["path"])

    def test_skipped_missing_failed_or_source_mutating_check_never_passes_F12_F15(self):
        spec = proposal()["checks"][0]
        baseline = {"exit": 1, "timeout": False, "source_unchanged": True, "skip_detected": False}
        baseline['test_run']=unittest_evidence(spec['argv'],'','test_behavior (fixture.C.test_behavior) ... FAIL\nRan 1 test in 0.01s\nAssertionError: expected behavior\nFAILED (failures=1)\n')
        candidate = {**baseline, "exit": 0, 'test_run':unittest_evidence(spec['argv'],'','test_behavior (fixture.C.test_behavior) ... ok\nRan 1 test in 0.01s\nOK\n')}
        self.assertEqual("PASS", assess_check(spec, baseline, candidate))
        self.assertEqual("FAIL", assess_check(spec, baseline, {**candidate, "exit": 1}))
        for altered in ({**candidate, "skip_detected": True}, {**candidate, "source_unchanged": False}, None):
            self.assertEqual("UNVERIFIED", assess_check(spec, baseline, altered))
        self.assertEqual("UNVERIFIED", assess_check(spec, candidate, candidate))

    def test_record_ids_cannot_be_used_as_paths(self):
        for value in ("../escape", "/absolute", "a/b", "", None):
            with self.subTest(value=value), self.assertRaises(Rejected):
                record_id(value)

    def test_wrong_hash_revision_candidate_or_confirmation_preserves_gate_F32(self):
        from loop.cli import decide
        t = self.make()
        evidence = self.root / "artifacts" / t["id"]
        evidence.mkdir(parents=True)
        (evidence / "source.txt").write_text("frozen")
        package = seal_zip(self.root / "review.zip", {"evidence": evidence}, {"task": t["id"], "packet_hash": t["content_hash"], "candidate": "candidate"})
        receipt = {k: package[k] for k in ("path", "sha256", "bytes")}
        gated = self.store.transition(t["id"], "READY", "AWAITING_HUMAN", review=json.dumps(receipt), seal=json.dumps({"commit": "candidate"}), outcome="PASS")
        cases = [("wrong", t["content_hash"], "candidate", gated["version"]), (package["sha256"], "wrong", "candidate", gated["version"]),
                 (package["sha256"], t["content_hash"], "wrong", gated["version"]), (package["sha256"], t["content_hash"], "candidate", 999),
                 (package["sha256"], t["content_hash"], "candidate", gated["version"])]
        for sha, packet, candidate, version in cases:
            with self.subTest(sha=sha, version=version), self.assertRaises(Rejected):
                decide(self.store, Engine(self.store, self.config), t["id"], "accept", sha, packet, candidate, version, "forged agent confirmation")
            self.assertEqual("AWAITING_HUMAN", self.store.task(t["id"])["state"])


class LiveLocalRunnerTests(IsolatedCase):
    def test_trusted_runner_has_no_network_or_host_source_F28(self):
        repo = self.root / "checkout"
        repo.mkdir()
        (repo / "code.py").write_text("x=1\n")
        parent_auth = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'auth.json'
        command = ['python3', '-c', 'import pathlib,socket; assert not pathlib.Path(' + repr(str(parent_auth)) + ').exists(); s=socket.socket(); assert s.connect_ex(("1.1.1.1",443)) != 0; print("CONFIRMED")']
        result = check_command(repo, command, self.root / "run")
        self.assertEqual(0, result["exit"])
        self.assertTrue(result["source_unchanged"])
        self.assertIn("CONFIRMED", (self.root / "run/stdout.txt").read_text())

    def test_timeout_terminates_the_private_process_tree_F05_F11_F27(self):
        repo = self.root / "checkout"
        repo.mkdir()
        result = check_command(repo, ["python3", "-c", "import subprocess,time; subprocess.Popen(['sleep','30']); time.sleep(30)"], self.root / "run", timeout=0.1)
        self.assertTrue(result["timeout"])
        self.assertNotEqual(0, result["exit"])


if __name__ == "__main__":
    unittest.main()
