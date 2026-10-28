import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from loop.native import Backend
from loop.native_compaction_timing import CompactionTiming
from loop.native_protocol import CompactionLifecycle
from loop.util import Rejected


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_rpc_send_and_ack_bind_actual_id_without_payload(self):
        trace=CompactionTiming(self.root,'doer',7,'synthetic-thread',60)
        backend=Backend.__new__(Backend);backend.lock=threading.RLock();backend.error=None;backend.sequence=41;backend.pending={};backend.compaction_timing=trace
        backend._send=lambda value:backend.pending[value['id']].set_result({'result':{}})
        self.assertEqual(backend.rpc('thread/compact/start',{'threadId':'synthetic-thread'}),{})
        rows=[json.loads(line) for line in trace.path.read_text().splitlines()]
        self.assertEqual([r['phase'] for r in rows],['BEGIN','RPC_SEND_INTENT','RPC_SENT','RPC_ACKNOWLEDGED'])
        self.assertEqual([r['rpc_id'] for r in rows[1:]],[42,42,42])
        self.assertNotIn('params',trace.path.read_text());self.assertEqual(trace.path.stat().st_mode&0o777,0o600)

    def test_failed_trace_never_labels_late_completion_as_success(self):
        tick=[0.0];trace=CompactionTiming(self.root,'doer',7,'thread',60,clock=lambda:tick[0])
        tick[0]=60;trace.mark('FAILED',error_class='Rejected');trace.mark('LIFECYCLE_RETURNED')
        rows=[json.loads(line) for line in trace.path.read_text().splitlines()]
        self.assertEqual(rows[-1]['phase'],'LATE_AFTER_FAILURE')
        self.assertNotIn('LIFECYCLE_RETURNED',[r['phase'] for r in rows])

    def test_existing_deadline_latch_rejects_late_lifecycle(self):
        tick=[0.0];life=CompactionLifecycle('thread',max_seconds=60,clock=lambda:tick[0])
        tick[0]=60
        with self.assertRaises(Rejected):life.budget()
        with self.assertRaises(Rejected):life.feed(dict(method='turn/completed',params=dict(threadId='thread',turn=dict(id='late',status='completed'))))

    def test_diagnostic_failure_still_stops_owned_backend(self):
        b=Backend.__new__(Backend);b.phase='read';b.lock=threading.RLock();b.active=None;b.error=None;b.root=self.root;b.role='doer';b.generation=7;b.thread='thread';b.close=Mock()
        b.rpc=Mock(side_effect=Rejected('synthetic incomplete transport'))
        original=CompactionTiming.mark
        def fail_on_failed(trace,phase,**kwargs):
            if phase=='FAILED':raise OSError('synthetic sink failure')
            return original(trace,phase,**kwargs)
        with patch.object(CompactionTiming,'mark',fail_on_failed),self.assertRaises(OSError):b.compact()
        b.close.assert_called_once();self.assertIsNone(b.active)

    def test_markers_are_bounded_and_reject_unapproved_fields(self):
        trace=CompactionTiming(self.root,'doer',7,'thread',60)
        with self.assertRaises(Rejected):trace.mark('PRIVATE_PROMPT')
        with self.assertRaises(Rejected):trace.mark('FAILED',error_class='message with private text')
        for _ in range(31):trace.mark('RPC_SENT',rpc_id=1)
        before=trace.path.read_bytes()
        with self.assertRaises(Rejected):trace.mark('RPC_SENT',rpc_id=1)
        self.assertEqual(trace.path.read_bytes(),before)
