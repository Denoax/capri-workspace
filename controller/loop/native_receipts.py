"""Durable observations of native frames, never completion or decision authority.

The backend reader is the sole writer. Receipt I/O takes no controller/SQLite
locks and calls no observers. The receive record precedes lifecycle validation;
the result refers to its sequence. A crash between them leaves an explicit gap.
"""
import json
import os
from pathlib import Path
import re
import threading

from .util import Rejected, digest, now, redact

PUBLIC_LABELS = frozenset(('thread','turn','answer','other',
    'commandExecution','mcpToolCall','webSearch','dynamicToolCall','agentMessage','reasoning',
    'contextCompaction','plan','fileChange','imageView','inProgress','completed','failed','interrupted',
    'turn/started','turn/completed','turn/moderationMetadata','item/started','item/completed',
    'thread/tokenUsage/updated','thread/status/changed','thread/settings/updated','model/rerouted'))


def public_label(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    identifier = re.fullmatch(r'(?:exec-)?[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}|(?:tool-|read-)\d+',value)
    if (len(value) <= 160 and (value in PUBLIC_LABELS or identifier)
            and redact(value) == value
            and not re.search(r'gh[pousr]_|github_pat_', value)):
        return value
    return {'sha256': digest(value.encode()), 'bytes': len(value.encode())}


class ReceivedReceipts:
    """Bounded fsynced JSONL; no raw text, commands, results or reasoning bodies."""
    def __init__(self, root, role, generation, *, max_bytes=32_000_000, max_frames=50000):
        self.path = Path(root)/'received-frames.jsonl'
        self.role, self.generation = role, generation
        self.max_bytes, self.max_frames = max_bytes, max_frames
        self.bytes = self.sequence = 0
        self.lock = threading.Lock()
        # Each backend generation owns a fresh private directory. Never append a
        # new writer to an existing, possibly incomplete generation receipt.
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        directory = os.open(self.path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _append(self, record):
        data = (json.dumps(record, sort_keys=True, ensure_ascii=False)+'\n').encode()
        if self.bytes + len(data) > self.max_bytes:
            raise Rejected('Native received-frame receipt byte budget exceeded')
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        try:
            written = 0
            while written < len(data):
                count = os.write(fd, data[written:])
                if count <= 0:
                    raise OSError('Incomplete received-frame receipt write')
                written += count
            os.fsync(fd)
        finally:
            os.close(fd)
        self.bytes += len(data)

    def received(self, raw, expected_thread):
        with self.lock:
            if self.sequence >= self.max_frames:
                raise Rejected('Native received-frame receipt count exceeded')
            self.sequence += 1
            envelope = {}
            try:
                value = json.loads(raw)
                if isinstance(value, dict):
                    envelope['method'] = public_label(value.get('method'))
                    envelope['rpc_id'] = public_label(value.get('id'))
                    params = value.get('params')
                    if isinstance(params, dict):
                        for key in ('threadId', 'turnId'):
                            envelope[key] = public_label(params.get(key))
                        for name in ('turn', 'item'):
                            obj = params.get(name)
                            if isinstance(obj, dict):
                                envelope[name] = {key: public_label(obj.get(key))
                                                  for key in ('id', 'type', 'status') if key in obj}
            except (ValueError, UnicodeError):
                envelope['malformed'] = True
            self._append(dict(schema=1, sequence=self.sequence, phase='RECEIVED', time=now(),
                              role=self.role, generation=self.generation,
                              expected_thread=public_label(expected_thread),
                              frame_sha256=digest(raw), frame_bytes=len(raw), envelope=envelope))
            return self.sequence

    def result(self, sequence, outcome, reason=None):
        if outcome not in ('VALIDATED', 'REJECTED'):
            raise Rejected('Unknown received-frame validation outcome')
        with self.lock:
            # Errors can originate in an untrusted backend or a failing sink.
            # Preserve exact diagnostics by hash, and expose only known causes.
            codes = {
                'Native turn exceeded exposed tool budget': 'EXPOSED_TOOL_BUDGET',
                'Combined native stage exposed-tool budget exceeded': 'STAGE_TOOL_BUDGET',
                'Wrong native thread': 'WRONG_THREAD',
                'Wrong or missing native turn': 'WRONG_TURN',
                'Duplicate item start': 'DUPLICATE_ITEM',
                'Unstarted/duplicate/conflicting item completion': 'ITEM_ORDER',
                'Oversized/incomplete native frame': 'FRAME_SIZE',
                'Malformed native JSON': 'MALFORMED_JSON',
            }
            self._append(dict(schema=1, sequence=sequence, phase=outcome, time=now(),
                              reason=codes.get(reason, 'OTHER_REJECTION') if reason else None,
                              reason_sha256=digest(reason.encode()) if reason else None))
