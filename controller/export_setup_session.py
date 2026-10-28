#!/usr/bin/env python3
"""Pinned, read-only export of this setup's visible local records, never hidden reasoning.

This is a version-dependent local exporter, not a provider replay API or IDE integration.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import uuid

from loop.util import Rejected, atomic, canonical, digest, now, redact, write_json

SUPPORTED = {"0.162.0-alpha.17.2"}
TOOL_TYPES = {"function_call", "function_call_output", "custom_tool_call", "custom_tool_call_output", "web_search_call"}


def export(source, thread, destination):
    uuid.UUID(thread)
    raw = Path(source).read_bytes()  # One point-in-time prefix; the source is never written.
    complete = raw[:raw.rfind(b"\n") + 1]
    events = [json.loads(line) for line in complete.splitlines()]
    metadata = [e["payload"] for e in events if e.get("type") == "session_meta"]
    if len(metadata) != 1 or metadata[0].get("id") != thread or metadata[0].get("cli_version") not in SUPPORTED:
        raise Rejected("Unknown local session schema or mismatched source identity")
    visible, excluded = [], Counter()
    for offset, event in enumerate(events):
        typ, payload = event.get("type"), event.get("payload", {})
        if typ == "response_item" and payload.get("type") == "message" and payload.get("role") in ("user", "assistant"):
            item = {k: payload[k] for k in ("type", "id", "role", "phase", "content") if k in payload}
        elif typ == "response_item" and payload.get("type") in TOOL_TYPES:
            item = {k: v for k, v in payload.items() if k != "internal_chat_message_metadata_passthrough"}
        elif typ == "event_msg" and payload.get("type") in ("user_message", "agent_message", "task_started", "task_complete", "patch_apply_end", "web_search_end"):
            item = payload
        else:
            excluded[typ + ":" + str(payload.get("type", ""))] += 1
            continue
        visible.append({"source_record": offset, "timestamp": event.get("timestamp"), "type": typ, "payload": item})
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    capture = b"".join(redact(canonical(e).decode()).encode() + b"\n" for e in visible)
    atomic(destination / "visible.jsonl", capture)
    report = {"exporter_version": 1, "time": now(), "thread": thread, "source": str(source), "source_cli_version": metadata[0]["cli_version"],
              "originator": metadata[0].get("originator"), "source_prefix_bytes": len(complete), "source_prefix_sha256": digest(complete),
              "visible_records": len(visible), "visible_sha256": digest(capture), "excluded_record_counts": dict(excluded), "trailing_fragment_bytes": len(raw) - len(complete),
              "coverage": "POINT_IN_TIME_VISIBLE_LOCAL_EXPORT", "gaps": ["Private reasoning, privileged instructions, opaque world state and unavailable provider internals excluded", "Active turn/final output after snapshot is not yet captured; refresh at the final checkpoint", "No public replay/sequence guarantees; pinned local schema only"]}
    write_json(destination / "export-receipt.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--thread", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(export(a.source, a.thread, a.output), indent=2))
