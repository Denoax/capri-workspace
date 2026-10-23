"""Synthetic wire-level regressions for resume replay; no model turn is dispatched."""
from io import BytesIO
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from loop.native import Backend, NativeAdapter
from loop.native_protocol import Lifecycle
from loop.context import ContextState
from test_context import binding, usage

class IdleUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.adapter=NativeAdapter.__new__(NativeAdapter)
        self.adapter.capture=None;self.adapter.capture_lock=threading.Lock()
        self.state=ContextState(self.root/'context.json',binding())
        self.state.rehydrating=True;self.state.persist()
        self.adapter.context_states={'doer':self.state};self.adapter.context_order={}
        self.adapter.planned_compactions=set()
        self.observed=[]
    def read(self,events,generation=3,active=None,thread='thread',prior='thread',budget=0):
        b=Backend.__new__(Backend)
        b.root=self.root;b.thread=thread;b.prior=prior;b.role='doer';b.generation=generation
        b.lock=threading.RLock();b.active=active;b.turn_bytes=0;b.idle_usage_bytes=budget
        b.error=None;b.pending={};b.clients={queue.Queue()}
        b.proc=SimpleNamespace(stdout=BytesIO(b''.join((json.dumps(v)+'\n').encode() for v in events)))
        def observe(role,gen,value):
            self.observed.append(value);self.adapter.observe(role,gen,value)
        b.observer=observe;b._reader();return b
    def test_resume_usage_before_publication_is_retained_without_rebinding(self):
        before=self.state.path.read_bytes()
        b=self.read([usage()],thread=None)
        self.assertEqual(b.error,'Backend disconnected; not task completion')
        saved=json.loads((self.root/'idle-usage.jsonl').read_text())
        self.assertEqual(saved['message'],usage())
        self.assertEqual(saved['generation'],3)
        self.assertEqual(saved['provenance'],'IDLE_HISTORY_NOT_FRESH_USAGE')
        self.assertEqual(self.observed[0]['method'],'native/idleUsageReceipt')
        self.assertEqual(self.state.path.read_bytes(),before)
        self.assertEqual(self.state.identity.role_generation,2)
        self.assertEqual(self.state.decision()['action'],'HOLD')
    def test_same_generation_idle_history_cannot_supply_fresh_reading(self):
        self.read([usage()],generation=2)
        self.assertIsNone(self.state.reading)
        self.assertEqual(self.adapter.context_order,{})
        self.assertEqual(self.state.decision()['action'],'HOLD')
    def test_idle_wrong_thread_and_missing_turn_are_rejected(self):
        for changes in ({'threadId':'other'},{'turnId':''}):
            v=usage();v['params'].update(changes)
            b=self.read([v])
            self.assertEqual(b.error,'Idle usage replay thread/turn mismatch')
        self.assertFalse((self.root/'idle-usage.jsonl').exists())
    def test_idle_usage_without_known_resume_thread_is_rejected(self):
        b=self.read([usage()],thread=None,prior=None)
        self.assertEqual(b.error,'Idle usage replay thread/turn mismatch')
    def test_active_turn_usage_still_updates_identity_bound_ledger(self):
        self.state.rehydrating=False
        life=Lifecycle('thread');life.feed(dict(method='turn/started',params=dict(threadId='thread',turn=dict(id='turn'))))
        b=self.read([usage()],generation=2,active=life)
        self.assertEqual(b.error,'Backend disconnected; not task completion')
        self.assertEqual(self.state.reading['latest_request']['totalTokens'],20000)
        self.assertEqual(self.state.reading['active_occupancy'],'UNKNOWN')
        self.assertFalse((self.root/'idle-usage.jsonl').exists())
    def test_replay_during_new_active_turn_remains_rejected(self):
        life=Lifecycle('thread');life.feed(dict(method='turn/started',params=dict(threadId='thread',turn=dict(id='new-turn'))))
        b=self.read([usage()],generation=2,active=life)
        self.assertEqual(b.error,'Wrong or missing native turn')
        self.assertFalse((self.root/'idle-usage.jsonl').exists())
    def test_idle_receipts_do_not_admit_unsolicited_turns_or_unbounded_capture(self):
        b=self.read([dict(method='turn/started',params=dict(threadId='thread',turn=dict(id='turn')))])
        self.assertEqual(b.error,'Unadmitted backend turn')
        b=self.read([usage()],budget=32_000_000)
        self.assertEqual(b.error,'Idle usage receipt budget exceeded')
        self.assertFalse((self.root/'idle-usage.jsonl').exists())
