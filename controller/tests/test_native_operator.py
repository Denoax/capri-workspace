"""Parent-operator contract tests with synthetic Engine/roles; no real models."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import socket
import threading

import test_controller
from loop.adapter import process_identity
from loop.native_operator import NativeOperator,request_review
from loop.native_startup import StartupJournal
from loop.util import Rejected,identity,tree,digest


def operator_fixture(self):
    self.workspace=self.root/'candidate';self.workspace.mkdir();(self.workspace/'code.py').write_text('sealed')
    packet=dict(requirements=[dict(id=f'N{i:02d}') for i in range(1,9)])
    task=self.store.create('task',packet,'owner');self.tid=task['id']
    self.store.transition(self.tid,'READY','DOER_RUNNING',candidate=str(self.workspace))
    self.store.transition(self.tid,'DOER_RUNNING','CANDIDATE_SEALED',seal=json.dumps(dict(source_hash=identity(tree(self.workspace)),files=tree(self.workspace))))
    self.controller=self.root/'source/controller';self.controller.mkdir(parents=True);(self.controller/'native.py').write_text('new source')
    self.evidence=self.root/'INDEX.json';self.evidence.write_text('{"N01":"synthetic receipt"}')
    self.calls=[];self.root_runtime=self.root/'runtime';self.root_runtime.mkdir()
    def review(tid):
        self.calls.append(('review',tid));self.store.transition(tid,'CANDIDATE_SEALED','REVIEWER_RUNNING');self.store.transition(tid,'REVIEWER_RUNNING','REVIEW_SEALED');self.store.transition(tid,'REVIEW_SEALED','REPORTING',outcome='UNVERIFIED')
    def report(prompt,report_task=None):
        self.calls.append(('same-thinker-report',report_task));self.store.transition(report_task,'REPORTING','AWAITING_HUMAN')
    self.engine=SimpleNamespace(store=self.store,require_current=lambda t:self.store.require_current(t['owner']),verify_inputs=lambda t:None,native_materials={},review=review,result=lambda tid,owner:dict(task=tid,state=self.store.task(tid)['state'],outcome=self.store.task(tid)['outcome']))
    self.adapter=SimpleNamespace(slots=SimpleNamespace(root=self.root_runtime),thinker_turn=report)
    self.journal=StartupJournal(self.store,'synthetic-maintenance',{})
    self.operator=NativeOperator(self.engine,self.adapter,dict(owner='owner',controller_hash=identity(tree(self.controller)),source_hash=identity(tree(self.controller.parent))),self.controller,self.journal)
    t=self.store.task(self.tid)
    self.binding=dict(task=self.tid,version=t['version'],owner='owner',packet_hash=t['content_hash'],source_hash=identity(tree(self.workspace)),controller_hash=identity(tree(self.controller)),supervisor_pid=os.getpid(),supervisor_identity=process_identity(os.getpid()),evidence=[dict(name='INDEX.json',path=str(self.evidence),sha256=digest(self.evidence.read_bytes()))])



class OperatorTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp();operator_fixture(self)

    def test_exact_hold_review_report_and_human_stop_once(self):
        result=self.operator.finish(dict(action='finish-review',binding=self.binding))
        self.assertEqual(result['status'],'AWAITING_HUMAN');self.assertEqual(self.store.task(self.tid)['outcome'],'UNVERIFIED')
        self.assertEqual(self.calls,[('review',self.tid),('same-thinker-report',self.tid)])
        with self.assertRaises(Rejected):self.operator.finish(dict(action='finish-review',binding=self.binding))
        self.assertEqual(len(self.calls),2)

    def test_stale_version_source_supervisor_and_evidence_reject_before_dispatch(self):
        for key,value in [('version',0),('source_hash','wrong'),('controller_hash','wrong'),('supervisor_identity','reused')]:
            with self.subTest(key=key),self.assertRaises(Rejected):self.operator.finish(dict(action='finish-review',binding={**self.binding,key:value}))
        self.evidence.write_text('changed')
        with self.assertRaises(Rejected):self.operator.finish(dict(action='finish-review',binding=self.binding))
        self.assertEqual(self.calls,[]);self.assertEqual(self.journal.records(),[])

    def test_failed_formal_review_is_held_and_never_fabricates_a_report(self):
        def failed(tid):
            self.calls.append(('review',tid));self.store.transition(tid,'CANDIDATE_SEALED','REVIEWER_RUNNING');raise RuntimeError('synthetic budget rejection')
        self.engine.review=failed
        with self.assertRaises(RuntimeError):self.operator.finish(dict(action='finish-review',binding=self.binding))
        self.assertEqual(self.store.task(self.tid)['state'],'BLOCKED');self.assertEqual(self.calls,[('review',self.tid)])
        self.assertEqual(self.journal.records()[-1]['milestone'],'FINAL_REVIEW_OR_REPORT_INCOMPLETE')

    def test_wrong_action_and_unbounded_evidence_reject(self):
        with self.assertRaises(Rejected):self.operator.finish(dict(action='accept',binding=self.binding))
        self.evidence.write_text('x'*24001);self.binding['evidence'][0]['sha256']=digest(self.evidence.read_bytes())
        with self.assertRaises(Rejected):self.operator.finish(dict(action='finish-review',binding=self.binding))
        self.assertEqual(self.calls,[])

    def test_socket_rejects_missing_private_parent_capability(self):
        self.operator.start()
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(3);client.connect(str(self.operator.path));client.sendall(b'{"key":"wrong","action":"finish-review","binding":{}}\n')
                result=json.loads(client.makefile('rb').readline())
            self.assertEqual(result['status'],'REJECTED');self.assertEqual(self.calls,[])
            self.assertEqual((self.root_runtime/'operator.key').stat().st_mode&0o777,0o600)
        finally:self.operator.close()

    def test_public_request_uses_existing_supervisor_main_thread(self):
        self.operator.start();result={}
        def client():result['value']=request_review(self.root_runtime,self.binding)
        worker=threading.Thread(target=client);worker.start()
        try:
            self.operator.poll(timeout=3);worker.join(timeout=3)
            self.assertFalse(worker.is_alive());self.assertEqual(result['value']['status'],'AWAITING_HUMAN')
        finally:self.operator.close()

    def test_unreconciled_maintenance_blocks_formal_review(self):
        self.journal.append('MAINTENANCE_UNCERTAIN',dict(key='synthetic-timeout',role='doer'))
        with self.assertRaises(Rejected):self.operator.finish(dict(action='finish-review',binding=self.binding))
        self.assertEqual(self.calls,[])

    def test_fence_checks_dead_readonly_identity_and_exact_source(self):
        from unittest.mock import patch
        from loop.context import Checkpoint,SECTIONS
        authority={name:{} for name in SECTIONS};authority.update(questions_answers={'pending':[]},inflight_uncertain=[],next_action={'human_gate':False})
        original=self.root/'original.txt';original.write_text('synthetic exact original');cp=Checkpoint(self.root/'cp.json',self.root);cp.save(authority,['original.txt'])
        backend=SimpleNamespace(active=None,error='synthetic timeout',phase='read',thread='prior',generation=2,proc=SimpleNamespace(pid=900001,poll=lambda:1),start_identity='synthetic-start',workspace=self.workspace,inputs=self.workspace)
        self.adapter.slots.backends={'doer':backend};self.adapter.checkpoint_authority=lambda *_:authority
        bound=dict(key='uncertain',action='compact-role',role='doer',old_thread='prior',generation=2,pid=900001,process='synthetic-start',source=tree(self.workspace),inputs=tree(self.workspace),checkpoint=str(cp.path),checkpoint_sha256=digest(cp.path.read_bytes()))
        self.journal.append('MAINTENANCE_READ_ONLY_BOUND',bound);self.journal.append('MAINTENANCE_UNCERTAIN',dict(key='uncertain',role='doer'))
        request={**self.binding,'uncertain_key':'uncertain'}
        with patch('loop.native_operator.process_identity',return_value='reused'):
            with self.assertRaises(Rejected):self.operator.reconcile(request,self.store.task(self.tid),backend)
        with patch('loop.native_operator.process_identity',return_value=None):
            result=self.operator.reconcile(request,self.store.task(self.tid),backend)
        self.assertEqual(result['status'],'FENCED_READ_ONLY');self.assertEqual(len(self.operator.unresolved()),1)
        # Fencing alone neither reuses a thread nor completes recovery/review.
        self.assertEqual(self.calls,[])
        with self.assertRaises(Rejected):self.operator.finish(dict(action='finish-review',binding=self.binding))
