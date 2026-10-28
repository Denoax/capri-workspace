"""Synthetic protocol regressions, not authentic producer qualification."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.adapter import validate_stream
from loop.util import Rejected


THREAD = "0197d81b-6a51-7000-8000-000000000001"
OTHER = "0197d81b-6a51-7000-8000-000000000002"
START = {"type": "thread.started", "thread_id": THREAD}
TURN = {"type": "turn.started"}
DONE = {"type": "turn.completed"}
COMMAND = {"type": "item.started", "item": {"id": "cmd", "type": "command_execution"}}
MESSAGE = {"type": "item.completed", "item": {"id": "msg", "type": "agent_message", "text": "hello"}}


def capture(*events):
    return b"".join(json.dumps(event).encode() + b"\n" for event in events)


class LifecycleTests(unittest.TestCase):
    def rejected(self, *events):
        with self.assertRaises(Rejected):
            validate_stream(capture(*events), 0, "final")

    # Keep these on the original three-argument public API so they can be
    # transplanted unchanged onto e2de086 and demonstrate each defect.
    def test_missing_turn_start(self):
        self.rejected(START, DONE)

    def test_duplicate_identical_thread_start(self):
        self.rejected(START, START, TURN, DONE)

    def test_completion_before_start(self):
        self.rejected(START, DONE, TURN)

    def test_command_after_completion(self):
        self.rejected(START, TURN, DONE, COMMAND)

    def test_duplicate_completion(self):
        self.rejected(START, TURN, DONE, DONE)

    def test_conflicting_identity(self):
        self.rejected(START, {"type": "thread.started", "thread_id": OTHER}, TURN, DONE)

    def test_valid_fresh_and_unpaired_agent_completion(self):
        events = [START, TURN, MESSAGE, DONE]
        self.assertEqual((THREAD, events), validate_stream(capture(*events), 0, "final"))

    def test_exact_resume_and_repeated_identity_across_attempts(self):
        for _ in range(2):
            self.assertEqual(THREAD, validate_stream(capture(START, TURN, DONE), 0, "final", expected_thread=THREAD)[0])

    def test_wrong_resume_identity(self):
        with self.assertRaises(Rejected):
            validate_stream(capture(START, TURN, DONE), 0, "final", expected_thread=OTHER)

    def test_invalid_uuid(self):
        for value in (None, 3, "uuid", "", THREAD.replace("-", "")):
            with self.subTest(value=value):
                self.rejected({"type": "thread.started", "thread_id": value}, TURN, DONE)

    def test_missing_and_duplicate_lifecycle_records(self):
        for events in ((), (TURN, DONE), (START,), (START, TURN), (START, TURN, TURN, DONE), (START, TURN, DONE, TURN)):
            with self.subTest(events=events):
                self.rejected(*events)

    def test_explicit_failures(self):
        for error in ({"type": "error"}, {"type": "turn.failed"}, {"type": "item.completed", "item": {"type": "error"}}):
            with self.subTest(error=error):
                self.rejected(START, TURN, error, DONE)
                self.rejected(START, TURN, DONE, error)

    def test_exit_and_final_file_are_not_lifecycle_authority(self):
        for code, final in ((1, "final"), (0, None)):
            with self.subTest(code=code, final=final), self.assertRaises(Rejected):
                validate_stream(capture(START, TURN, DONE), code, final)
        self.rejected()

    def test_malformed_nonobject_and_type_invalid_records(self):
        for record in (b"{\n", b"[]\n", b"null\n", b"3\n", b"\n", b"{}\n", b'{"type":3}\n', b'{"type":""}\n', b'{"type":"new.event","x":NaN}\n', b'\xff\n'):
            with self.subTest(record=record), self.assertRaises(Rejected):
                validate_stream(capture(START, TURN) + record + capture(DONE), 0, "final")

    def test_unterminated_json_and_truncated_fragments(self):
        for raw in (capture(START, TURN, DONE)[:-1], capture(START, TURN) + b'{"type":', capture(START, TURN, DONE) + b" "):
            with self.subTest(raw=raw), self.assertRaises(Rejected):
                validate_stream(raw, 0, "final")

    def test_known_item_variants_without_universal_pairing(self):
        for kind in ("command_execution", "mcp_tool_call", "file_change", "agent_message"):
            with self.subTest(kind=kind):
                item = {"id": "i", "type": kind}
                records = [START, TURN, {"type": "item.started", "item": item}, {"type": "item.updated", "item": item}, {"type": "item.completed", "item": item}, DONE]
                self.assertEqual(records, validate_stream(capture(*records), 0, "final")[1])

    def test_known_items_require_active_turn(self):
        for kind in ("item.started", "item.updated", "item.completed"):
            event = {"type": kind, "item": {"type": "command_execution"}}
            with self.subTest(kind=kind):
                self.rejected(event, START, TURN, DONE)
                self.rejected(START, event, TURN, DONE)
                self.rejected(START, TURN, DONE, event)

    def test_invalid_item_shapes_and_unknown_semantics(self):
        for item in (None, [], "x", {}, {"type": 1}, {"type": "future_execution"}):
            with self.subTest(item=item):
                self.rejected(START, TURN, {"type": "item.completed", "item": item}, DONE)

    def test_unknown_controls_fail_compatibility(self):
        for event in ({"type": "turn.paused"}, {"type": "thread.updated"}, {"type": "item.failed"}, {"type": "new.event", "turn_id": "x"}):
            with self.subTest(event=event), self.assertRaisesRegex(Rejected, "Compatibility UNVERIFIED"):
                validate_stream(capture(START, TURN, event, DONE), 0, "final")

    def test_additive_records_and_fields_retained_in_order(self):
        extra = {"type": "new.event", "data": {"nested": 3}}
        records = [extra, dict(START, future=True), TURN, MESSAGE, DONE, extra]
        self.assertEqual(records, validate_stream(capture(*records), 0, "final")[1])
        self.rejected(START, extra, DONE)

    def test_incremental_and_replay_agree_and_report_unknown_offsets(self):
        from loop.event_stream import EventStream
        stream = EventStream(expected_thread=THREAD)
        records = [START, TURN, {"type": "new.event"}, MESSAGE, DONE]
        for record in records:
            self.assertEqual(record, stream.feed_line(capture(record)))
        self.assertEqual(validate_stream(capture(*records), 0, "final"), stream.finish(0, "final"))
        self.assertEqual([{"line": 3, "byte": len(capture(START, TURN)), "type": "new.event"}], stream.unknown_records)

    def test_failure_offsets_are_bounded_and_do_not_include_provider_text(self):
        private = "private-provider-text" * 1000
        with self.assertRaises(Rejected) as caught:
            validate_stream(capture(START, TURN) + capture({"type": "error", "message": private}), 0, "final")
        self.assertIn(f"line=3, byte={len(capture(START, TURN))}", str(caught.exception))
        self.assertNotIn("private-provider-text", str(caught.exception))
        self.assertLess(len(str(caught.exception)), 200)

    def test_invalid_incremental_stream_cannot_be_repaired(self):
        from loop.event_stream import EventStream
        stream = EventStream()
        stream.feed_line(capture(START))
        with self.assertRaises(Rejected):
            stream.feed_line(capture(DONE))
        with self.assertRaises(Rejected):
            stream.feed_line(capture(TURN))
        with self.assertRaises(Rejected):
            stream.finish(0, "final")


class AdapterCallerTests(unittest.TestCase):
    """Actual Adapter/Engine/Store boundary; local synthetic producer only."""

    def setUp(self):
        import tempfile
        import subprocess
        from loop.store import Store
        from loop.engine import Engine
        import test_controller
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.addCleanup(self.store.close)
        repo = self.root / "fixtures/repo"
        repo.mkdir(parents=True)
        (repo / "module.py").write_text("value=1\n")
        for command in (["git", "init", "-q", str(repo)], ["git", "-C", str(repo), "add", "."],
                        ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "-qm", "Baseline"]):
            subprocess.run(command, check=True, capture_output=True)
        self.engine = Engine(self.store, {"notes": str(self.root / "notes"), "authorized_repositories": [str(repo)], "codex_binary": "/bin/false"})
        from unittest.mock import patch
        with patch.object(self.engine, "instructions", return_value=[]):
            self.tid = self.engine.submit(test_controller.proposal(), repo, {"text": "Synthetic lifecycle control"}, "owner", "key")["task"]
        self.inputs = self.root / "synthetic-inputs"
        self.inputs.mkdir()

    def run_capture(self, raw, reason, resume=None, uncertain=False):
        from unittest.mock import patch
        import subprocess
        from loop.adapter import terminate
        runtime = self.root / "synthetic-runtime"
        # One write keeps invalid framed records and trailing fragments observable.
        code = "import os,time; from pathlib import Path; Path(" + repr(str(runtime / "final.txt")) + ").write_text('{}'); os.write(1," + repr(raw) + "); time.sleep(2)"
        def prepare(path, *_):
            path.mkdir(parents=True)
            (path / "config.toml").write_text("# Synthetic transport\n")
        def stop(process):
            terminate(process)
            if uncertain:
                raise Rejected("Synthetic unresolved termination")
        original_run = self.engine.adapter.run
        def routed(*args, **kwargs):
            kwargs.update(runtime=runtime, resume=resume)
            return original_run(*args, **kwargs)
        with patch("loop.adapter.prepare_runtime", side_effect=prepare), patch("loop.adapter.argv", return_value=[sys.executable, "-c", code]), patch("loop.adapter.terminate", side_effect=stop), patch.object(self.engine, "inputs", return_value=self.inputs), patch.object(self.engine, "project"), patch.object(self.engine.adapter, "run", side_effect=routed) as runs, patch.object(self.engine, "review") as review:
            with self.assertRaisesRegex(Rejected, reason):
                self.engine.run(self.tid)
            self.assertEqual(1, runs.call_count)
            review.assert_not_called()
        attempt = self.store.db.execute("SELECT * FROM attempts WHERE task=?", (self.tid,)).fetchone()
        result = json.loads(attempt["result"])
        self.assertEqual("DISPATCH_UNCERTAIN" if uncertain else "FAILED", attempt["status"])
        self.assertEqual(result, json.loads((Path(attempt["output"]) / "receipt.json").read_text()))
        self.assertEqual("BLOCKED", self.store.task(self.tid)["state"])
        self.assertEqual(0, result["tool_interactions"])
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='ROLE_COMPLETED'").fetchone()[0])
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='ROLE_FAILED'").fetchone()[0])
        with self.assertRaises(Rejected):
            self.engine.run(self.tid)
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0])
        return result, (Path(attempt["output"]) / "events.jsonl").read_bytes()

    def test_early_invalid_lifecycle_precedes_ack_and_tools(self):
        result, raw = self.run_capture(capture(START, COMMAND, MESSAGE, DONE) + b'{"partial":', "Item activity outside active turn")
        self.assertIn("line=2", result["failure"])
        self.assertIn("byte=" + str(len(capture(START))), result["failure"])
        self.assertIn(b'"command_execution"', raw)
        self.assertTrue(raw.endswith(b'{"partial":'))

    def test_wrong_explicit_resume_fails_before_identity_update(self):
        result, _ = self.run_capture(capture(START, TURN, MESSAGE, COMMAND, DONE), "resume UUID mismatch", resume=OTHER)
        self.assertIsNone(result["thread"])
        self.assertEqual(1, result["lifecycle"]["line"])

    def test_uncertain_termination_has_durable_receipt_and_no_retry(self):
        self.run_capture(capture(START, DONE), "termination is not reconciled", uncertain=True)

    def test_unknown_control_and_partial_fragments_retained(self):
        result, raw = self.run_capture(capture(START, TURN, {"type": "turn.future", "secret": "synthetic-secret"}, {"type": "new.event", "secret": "buffered-secret"}) + b'{"partial":', "Compatibility UNVERIFIED")
        self.assertIn(b'"turn.future"', raw)
        self.assertNotIn(b"synthetic-secret", raw)
        self.assertNotIn(b"buffered-secret", raw)
        self.assertLess(len(result["failure"]), 200)
        self.assertEqual("PARTIAL", result["coverage"])

    def test_nonobject_is_failed_not_attribute_error(self):
        self.run_capture(capture(START, TURN) + b'[]\n', "Expected object")

    def test_eof_fragment_cannot_complete_attempt(self):
        # Producer exits naturally after its sleep; even a complete JSON object
        # without LF is an invalid fragment, preserved without adding framing.
        _, raw = self.run_capture(capture(START, TURN, DONE)[:-1], "Incomplete final JSONL fragment")
        self.assertFalse(raw.endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
