"""A01/A02 synthetic temporary-state regressions; never proof of human origin."""
import contextlib
import json
from pathlib import Path
import subprocess
import threading
from unittest.mock import patch

from test_controller import IsolatedCase, proposal
from loop.cli import capture_human_answer, decide, prepare_recontract
from loop.collector import seal_zip
from loop.engine import Engine
from loop.service import capability, handle, recover
from loop.store import Store
from loop.util import NeedsInput, Rejected


class QuestionTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.repo = self.root / 'fixtures/repo'
        self.repo.mkdir(parents=True)
        (self.repo / 'module.py').write_text('value=1\n')
        for argv in (['git', 'init', '-q', str(self.repo)], ['git', '-C', str(self.repo), 'add', '.'], ['git', '-C', str(self.repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'Baseline']):
            subprocess.run(argv, check=True, capture_output=True)
        self.config['authorized_repositories'] = [str(self.repo)]
        self.token = capability(self.store, 'owner', {'repo': str(self.repo), 'request': {'text': 'Exact synthetic request'}, 'key': 'key'})

    def call(self, operation, arguments):
        return handle(self.store, self.config, {'capability': self.token, 'operation': operation, 'arguments': arguments})['result']

    def ask(self, text='Blank name behavior?'):
        return self.call('ask_human', {'question': text})

    def answer(self, q, text='Exact human fixture answer', source_ref='synthetic-human-transport:one', **changes):
        args = {k: q[k] for k in ('question_id', 'owner', 'scope_key', 'task_id', 'revision', 'packet_hash')}
        args.update(text=text, origin='FOREGROUND_HUMAN_STDIN', source_ref=source_ref)
        args.update(changes)
        return capture_human_answer(self.store, **args)

    def test_unanswered_question_blocks_immediate_submission_and_restart(self):
        q = self.ask()
        with self.assertRaises(Rejected):
            self.call('submit_task', {'proposal': proposal()})
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='DISPATCH'").fetchone()[0])
        self.store.close()
        self.store = Store(self.root)
        recover(self.store)
        with self.assertRaises(Rejected):
            self.call('submit_task', {'proposal': proposal()})
        self.assertEqual('PENDING', self.store.question(q['question_id'])['status'])
        with self.assertRaises(Rejected):
            self.store.create('direct-bypass', {}, 'owner')

    def test_only_scoped_actual_capture_resolves_and_exact_answer_is_frozen(self):
        q = self.ask()
        for operation in ('answer_question', 'resolve_question', 'capture_human_answer'):
            with self.assertRaises(Rejected):
                self.call(operation, {'question_id': q['question_id'], 'answer': 'model guess', 'origin': 'FOREGROUND_HUMAN_STDIN'})
        with self.assertRaises(Rejected):
            self.answer(q, origin='CONTROLLER_DATA_NOT_HUMAN')
        answered = self.answer(q, text='Return “Hello, Guest!”')
        self.assertEqual('ANSWERED', answered['status'])
        self.assertEqual(answered['answer_id'], self.answer(q, text='Return “Hello, Guest!”')['answer_id'])
        self.answer(q, text='Preserve exact later correction!', source_ref='synthetic-human-transport:two')
        with self.assertRaises(Rejected):
            self.answer(q, text='Return “Hello, Guest!”')
        t = self.call('submit_task', {'proposal': proposal()})
        request = self.store.task(t['task'])['packet']['request']
        self.assertEqual(['Return “Hello, Guest!”', 'Preserve exact later correction!'], [a['answer'] for a in request['human_answers']])
        self.assertEqual('Exact synthetic request', request['text'])
        self.assertEqual(2, self.store.db.execute('SELECT COUNT(*) FROM question_answers').fetchone()[0])
        with self.assertRaises(Rejected):
            self.answer(q, text='Old prefreeze binding')

    def test_every_answer_binding_field_is_checked_without_mutation(self):
        q = self.ask()
        cases = {'owner': 'other', 'scope_key': 'other', 'task_id': 'other', 'revision': 999, 'packet_hash': 'other'}
        for key, value in cases.items():
            with self.subTest(field=key), self.assertRaises(Rejected):
                self.answer(q, **{key: value})
        self.assertEqual('PENDING', self.store.question(q['question_id'])['status'])
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM question_answers').fetchone()[0])

    def test_material_questions_are_independent_and_repeated_pending_ask_is_idempotent(self):
        first = self.ask()
        self.assertEqual(first['question_id'], self.ask()['question_id'])
        second = self.ask('Second material question?')
        self.answer(first)
        with self.assertRaises(Rejected):
            self.call('submit_task', {'proposal': proposal()})
        self.answer(second)
        self.assertEqual('READY', self.call('submit_task', {'proposal': proposal()})['state'])

    def test_frozen_question_and_answer_hold_dispatch_report_until_recontract(self):
        t = self.call('submit_task', {'proposal': proposal()})
        q = self.ask()
        self.assertEqual(t['task'], q['task_id'])
        engine = Engine(self.store, self.config)
        for answered in (False, True):
            if answered:
                self.answer(q, source_ref='synthetic-afterfreeze:one')
            with self.subTest(answered=answered), self.assertRaises(NeedsInput):
                engine.require_current(self.store.task(t['task']))
            with self.assertRaises(NeedsInput):
                self.store.transition(t['task'], 'NEEDS_INPUT', 'DOER_RUNNING')
            self.assertEqual('NEEDS_INPUT', engine.result(t['task'], 'owner')['state'])
        self.assertEqual('NEEDS_INPUT', self.store.task(t['task'])['state'])
        with patch.object(engine, 'project', return_value={}):
            repo, text, lineage = prepare_recontract(self.store, engine, t['task'], 'Explicit actual fixture correction')
        self.assertEqual('SUPERSEDED', self.store.task(t['task'])['state'])
        self.assertEqual('Exact human fixture answer', lineage['human_answers'][0]['answer'])
        self.assertEqual(2, lineage['revision'])
        with self.assertRaises(Rejected):
            self.answer(q, source_ref='synthetic-afterfreeze:stale')

    def test_frozen_answer_rejects_a_newer_task_revision(self):
        tid = self.call('submit_task', {'proposal': proposal()})['task']
        q = self.ask()
        self.store.db.execute('UPDATE tasks SET revision=revision+1 WHERE id=?', (tid,))
        with self.assertRaises(Rejected):
            self.answer(q)
        self.assertEqual('PENDING', self.store.question(q['question_id'])['status'])

    def test_dispatch_intent_is_not_recorded_or_spawned_with_a_pending_question(self):
        from loop.adapter import Adapter
        tid = self.call('submit_task', {'proposal': proposal()})['task']
        self.ask()
        workspace = self.root / 'workspace'
        workspace.mkdir()
        inputs = self.root / 'inputs'
        inputs.mkdir()
        with patch('loop.adapter.subprocess.Popen') as spawn, self.assertRaises(NeedsInput):
            Adapter(self.store, self.config).run(tid, 'preflight', workspace, inputs, 'Synthetic preflight prompt')
        spawn.assert_not_called()
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0])

    def test_unanswered_question_cannot_be_cleared_by_recontract(self):
        tid = self.call('submit_task', {'proposal': proposal()})['task']
        self.ask()
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        with self.assertRaises(Rejected):
            prepare_recontract(self.store, Engine(self.store, self.config), tid, 'Generic correction cannot answer a bound question')
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])

    def test_late_question_cannot_be_orphaned_by_recontract(self):
        tid = self.call('submit_task', {'proposal': proposal()})['task']
        self.answer(self.ask())
        engine = Engine(self.store, self.config)
        original_transaction = self.store.transaction
        @contextlib.contextmanager
        def new_question_before_transaction():
            with patch.object(self.store, 'transaction', original_transaction):
                self.ask('Late question during re-contract?')
            with original_transaction():
                yield
        with patch.object(self.store, 'transaction', new_question_before_transaction), self.assertRaises(Rejected):
            prepare_recontract(self.store, engine, tid, 'Actual fixture correction')
        self.assertEqual('NEEDS_INPUT', self.store.task(tid)['state'])
        self.assertEqual('PENDING', self.store.questions('owner')[-1]['status'])
        self.assertEqual('Late question during re-contract?', self.store.questions('owner')[-1]['text'])

    def test_question_between_validation_and_freeze_blocks_intake_atomically(self):
        from loop.contract import validate
        def question_after_validate(*args, **kwargs):
            packet = validate(*args, **kwargs)
            self.ask()
            return packet
        with patch('loop.engine.validate', side_effect=question_after_validate), self.assertRaises(Rejected):
            self.call('submit_task', {'proposal': proposal()})
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])

    def test_answer_correction_between_validation_and_freeze_rejects_stale_packet(self):
        from loop.contract import validate
        q = self.ask()
        self.answer(q)
        def correction_after_validate(*args, **kwargs):
            packet = validate(*args, **kwargs)
            self.answer(q, text='Newer correction', source_ref='synthetic-human-transport:newer')
            return packet
        with patch('loop.engine.validate', side_effect=correction_after_validate), self.assertRaises(Rejected):
            self.call('submit_task', {'proposal': proposal()})
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])

    def test_answer_failure_rolls_back_resolution_and_event(self):
        q = self.ask()
        with patch.object(self.store, 'event', side_effect=RuntimeError('Injected write failure')), self.assertRaises(RuntimeError):
            self.answer(q)
        self.assertEqual('PENDING', self.store.question(q['question_id'])['status'])
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM question_answers').fetchone()[0])

    def test_report_acknowledgment_is_held_after_late_question(self):
        tid = self.call('submit_task', {'proposal': proposal()})['task']
        self.store.transition(tid, 'READY', 'REPORTING')
        self.ask()
        with self.assertRaises(NeedsInput):
            Engine(self.store, self.config).acknowledge_report(tid, 'owner', {'package_sha256': 'x', 'packet_hash': 'x', 'summary': 'stale', 'limitations': [], 'gate': 'AWAITING_HUMAN'}, 'session')
        self.assertEqual('REPORTING', self.store.task(tid)['state'])

    def test_question_during_projection_fences_gate_transition_and_result_ack(self):
        tid = self.call('submit_task', {'proposal': proposal()})['task']
        self.store.transition(tid, 'READY', 'REPORTING')
        with self.store.transaction():
            self.store.db.execute("INSERT INTO outbox(id,task,kind,logical_key,payload) VALUES('result',?,'RESULT','result','{}')", (tid,))
        engine = Engine(self.store, self.config)
        t = self.store.task(tid)
        response = {'package_sha256': 'package', 'packet_hash': t['content_hash'], 'summary': 'Synthetic report', 'limitations': [], 'gate': 'AWAITING_HUMAN'}
        def late_question(_):
            self.ask()
        with patch.object(engine, 'result', return_value={'package': {'sha256': 'package'}}), patch.object(engine, 'project', side_effect=late_question), self.assertRaises(NeedsInput):
            engine.acknowledge_report(tid, 'owner', response, 'session')
        self.assertEqual('REPORTING', self.store.task(tid)['state'])
        self.assertEqual('PENDING', self.store.db.execute("SELECT status FROM outbox WHERE kind='RESULT'").fetchone()[0])

    def test_legacy_questions_migrate_pending_without_guessing_answers(self):
        tid = self.call('submit_task', {'proposal': proposal()})['task']
        with self.store.transaction():
            event = self.store.event(None, 'QUESTION', {'owner': 'owner', 'question': 'Legacy ambiguity?', 'answer': 'PENDING_HUMAN'})
            self.store.event(None, 'HUMAN_CORRECTION', {'owner': 'owner', 'text': 'Unbound text is not a question resolution'})
        self.store.db.execute('DROP TABLE question_answers')
        self.store.db.execute('DROP TABLE questions')
        self.store.db.execute('PRAGMA user_version=1')
        self.store.close()
        self.store = Store(self.root)
        self.assertEqual(2, self.store.db.execute('PRAGMA user_version').fetchone()[0])
        q = self.store.question('legacy:' + str(event))
        self.assertEqual(tid, q['task_id'])
        self.assertEqual('PENDING', q['status'])
        self.assertEqual(self.store.task(tid)['content_hash'], q['packet_hash'])
        with self.assertRaises(NeedsInput):
            Engine(self.store, self.config).require_current(self.store.task(tid))
        self.store.close()
        self.store = Store(self.root)
        self.assertEqual(1, len(self.store.questions('owner')))


class DecisionTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        task = self.make()
        folder = self.root / 'artifacts' / task['id']
        folder.mkdir(parents=True)
        (folder / 'evidence.txt').write_text('Synthetic source-bound gate fixture')
        package = seal_zip(self.root / 'review.zip', {'evidence': folder}, {'task': task['id'], 'packet_hash': task['content_hash'], 'candidate': 'candidate'})
        receipt = {k: package[k] for k in ('path', 'sha256', 'bytes')}
        self.task = self.store.transition(task['id'], 'READY', 'AWAITING_HUMAN', review=json.dumps(receipt), seal=json.dumps({'commit': 'candidate', 'files': {}}), outcome='PASS')
        self.engine = Engine(self.store, self.config)
        self.args = dict(task_id=task['id'], action='revise', package_sha256=package['sha256'], packet_hash=task['content_hash'], candidate='candidate', version=self.task['version'], confirm=f"revise {task['id']} {package['sha256']}")

    def decision(self, **changes):
        return decide(self.store, self.engine, **{**self.args, **changes})

    def assert_undecided(self):
        self.assertEqual('AWAITING_HUMAN', self.store.task(self.task['id'])['state'])
        self.assertEqual(self.task['version'], self.store.task(self.task['id'])['version'])
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0])
        self.assertEqual(0, self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='HUMAN_DECISION'").fetchone()[0])

    def test_transition_failure_rolls_back_decision_event_and_projection_outbox(self):
        before = self.store.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]
        with patch.object(self.store, 'transition_in_transaction', side_effect=RuntimeError('Before gate CAS')), self.assertRaises(RuntimeError):
            self.decision()
        self.assert_undecided()
        self.assertEqual(before, self.store.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0])

    def test_event_failure_after_cas_rolls_back_every_decision_write(self):
        original = self.store.event
        def fail_final_event(task, kind, data):
            if kind == 'HUMAN_DECISION':
                raise RuntimeError('After CAS, before commit')
            return original(task, kind, data)
        with patch.object(self.store, 'event', side_effect=fail_final_event), self.assertRaises(RuntimeError):
            self.decision()
        self.assert_undecided()

    def test_after_commit_crash_retry_is_idempotent_and_notes_are_recoverable(self):
        with patch.object(self.engine, 'project', side_effect=RuntimeError('Synthetic crash after COMMIT')), self.assertRaises(RuntimeError):
            self.decision(operation_id='stable-operation')
        self.assertEqual('REVISION_REQUESTED', self.store.task(self.task['id'])['state'])
        self.store.close()
        self.store = Store(self.root)
        self.engine = Engine(self.store, self.config)
        result = self.decision(operation_id='stable-operation')
        self.assertEqual('REVISION_REQUESTED', result['state'])
        self.assertEqual(1, self.store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0])
        self.assertEqual(1, self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='HUMAN_DECISION'").fetchone()[0])
        self.assertEqual(self.task['version'] + 1, self.store.task(self.task['id'])['version'])
        self.assertEqual(0, self.engine.notes.reconcile()['pending'])

    def test_notes_failure_after_commit_returns_pending_and_replays_without_new_decision(self):
        with patch.object(self.engine, 'project', side_effect=OSError('Disk full')):
            result = self.decision()
        self.assertEqual('PENDING', result['documentation'])
        self.assertEqual('REVISION_REQUESTED', self.store.task(self.task['id'])['state'])
        self.decision()
        self.assertEqual(1, self.store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0])
        self.assertEqual(0, self.engine.notes.reconcile()['pending'])

    def test_operation_identity_cannot_be_reused_for_a_conflicting_action(self):
        self.decision(operation_id='one')
        args = {**self.args, 'action': 'reject', 'confirm': f"reject {self.task['id']} {self.args['package_sha256']}"}
        with self.assertRaises(Rejected):
            decide(self.store, self.engine, **args, operation_id='one')
        self.assertEqual('REVISION_REQUESTED', self.store.task(self.task['id'])['state'])
        self.assertEqual(1, self.store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0])

    def test_wrong_bindings_do_not_write_and_are_rechecked_inside_transaction(self):
        for key, value in {'package_sha256': 'wrong', 'packet_hash': 'wrong', 'candidate': 'wrong', 'version': 999}.items():
            with self.subTest(field=key), self.assertRaises(Rejected):
                args = {**self.args, key: value}
                args['confirm'] = f"{args['action']} {args['task_id']} {args['package_sha256']}"
                decide(self.store, self.engine, **args)
            self.assert_undecided()
        original_transaction = self.store.transaction
        @contextlib.contextmanager
        def concurrent_update_before_begin():
            self.store.db.execute('UPDATE tasks SET version=version+1 WHERE id=?', (self.task['id'],))
            with original_transaction():
                yield
        with patch.object(self.store, 'transaction', concurrent_update_before_begin), self.assertRaises(Rejected):
            self.decision()
        self.assertEqual(0, self.store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0])

    def test_conflicting_concurrent_decisions_have_one_winner(self):
        barrier = threading.Barrier(2)
        results = []
        def worker(action):
            store = Store(self.root)
            engine = Engine(store, self.config)
            try:
                barrier.wait(timeout=3)
                args = {**self.args, 'action': action, 'confirm': f"{action} {self.task['id']} {self.args['package_sha256']}"}
                with patch.object(engine, 'project', return_value={}):
                    results.append(decide(store, engine, **args))
            except Rejected as error:
                results.append(error)
            finally:
                store.close()
        threads = [threading.Thread(target=worker, args=(action,)) for action in ('revise', 'reject')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
        self.assertEqual(1, sum(isinstance(r, dict) for r in results))
        self.assertEqual(1, sum(isinstance(r, Rejected) for r in results))
        self.assertEqual(1, self.store.db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0])

    def test_accept_has_no_dispatch_integration_or_production_side_effect(self):
        args = {**self.args, 'action': 'accept', 'confirm': f"accept {self.task['id']} {self.args['package_sha256']}"}
        before = self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='DISPATCH'").fetchone()[0]
        result = decide(self.store, self.engine, **args)
        self.assertEqual('ACCEPTED', result['state'])
        self.assertEqual('NOT_PERFORMED', result['integration'])
        self.assertEqual('NOT_AUTHORIZED', result['next_task'])
        self.assertEqual(before, self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE kind='DISPATCH'").fetchone()[0])
        self.assertEqual(1, self.store.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])
