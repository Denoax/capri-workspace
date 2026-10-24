import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from loop.native_owner_outcomes import completed_hold, OwnerHold
from loop.native import NativeAdapter
from loop.service import capability
from loop.store import Store
from loop.util import Rejected, NeedsInput, digest


class OwnerOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.state=Store(Path(self.temp.name));self.addCleanup(self.state.close)

    def test_pending_question_is_bound_and_existing_answer_is_preserved(self):
        question=self.state.ask_question('owner','scope',1,'Exact blank label behavior?')
        hold=completed_hold(self.state,'owner','Model must not invent an answer')
        self.assertEqual(hold.result['outcome'],'NEEDS_INPUT')
        self.assertEqual(hold.result['questions'][0]['id'],question['question_id'])
        self.assertEqual(hold.result['gate'],'BLOCKED')
        # Existing core API, synthetic transport fixture, disposable Store only.
        fields=dict(question_id=question['question_id'],owner='owner',scope_key='scope',task_id=None,
            revision=1,packet_hash=None,text='Return "Untitled"',
            origin='ACTUAL_USER_ANSWER_FORWARDED_FROM_SETUP_CHAT',source_ref='SYNTHETIC_UNIT_ONLY')
        self.state.answer_question(**fields)
        self.assertIsNone(completed_hold(self.state,'owner','done'))
        self.assertEqual(self.state.human_answers('owner')[0]['answer'],'Return "Untitled"')

    def test_model_cannot_create_a_question_by_claiming_one(self):
        with self.assertRaisesRegex(Rejected,'actual durable core question'):
            completed_hold(self.state,'owner',json.dumps(dict(outcome='NEEDS_INPUT',detail='invented')))

    def test_source_and_budget_gaps_remain_distinct_completed_holds(self):
        for outcome in ['INSUFFICIENT_SOURCE','BUDGET_INFEASIBLE']:
            hold=completed_hold(self.state,'owner',json.dumps(dict(outcome=outcome,detail='specific gap')))
            self.assertEqual(hold.result['outcome'],outcome)
            self.assertEqual(hold.result['gate'],'BLOCKED')
        self.assertIsNone(completed_hold(self.state,'owner','Native turn exceeded exposed tool budget'))
        self.assertEqual(self.state.db.execute('SELECT count(*) FROM tasks').fetchone()[0],0)

    def test_question_after_native_dispatch_returns_typed_hold_only_with_completed_capture(self):
        for complete in (True,False):
            with self.subTest(complete=complete),tempfile.TemporaryDirectory() as temp:
                state=Store(Path(temp));self.addCleanup(state.close)
                adapter=NativeAdapter.__new__(NativeAdapter);adapter.store=state;adapter.thinker_owner='owner'
                token=capability(state,'owner',dict(repo=temp,request=dict(text='scope'),key='key'))
                adapter.thinker_capability_hash=digest(token.encode())
                adapter.prepare_owner_context=lambda:(SimpleNamespace(identity=SimpleNamespace(revision=1),decision=lambda **kw:dict(action='ALLOW')),dict(source_hash='source'))
                adapter.owner_idle_maintenance=lambda payload:None;adapter.owner_recovery_estimate=lambda:0;adapter.owner_packet=lambda:None
                adapter.capture=None;adapter.evidence_check=lambda *args:True
                backend=SimpleNamespace(thread='thread',generation=1,phase='read',admission=None,output_schema=None)
                def dispatch(binding,payload,**kwargs):
                    with backend.admission(binding,'controller',payload):
                        state.ask_question('owner','scope',1,'Exact behavior?')
                        events=[dict(role='thinker',message=dict(method='turn/started',params=dict(threadId='thread',turn=dict(id='turn'))))]
                        if complete:events.append(dict(role='thinker',message=dict(method='turn/completed',params=dict(threadId='thread',turn=dict(id='turn',status='completed')))))
                        (adapter.capture/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in events))
                        return 'question held'
                backend.dispatch=dispatch;adapter.slots=SimpleNamespace(backends=dict(thinker=backend),save=lambda:None)
                with self.assertRaises(NeedsInput) as caught:adapter.owner_dispatch([dict(type='text',text='scope')])
                self.assertEqual(isinstance(caught.exception,OwnerHold),complete)
                self.assertEqual(state.db.execute('SELECT count(*) FROM tasks').fetchone()[0],0)


if __name__=='__main__':unittest.main()
