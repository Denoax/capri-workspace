"""Bounded exec JSONL profile; not an SDK or app-server event grammar."""

import json
import uuid

from .util import Rejected


class EventStream:
    """One instance per invocation, including each explicit-ID resume.

    feed_line consumes a complete LF-framed byte record before callers act on it.
    Capture retention/redaction belongs to the adapter, not this parser.
    """

    ITEM_TYPES = frozenset(("agent_message", "command_execution", "file_change", "mcp_tool_call"))

    def __init__(self, expected_thread=None):
        self.state = "NEW"
        self.thread = None
        self.events = []
        self.unknown_records = []
        self.line = 0
        self.offset = 0
        self.failure = None
        self.expected_thread = self._uuid(expected_thread) if expected_thread is not None else None

    @staticmethod
    def _uuid(value):
        if not isinstance(value, str):
            raise Rejected("Thread identity must be a UUID string")
        try:
            parsed = uuid.UUID(value)
        except ValueError as ex:
            raise Rejected("Invalid thread UUID") from ex
        if str(parsed) != value.lower():
            raise Rejected("Thread UUID must use hyphenated form")
        return parsed

    def _reject(self, reason):
        # Never interpolate provider content, tool output or private reasoning.
        self.failure = f"{reason}; line={self.line}, byte={self.offset}, state={self.state}"
        self.state = "FAILED"
        raise Rejected(self.failure)

    def feed_line(self, raw):
        if self.failure:
            raise Rejected(self.failure)
        self.line += 1
        if not raw.endswith(b"\n"):
            self._reject("Incomplete final JSONL fragment")
        try:
            event = json.loads(raw.decode("utf-8"), parse_constant=self._invalid_constant)
        except (ValueError, UnicodeDecodeError):
            self._reject("Malformed JSONL record")
        if not isinstance(event, dict) or not isinstance(event.get("type"), str) or not event["type"]:
            self._reject("Expected object with nonempty string event type")
        self.events.append(event)
        self._observe(event)
        self.offset += len(raw)
        return event

    @staticmethod
    def _invalid_constant(value):
        raise ValueError("Non-JSON numeric constant")

    def _observe(self, event):
        kind = event["type"]
        if kind in ("error", "turn.failed"):
            self._reject("Explicit producer failure")
        if kind == "thread.started":
            if self.state != "NEW":
                self._reject("Duplicate or out-of-order thread start")
            try:
                thread_uuid = self._uuid(event.get("thread_id"))
            except Rejected:
                self._reject("Invalid thread UUID")
            if self.expected_thread is not None and thread_uuid != self.expected_thread:
                self._reject("Explicit resume UUID mismatch")
            self.thread = event["thread_id"]
            self.state = "THREAD"
        elif kind == "turn.started":
            if self.state != "THREAD":
                self._reject("Turn start requires exactly one thread start")
            self.state = "ACTIVE"
        elif kind == "turn.completed":
            if self.state != "ACTIVE":
                self._reject("Turn completion requires one active turn")
            self.state = "COMPLETED"
        elif kind in ("item.started", "item.updated", "item.completed"):
            item = event.get("item")
            if not isinstance(item, dict) or not isinstance(item.get("type"), str):
                self._reject("Invalid item shape")
            if item["type"] == "error":
                self._reject("Explicit item failure")
            if item["type"] not in self.ITEM_TYPES:
                self._reject("Compatibility UNVERIFIED: unclassified item semantics")
            if self.state != "ACTIVE":
                self._reject("Item activity outside active turn")
            # Observed agent-message completions need no matching item start.
        elif kind.split(".", 1)[0] in ("thread", "turn", "item") or any(
            key in event for key in ("thread_id", "turn_id", "item")
        ):
            self._reject("Compatibility UNVERIFIED: unclassified control semantics")
        else:
            # Additive observations cannot move or repair lifecycle state.
            self.unknown_records.append({"line": self.line, "byte": self.offset, "type": kind})

    def finish(self, exit_code, final):
        if self.failure:
            raise Rejected(self.failure)
        if self.state != "COMPLETED" or exit_code != 0 or final is None:
            self._reject("Transport incomplete/failed")
        return self.thread, self.events


def validate_stream(raw, exit_code, final, expected_thread=None):
    stream = EventStream(expected_thread)
    # Split only on LF: other Unicode/ASCII separators are not JSONL frames.
    lines = raw.split(b"\n")
    for line in lines[:-1]:
        stream.feed_line(line + b"\n")
    if lines[-1]:
        stream.feed_line(lines[-1])
    return stream.finish(exit_code, final)
