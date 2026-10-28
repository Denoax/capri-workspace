"""Synthetic protocol/gateway controls; these do not establish live qualification."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.native_protocol import Lifecycle, decode
from loop.native import Backend, Binding, deny_admission
from loop.settings import Settings
from loop.util import Rejected


def event(method, **kw):
    return dict(method=method, params=dict(threadId='thread', **kw))


def start(life):
    life.feed(event('turn/started', turn=dict(id='turn', status='inProgress')))


def item(life, iid, kind, **kw):
    value = dict(id=iid, type=kind, **kw)
    life.feed(event('item/started', turnId='turn', item=value))
    life.feed(event('item/completed', turnId='turn', item=value))


class NativeTests(unittest.TestCase):
    def test_complete_requires_output_and_independent_check(self):
        life = Lifecycle('thread', 'hash')
        start(life)
        item(life, 'ack', 'agentMessage', text='ACK:hash', phase='commentary')
        item(life, 'tool', 'commandExecution')
        item(life, 'answer', 'agentMessage', text='result', phase='final_answer')
        life.feed(event('turn/completed', turn=dict(id='turn', status='completed')))
        self.assertEqual(life.finish(lambda x: x == 'result', lambda: True), 'result')
        with self.assertRaises(Rejected):
            life.feed(event('turn/completed', turn=dict(id='turn', status='completed')))
        with self.assertRaises(Rejected):
            life.finish(lambda _: True, lambda: True)

    def test_wrong_thread_turn_terminal_and_order_latch(self):
        for value in [event('turn/completed', turn=dict(id='turn', status='completed')),
                      dict(method='turn/started', params=dict(threadId='other', turn=dict(id='turn'))),
                      event('item/completed', turnId='other', item=dict(id='a', type='agentMessage'))]:
            life = Lifecycle('thread')
            with self.assertRaises(Rejected):
                life.feed(value)
            self.assertIsNotNone(life.failure)
        for status in ('failed', 'interrupted', None):
            life = Lifecycle('thread'); start(life)
            with self.assertRaises(Rejected):
                life.feed(event('turn/completed', turn=dict(id='turn', status=status)))

    def test_tool_before_ack_and_thirteenth_tool_are_rejected(self):
        life = Lifecycle('thread', 'hash'); start(life)
        with self.assertRaises(Rejected):
            item(life, 'tool', 'commandExecution')
        life = Lifecycle('thread'); start(life)
        for n in range(12):
            item(life, str(n), 'mcpToolCall')
        with self.assertRaises(Rejected):
            item(life, '13', 'webSearch')

    def test_deadline_and_bad_json(self):
        now = [0]
        life = Lifecycle('thread', clock=lambda: now[0]); start(life)
        now[0] = 240
        with self.assertRaises(Rejected):
            life.budget()
        for raw in ('[]', '{', '{"id":1,"id":2}', '{"x":NaN}'):
            with self.assertRaises(Rejected):
                decode(raw)

    def test_gateway_denies_mutations_without_forwarding(self):
        backend = Backend.__new__(Backend)
        backend.thread, backend.role, backend.generation = 'thread', 'doer', 0
        backend.observer = None
        calls = []
        backend.rpc = lambda *x: calls.append(x)
        for method in ('thread/shellCommand', 'turn/start', 'turn/steer', 'config/value/write',
                       'fs/writeFile', 'command/exec', 'thread/compact/start', 'unknown'):
            with self.assertRaises(Rejected):
                backend.frontend(dict(method=method, params=dict(threadId='thread')))
        self.assertEqual(calls, [])
        with self.assertRaises(Rejected):
            backend.frontend(dict(method='thread/read', params=dict(threadId='other')))

    def test_empty_attach_reuses_start_and_never_creates_thread(self):
        b = Backend.__new__(Backend)
        b.thread, b.empty, b.started_response = 'thread', True, {'thread': {'id': 'thread'}}
        self.assertEqual(b.frontend({'method': 'thread/start'}), b.started_response)
        self.assertEqual(b.frontend({'method': 'thread/resume', 'params': {'threadId': 'thread'}}), b.started_response)
        with self.assertRaises(Rejected):
            b.frontend({'method': 'thread/resume', 'params': {'threadId': 'other'}})
        b.empty = False
        with self.assertRaises(Rejected):
            b.frontend({'method': 'thread/start'})

    def test_default_admission_is_not_boolean_or_uid_authorization(self):
        with self.assertRaises(Rejected):
            with deny_admission(None, 'controller', []):
                self.fail('denial allowed work')

    def test_settings_preserve_guards_and_exact_model(self):
        s = Settings('codex', '/operator/auth', '/private/state', efforts=dict(thinker='high', doer='medium', reviewer='high'))
        for role in ('thinker', 'doer', 'reviewer'):
            text = s.config(role)
            self.assertIn('approval_policy = "never"', text)
            self.assertIn('web_search = "disabled"', text)
            self.assertIn('"/codex-home" = "deny"', text)
            self.assertIn('extends = ":read-only"', text)
        self.assertIn('extends = ":workspace"', s.config('doer', 'write'))
        with self.assertRaises(Rejected):
            Settings('codex', '/auth', '/state', model='other')
        with self.assertRaises(Rejected):
            s.config('reviewer', 'write')


if __name__ == '__main__':
    unittest.main()

class StoreAdmissionTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from loop.store import Store
        from loop.native import StoreAdmission
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        t = self.store.create('native-test', {'source': {}, 'requirements': []}, 'native-owner')
        self.store.transition(t['id'], 'READY', 'DOER_RUNNING')
        self.tid = t['id']
        class Engine:
            def __init__(inner, store): inner.store = store
            def verify_inputs(inner, task):
                if task['packet'] != {'source': {}, 'requirements': []}:
                    raise Rejected('Modified packet')
        self.admission = StoreAdmission(Engine(self.store), self.tid, t['generation'], lambda *_: True)
        self.binding = Binding('doer', 'native-thread', 7, t['content_hash'], 'source', t['revision'], 'lease', 'read')
        self.admission.expected_binding = self.binding
        self.admission.lease = 'lease'

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_role_generation_is_distinct_from_task_generation(self):
        with self.admission(self.binding, 'controller', []):
            self.assertEqual(self.binding.generation, 7)
        self.assertEqual(self.store.task(self.tid)['generation'], 1)

    def test_unknown_context_and_unattested_input_fail_closed(self):
        self.admission.context_policy = None
        with self.assertRaises(Rejected):
            with self.admission(self.binding, 'controller', []): self.fail('unknown admitted')
        with self.assertRaises(Rejected):
            with self.admission(self.binding, 'native-client-unattested', []): self.fail('unattested admitted')

    def test_questions_generation_and_human_gate_block(self):
        self.store.ask_question('native-owner', 'native-test', 1, 'Synthetic pending question')
        with self.assertRaises(Rejected):
            with self.admission(self.binding, 'controller', []): self.fail('question bypass')

    def test_second_writer_is_rejected_at_real_store_lock(self):
        from loop.store import Store
        other = Store(self.temp.name)
        try:
            with other.lock('native-writer'):
                with self.assertRaises(Rejected):
                    with self.admission(self.binding, 'controller', []): self.fail('second writer')
        finally:
            other.close()

    def test_changed_gate_or_generation_is_rejected(self):
        self.store.db.execute("UPDATE tasks SET generation=generation+1 WHERE id=?", (self.tid,))
        with self.assertRaises(Rejected):
            with self.admission(self.binding, 'controller', []): self.fail('stale generation')
        self.store.db.execute("UPDATE tasks SET generation=generation-1,state='AWAITING_HUMAN' WHERE id=?", (self.tid,))
        with self.assertRaises(Rejected):
            with self.admission(self.binding, 'controller', []): self.fail('human gate bypass')


class CompatibilityFixTests(unittest.TestCase):
    def test_required_tui_reads_and_full_unattested_input_receipt(self):
        b = Backend.__new__(Backend)
        b.thread, b.role, b.generation = 'thread', 'doer', 0
        calls, receipts = [], []
        b.rpc = lambda *args: calls.append(args) or {}
        b.observer = lambda *args: receipts.append(args[-1])
        for method in ('account/read', 'config/read', 'hooks/list', 'skills/list',
                       'account/bedrock/checkGovCloudRequirements', 'account/rateLimits/read'):
            b.frontend(dict(method=method))
        self.assertEqual(len(calls), 6)
        payload = {'threadId': 'thread', 'input': [{'type': 'text', 'text': 'Synthetic correction'}]}
        with self.assertRaises(Rejected):
            b.frontend(dict(method='turn/start', params=payload))
        self.assertEqual(receipts[0]['params']['payload'], payload)
        self.assertEqual(receipts[0]['params']['provenance'], 'native-client-unattested')

    def test_empty_attach_does_not_resume(self):
        from loop.native import NativeSlots
        from types import SimpleNamespace
        slots = NativeSlots.__new__(NativeSlots)
        slots.settings = SimpleNamespace(executable=lambda: '/usr/bin/codex')
        slots.root = Path('/private/state')
        slots.backends = {'doer': SimpleNamespace(thread='thread', empty=True)}
        command = slots.attach('doer')
        self.assertNotIn('resume', command)
        self.assertIn('--remote', command)
        slots.backends['doer'].empty = False
        self.assertIn('resume', slots.attach('doer'))


class ObserverReplacementTests(unittest.TestCase):
    def test_remount_metadata_does_not_rebind_or_admit_old_context(self):
        import tempfile
        import threading
        from dataclasses import replace
        from loop.native import NativeAdapter
        from loop.context import ContextState, UsageIdentity
        with tempfile.TemporaryDirectory() as root:
            adapter = NativeAdapter.__new__(NativeAdapter)
            adapter.capture, adapter.capture_lock = None, threading.Lock()
            uid = UsageIdentity('doer', 'thread', 'turn', 'task', 1, 'gpt-6.1-sol',
                                2, 1, 'server', 'process', '0.163.0', 'synthetic')
            state = ContextState(Path(root)/'context.json', uid)
            state.rehydrating = True
            state.persist()
            before = state.path.read_bytes()
            adapter.context_states = {'doer': state}
            adapter.context_order = {}
            adapter.planned_compactions = set()
            # thread/start/resume emits these before NativeSlots publishes gen 3.
            for method in ('thread/started', 'thread/status/changed', 'account/updated'):
                adapter.observe('doer', 3, event(method, status={'type': 'idle'}))
            self.assertEqual(state.path.read_bytes(), before)
            self.assertEqual(state.identity, uid)
            self.assertEqual(state.decision()['action'], 'HOLD')
            sensitive = [event('thread/tokenUsage/updated'),
                         event('turn/started', turn={'id': 'new'}),
                         event('turn/completed', turn={'id': 'turn', 'status': 'completed'})]
            for method in ('item/started', 'item/completed'):
                sensitive.append(event(method, turnId='turn',
                    item={'id': 'compact', 'type': 'contextCompaction'}))
            # Neither pending replacement nor retired generations mutate state.
            for generation in (1, 3):
                for value in sensitive:
                    with self.assertRaisesRegex(Rejected, 'generation'):
                        adapter.observe('doer', generation, value)
            self.assertEqual(state.path.read_bytes(), before)
            self.assertEqual(adapter.context_order, {})
            # Publication/reconciliation of the new identity still permits its
            # admitted lifecycle, while the old generation remains fenced.
            state.identity = replace(uid, role_generation=3)
            adapter.observe('doer', 3, event('turn/started', turn={'id': 'new'}))
            self.assertEqual(state.identity.turn, 'new')
            with self.assertRaisesRegex(Rejected, 'generation'):
                adapter.observe('doer', 2, sensitive[0])
            self.assertEqual(state.decision()['action'], 'HOLD')
