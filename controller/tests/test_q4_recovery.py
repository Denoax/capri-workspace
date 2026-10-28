"""Q4 synthetic temporary-state evidence; no call here proves human origin."""
import contextlib
import json
import io
import os
import threading
import sys
import uuid
import subprocess
from unittest.mock import patch

import test_controller
from loop.cli import capture_human_answer, prepare_recontract, thinker_cycle
from loop.engine import Engine
from loop.adapter import Adapter, process_identity
from loop.service import capability, handle, recover
from loop.store import Store
from loop.util import NeedsInput, Rejected


class RecoveryTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp()
        self.repo = self.root / 'fixtures/repo'
        self.repo.mkdir(parents=True)
        (self.repo / 'module.py').write_text('value=1\n')
        for argv in (['git', 'init', '-q', str(self.repo)], ['git', '-C', str(self.repo), 'add', '.'], ['git', '-C', str(self.repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'Baseline']):
            subprocess.run(argv, check=True, capture_output=True)
        self.config['authorized_repositories'] = [str(self.repo)]
        self.token = capability(self.store, 'owner', {'repo': str(self.repo), 'request': {'text': 'Exact synthetic request'}, 'key': 'key'})
        self.engine = Engine(self.store, self.config)

    def call(self, operation, arguments):
        return handle(self.store, self.config, {'capability': self.token, 'operation': operation, 'arguments': arguments})['result']

    def freeze(self):
        return self.call('submit_task', {'proposal': test_controller.proposal()})['task']

    def ask(self, text='Synthetic post-freeze question?'):
        return self.call('ask_human', {'question': text})

    def answer(self, q, text='Synthetic exact answer', source_ref='SYNTHETIC_Q4_NOT_HUMAN', **changes):
        args = {k: q[k] for k in ('question_id', 'owner', 'scope_key', 'task_id', 'revision', 'packet_hash')}
        args.update(text=text, origin='FOREGROUND_HUMAN_STDIN', source_ref=source_ref)
        args.update(changes)
        return capture_human_answer(self.store, **args)

    def reopen(self):
        self.store.close()
        self.store = Store(self.root)
        recover(self.store)
        self.engine = Engine(self.store, self.config)

    def test_actual_entry_points_reach_recontract_without_manual_state_hop(self):
        tid = self.freeze()
        packet = self.root / 'artifacts' / tid / 'packet.json'
        original = packet.read_bytes()
        q = self.ask()
        with self.assertRaises(Rejected):
            self.engine.run(tid)
        self.reopen()
        answered = self.answer(q, text='SYNTHETIC: preserve Return "Untitled" exactly')
        with self.assertRaises(Rejected):
            self.engine.run(tid)
        try:
            repo, text, lineage = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        except Rejected as ex:
            self.fail('Q4 actual entry-point recovery is unreachable: ' + str(ex))
        self.assertEqual('SUPERSEDED', self.store.task(tid)['state'])
        self.assertEqual(original, packet.read_bytes())
        self.assertEqual(2, lineage['revision'])
        self.assertEqual(answered['answer'], lineage['human_answers'][0]['answer'])
        result = self.engine.submit(test_controller.proposal(), repo, {'text': text, 'lineage': lineage}, lineage.get('successor_owner', 'successor-owner'), 'successor-key')
        successor = self.store.task(result['task'])
        self.assertEqual('READY', successor['state'])
        self.assertEqual(2, successor['revision'])
        self.assertEqual(answered['answer'], successor['packet']['request']['human_answers'][0]['answer'])
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0])

    def held(self):
        tid = self.freeze()
        q = self.ask()
        self.answer(q)
        return tid, q

    def events(self, tid, kind):
        return [json.loads(r['data']) for r in self.store.db.execute('SELECT data FROM events WHERE task=? AND kind=? ORDER BY seq', (tid, kind))]

    def assert_no_writer(self):
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0])

    def test_question_commits_one_durable_hold_and_dispatch_outbox_survives_restarts(self):
        tid = self.freeze()
        q = self.ask()
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        self.assertEqual('HELD', self.store.db.execute("SELECT status FROM outbox WHERE task=? AND kind='DISPATCH'", (tid,)).fetchone()[0])
        for _ in range(3):
            self.reopen()
            self.assertEqual('NEEDS_INPUT', self.call('request_status', {'task': tid})['state'])
            self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
            self.assertEqual([], self.store.db.execute("SELECT id FROM tasks WHERE state='READY'").fetchall())
            with self.assertRaises(NeedsInput):
                self.engine.run(tid)
        self.assertEqual(q['question_id'], self.ask()['question_id'])
        self.assertEqual(1, len(self.events(tid, 'QUESTION')))
        self.assertEqual(1, len(self.events(tid, 'STATE')))
        self.assertEqual([], self.events(tid, 'SCHEDULER_ERROR'))
        self.assert_no_writer()

    def test_answer_before_scheduler_observation_never_releases_frozen_revision(self):
        tid, q = self.held()
        self.reopen()
        self.assertEqual('ANSWERED', self.store.question(q['question_id'])['status'])
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        with self.assertRaises(NeedsInput):
            self.engine.run(tid)
        self.assert_no_writer()

    def legacy_ready(self, answered=False):
        # Synthetic emulation of the reviewed v2 code path, in temporary state only.
        tid = self.freeze()
        with patch.object(self.store, '_hold_ready_in_transaction', return_value=None):
            q = self.ask()
            if answered:
                self.answer(q)
        self.assertEqual('READY', self.store.task(tid)['state'])
        return tid, q

    def test_reopen_repairs_legacy_unanswered_ready_without_an_error_loop(self):
        tid, q = self.legacy_ready()
        self.reopen()
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        with self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic cannot answer implicitly')
        self.answer(q)
        _, _, lineage = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual(2, lineage['revision'])
        self.assertEqual(1, len(self.events(tid, 'HUMAN_RECONTRACT')))
        self.assert_no_writer()

    def test_reopen_repairs_legacy_answered_ready_and_retries_do_not_repeat_hold(self):
        tid, _ = self.legacy_ready(answered=True)
        for _ in range(3):
            self.reopen()
            self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        self.assertEqual(1, len(self.events(tid, 'STATE')))
        prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assert_no_writer()

    def test_unanswered_and_wrong_bound_or_model_answers_cannot_release_hold(self):
        tid = self.freeze()
        q = self.ask()
        for field, value in {'owner': 'other', 'scope_key': 'other', 'task_id': 'other', 'revision': 9, 'packet_hash': 'wrong', 'origin': 'CONTROLLER_DATA_NOT_HUMAN'}.items():
            with self.subTest(field=field), self.assertRaises(Rejected):
                self.answer(q, **{field: value})
        with self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic instruction is not a bound answer')
        self.assertEqual('PENDING', self.store.question(q['question_id'])['status'])
        self.assertEqual([], self.store.human_answers('owner'))
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        self.assert_no_writer()

    def insert_attempt(self, tid, status, pid=None):
        self.store.db.execute('INSERT INTO attempts(id,task,generation,role,status,pid,start_identity,output) VALUES(?,?,1,?,?,?,?,?)', (str(uuid.uuid4()), tid, 'doer', status, pid, process_identity(pid) if pid else None, 'SYNTHETIC_Q4_ATTEMPT'))

    def test_live_owned_or_uncertain_old_attempts_require_reconciliation(self):
        tid, _ = self.held()
        for status, pid in [('RUNNING', os.getpid()), ('DISPATCH_UNCERTAIN', None), ('SPAWN_INTENT', None)]:
            with self.subTest(status=status):
                self.insert_attempt(tid, status, pid)
                with self.assertRaises(Rejected):
                    prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
                self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
                self.assertEqual([], self.events(tid, 'HUMAN_RECONTRACT'))
                self.store.db.execute('DELETE FROM attempts WHERE task=?', (tid,))

    def during_commit(self, action):
        original = self.store.transaction
        calls = 0
        @contextlib.contextmanager
        def interleaved():
            nonlocal calls
            calls += 1
            if calls == 2:  # first transaction only normalizes a legacy READY hold
                with patch.object(self.store, 'transaction', original):
                    action()
            with original():
                yield
        return patch.object(self.store, 'transaction', interleaved)

    def test_question_during_recontract_preserves_both_questions_and_held_task(self):
        tid, _ = self.held()
        with self.during_commit(lambda: self.ask('Synthetic late question?')), self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual(['ANSWERED', 'PENDING'], [q['status'] for q in self.store.questions('owner')])
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        self.assertEqual([], self.events(tid, 'HUMAN_RECONTRACT'))

    def test_answer_correction_during_recontract_is_not_lost(self):
        tid, q = self.held()
        with self.during_commit(lambda: self.answer(q, text='Synthetic later exact answer', source_ref='SYNTHETIC_Q4_LATER')), self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual(2, len(self.store.human_answers('owner')))
        _, _, lineage = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual(['Synthetic exact answer', 'Synthetic later exact answer'], [a['answer'] for a in lineage['human_answers']])

    def test_question_and_immediate_answer_during_recontract_still_invalidate_snapshot(self):
        tid, _ = self.held()
        def late_resolved_question():
            self.answer(self.ask('Synthetic immediately answered late question?'), text='Synthetic second answer')
        with self.during_commit(late_resolved_question), self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual(['ANSWERED', 'ANSWERED'], [q['status'] for q in self.store.questions('owner')])
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])

    def test_attempt_created_during_recontract_is_rechecked_before_commit(self):
        tid, _ = self.held()
        with self.during_commit(lambda: self.insert_attempt(tid, 'SPAWN_INTENT')), self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        self.assertEqual([], self.events(tid, 'HUMAN_RECONTRACT'))

    def test_changed_state_version_during_recontract_rejects_stale_cas(self):
        tid, _ = self.held()
        with self.during_commit(lambda: self.store.transition(tid, 'NEEDS_INPUT', 'BLOCKED')), self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual('BLOCKED', self.store.task(tid)['state'])
        self.assertEqual([], self.events(tid, 'HUMAN_RECONTRACT'))

    def test_busy_correction_during_recontract_is_retained_for_a_fresh_snapshot(self):
        tid, _ = self.held()
        def correction():
            self.store.db.execute("INSERT INTO human_inputs(owner,time,text,origin) VALUES('owner','synthetic','Exact synthetic late correction','SYNTHETIC_Q4_NOT_HUMAN')")
        with self.during_commit(correction), self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        _, text, lineage = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual('Exact synthetic late correction', lineage['human_corrections'][0]['text'])
        self.assertIn('Exact synthetic late correction', text)

    def test_question_and_hold_failure_rolls_back_question_state_and_note_outbox(self):
        tid = self.freeze()
        before = self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        original = self.store.event
        def fail_after_state(task, kind, data):
            result = original(task, kind, data)
            if kind == 'STATE' and data.get('to') == 'NEEDS_INPUT':
                raise RuntimeError('Synthetic hold commit failure')
            return result
        with patch.object(self.store, 'event', side_effect=fail_after_state), self.assertRaises(RuntimeError):
            self.ask()
        self.assertEqual('READY', self.store.task(tid)['state'])
        self.assertEqual([], self.store.questions('owner'))
        self.assertEqual(before, self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])
        self.assertEqual('PENDING', self.store.db.execute("SELECT status FROM outbox WHERE task=? AND kind='DISPATCH'", (tid,)).fetchone()[0])
        self.assert_no_writer()

    def test_committed_hold_survives_notes_failure_and_replays_once(self):
        tid = self.freeze()
        self.ask()
        with patch('loop.notes.atomic', side_effect=OSError('Synthetic projection failure')), self.assertRaises(OSError):
            self.engine.notes.replay()
        self.assertGreater(self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='NOTE' AND status='PENDING'").fetchone()[0], 0)
        self.reopen()
        self.engine.notes.replay()
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='NOTE' AND status='PENDING'").fetchone()[0])
        self.assertEqual(1, len(self.events(tid, 'STATE')))
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        self.assert_no_writer()

    def test_recontract_failure_after_cas_rolls_back_every_recovery_write(self):
        tid, q = self.held()
        before = self.store.task(tid)
        count = self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        original = self.store.event
        def fail_receipt(task, kind, data):
            if kind == 'HUMAN_RECONTRACT':
                raise RuntimeError('Synthetic receipt failure after state CAS')
            return original(task, kind, data)
        with patch.object(self.store, 'event', side_effect=fail_receipt), self.assertRaises(RuntimeError):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual(before, self.store.task(tid))
        self.assertEqual(count, self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])
        self.assertTrue(self.store.question(q['question_id'])['requires_recontract'])
        self.assertEqual(1, self.store.db.execute("SELECT enabled FROM capabilities WHERE owner='owner'").fetchone()[0])
        self.assertEqual('HELD', self.store.db.execute("SELECT status FROM outbox WHERE task=? AND kind='DISPATCH'", (tid,)).fetchone()[0])

    def test_crash_after_recontract_commit_reuses_same_receipt_after_restart(self):
        tid, _ = self.held()
        with patch.object(self.engine, 'project', side_effect=RuntimeError('Synthetic crash after commit')), self.assertRaises(RuntimeError):
            prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        saved = self.store.recontract_receipt(tid)
        self.reopen()
        result = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual((saved['repo'], saved['text'], saved['lineage']), result)
        self.assertEqual(1, len(self.events(tid, 'HUMAN_RECONTRACT')))
        self.assertEqual(2, len(self.events(tid, 'STATE')))
        with self.assertRaises(Rejected):
            prepare_recontract(self.store, self.engine, tid, 'Different synthetic instruction')
        self.assertEqual('SUPERSEDED', self.call_with_revoked_status(tid)['state'])

    def call_with_revoked_status(self, tid):
        # Library observation only; the old model capability stays revoked.
        return self.engine.result(tid, 'owner')

    def test_notes_pending_returns_committed_recovery_and_retry_replays_same_operation(self):
        tid, _ = self.held()
        output = io.StringIO()
        with patch.object(self.engine, 'project', side_effect=OSError('Synthetic notes full')), contextlib.redirect_stderr(output):
            first = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertIn('documentation PENDING', output.getvalue())
        second = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual(first, second)
        self.assertEqual(1, len(self.events(tid, 'HUMAN_RECONTRACT')))
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='NOTE' AND status='PENDING'").fetchone()[0])

    def test_prepared_scope_binds_one_successor_and_exact_answer_before_dispatch(self):
        tid, q = self.held()
        repo, text, lineage = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        request = {'text': text, 'lineage': lineage}
        with self.assertRaises(Rejected):
            self.engine.submit(test_controller.proposal(), repo, request, 'wrong-owner', 'successor')
        altered = {**lineage, 'human_answers': []}
        with self.assertRaises(Rejected):
            self.engine.submit(test_controller.proposal(), repo, {'text': text, 'lineage': altered}, lineage['successor_owner'], 'successor')
        new = self.engine.submit(test_controller.proposal(), repo, request, lineage['successor_owner'], 'successor')
        self.assertEqual(new, self.engine.submit(test_controller.proposal(), repo, request, lineage['successor_owner'], 'successor'))
        with self.assertRaises(Rejected):
            self.engine.submit(test_controller.proposal(), repo, request, lineage['successor_owner'], 'different-successor')
        packet = self.store.task(new['task'])['packet']
        self.assertEqual(lineage['human_answers'], packet['request']['human_answers'])
        self.assertEqual(self.store.task(tid)['packet']['requirements'], packet['lineage']['preserved_requirements'])
        with self.assertRaises(Rejected):
            self.answer(q, text='Stale synthetic answer')
        self.assert_no_writer()

    def test_recontract_retry_never_creates_another_thinker_after_uncertain_start(self):
        tid, _ = self.held()
        repo, text, lineage = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        with patch('loop.cli.snapshot', side_effect=RuntimeError('Synthetic crash before Thinker process')), self.assertRaises(RuntimeError):
            thinker_cycle(self.root, self.config, repo, text, lineage=lineage)
        with patch('loop.cli.snapshot') as snapshot, patch('loop.cli.subprocess.Popen') as spawn, self.assertRaises(Rejected):
            thinker_cycle(self.root, self.config, repo, text, lineage=lineage)
        snapshot.assert_not_called()
        spawn.assert_not_called()
        self.assertEqual(1, len(self.events(tid, 'RECONTRACT_THINKER_INTENT')))
        self.assert_no_writer()

    def test_concurrent_recontract_has_one_winner_and_retry_reuses_saved_scope(self):
        tid, _ = self.held()
        entered, release = threading.Event(), threading.Event()
        result = []
        def first():
            store = Store(self.root)
            engine = Engine(store, self.config)
            def hold_projection(_):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError('Synthetic synchronization timeout')
            try:
                with patch.object(engine, 'project', side_effect=hold_projection):
                    result.append(prepare_recontract(store, engine, tid, 'Synthetic scoped recovery'))
            finally:
                store.close()
        thread = threading.Thread(target=first)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            with self.assertRaises(Rejected):
                prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        finally:
            release.set()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(1, len(result))
        self.assertEqual(result[0], prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery'))
        self.assertEqual(1, len(self.events(tid, 'HUMAN_RECONTRACT')))

    def test_question_before_dispatch_intent_blocks_actual_adapter_entry(self):
        tid = self.freeze()
        workspace, inputs = self.root / 'synthetic-workspace', self.root / 'synthetic-inputs'
        workspace.mkdir(); inputs.mkdir()
        def prepare(runtime, *_):
            runtime.mkdir(parents=True)
            (runtime / 'config.toml').write_text('# Synthetic transport only\n')
            self.ask()
        with patch('loop.adapter.prepare_runtime', side_effect=prepare), patch('loop.adapter.argv', return_value=['/bin/false']), patch('loop.adapter.subprocess.Popen') as spawn, self.assertRaises(NeedsInput):
            Adapter(self.store, self.config).run(tid, 'preflight', workspace, inputs, 'SYNTHETIC transport ordering test')
        spawn.assert_not_called()
        self.assert_no_writer()
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])

    def test_question_after_dispatch_intent_preserves_already_dispatched_boundary(self):
        tid = self.freeze()
        workspace, inputs, runtime = self.root / 'synthetic-workspace', self.root / 'synthetic-inputs', self.root / 'synthetic-runtime'
        workspace.mkdir(); inputs.mkdir()
        session = str(uuid.uuid4())
        code = 'from pathlib import Path; import json; Path(' + repr(str(runtime / 'final.txt')) + ').write_text("SYNTHETIC local transport result"); print(json.dumps({"type":"thread.started","thread_id":' + repr(session) + '})); print(json.dumps({"type":"turn.started"})); print(json.dumps({"type":"turn.completed"}))'
        original_spawn = subprocess.Popen
        def prepare(runtime, *_):
            runtime.mkdir(parents=True)
            (runtime / 'config.toml').write_text('# Synthetic transport only\n')
        def question_then_spawn(*args, **kwargs):
            self.ask()
            return original_spawn(*args, **kwargs)
        with patch('loop.adapter.prepare_runtime', side_effect=prepare), patch('loop.adapter.argv', return_value=[sys.executable, '-c', code]), patch('loop.adapter.subprocess.Popen', side_effect=question_then_spawn):
            _, receipt = Adapter(self.store, self.config).run(tid, 'preflight', workspace, inputs, 'SYNTHETIC local subprocess, no model/human evidence', runtime=runtime)
        self.assertEqual('COMPLETED', receipt['status'])
        ordering = [r['kind'] for r in self.store.db.execute("SELECT kind FROM events WHERE task=? AND kind IN ('DISPATCH_INTENT','QUESTION') ORDER BY seq", (tid,))]
        self.assertEqual(['DISPATCH_INTENT', 'QUESTION'], ordering)
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        with self.assertRaises(NeedsInput):
            self.store.require_current('owner')

    def test_supported_recontract_directly_normalizes_a_legacy_held_ready_record(self):
        tid, _ = self.legacy_ready(answered=True)
        prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        self.assertEqual('SUPERSEDED', self.store.task(tid)['state'])
        self.assertEqual(['NEEDS_INPUT', 'SUPERSEDED'], [e['to'] for e in self.events(tid, 'STATE')])
        self.assert_no_writer()

    def test_superseded_owner_cannot_commit_a_stale_adapter_attempt(self):
        tid, _ = self.held()
        prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        workspace, inputs = self.root / 'synthetic-workspace', self.root / 'synthetic-inputs'
        workspace.mkdir(); inputs.mkdir()
        def prepare(runtime, *_):
            runtime.mkdir(parents=True)
            (runtime / 'config.toml').write_text('# Synthetic transport only\n')
        with patch('loop.adapter.prepare_runtime', side_effect=prepare), patch('loop.adapter.argv', return_value=['/bin/false']), patch('loop.adapter.subprocess.Popen') as spawn, self.assertRaises(Rejected):
            Adapter(self.store, self.config).run(tid, 'doer', workspace, inputs, 'SYNTHETIC stale revision attempt')
        spawn.assert_not_called()
        self.assert_no_writer()

    def test_engine_running_stage_moves_to_hold_at_its_next_safe_boundary(self):
        tid = self.freeze()
        def material_question(*args, **kwargs):
            self.assertEqual('DOER_RUNNING', self.store.task(tid)['state'])
            self.ask()
            raise NeedsInput('Synthetic question at preflight boundary')
        with patch.object(self.engine.adapter, 'run', side_effect=material_question), self.assertRaises(NeedsInput):
            self.engine.run(tid)
        task = self.store.task(tid)
        self.assertEqual('NEEDS_INPUT', task['state'])
        self.assertTrue(task['candidate'])
        self.assertEqual(['DOER_RUNNING', 'NEEDS_INPUT'], [e['to'] for e in self.events(tid, 'STATE')])
        self.assertEqual(1, len(self.events(tid, 'QUESTION')))
        self.assert_no_writer()

    def test_direct_successor_freeze_rejects_wrong_revision_and_source_binding(self):
        tid, _ = self.held()
        _, text, lineage = prepare_recontract(self.store, self.engine, tid, 'Synthetic scoped recovery')
        packet = {**self.store.task(tid)['packet'], 'lineage': lineage, 'task_revision': lineage['revision'], 'request': {'text': text, 'lineage': lineage, 'human_answers': lineage['human_answers']}}
        for changes in ({'task_revision': lineage['revision'] + 1}, {'source': {**packet['source'], 'head': 'stale-source'}}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                self.store.create('successor', {**packet, **changes}, lineage['successor_owner'])
        self.assertEqual(1, self.store.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])
        self.assert_no_writer()
