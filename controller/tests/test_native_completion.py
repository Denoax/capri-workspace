"""Synthetic completion controls; not native/live or human qualification."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.engine import Engine, ACK_SCHEMA
from loop.native import Binding, NativeAdapter
from loop.native_completion import retain_execution, repair_turn
from loop.native_protocol import Lifecycle
from loop.store import Store
from loop.util import Rejected, identity, tree


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.work = self.root/'work'; self.work.mkdir()
        (self.work/'module.py').write_text('before=1\n')
        self.before = tree(self.work)
        packet = dict(source=dict(source_hash=identity(self.before)), instructions_hash='instructions',
            requirements_hash='requirements', requirements=[dict(id='N0'+str(i)) for i in range(1,9)],
            allowed_paths=['module.py'], steps=[dict(allowed_paths=['module.py'])])
        self.store = Store(self.root/'store'); self.addCleanup(self.store.close)
        self.task = self.store.create('synthetic', packet, 'owner')
        self.engine = Engine.__new__(Engine); self.engine.store=self.store
        self.engine.verify_inputs=lambda _: None
        self.ack = dict(packet_hash=self.task['content_hash'], source_hash=packet['source']['source_hash'],
            instructions_hash='instructions', requirements_hash='requirements',
            requirement_ids=['N0'+str(i) for i in range(1,9)], status='ACK', summary='synthetic')
        self.binding = Binding('doer','thread',2,self.task['content_hash'],identity(self.before),1,'lease','write')

    def lifecycle(self, capture, final, unfinished=False):
        life=Lifecycle('thread'); messages=[]
        def feed(method, **params):
            value=dict(method=method,params=dict(threadId='thread',**params)); life.feed(value); messages.append(value)
        feed('turn/started',turn=dict(id='turn'))
        feed('item/started',turnId='turn',item=dict(id='tool',type='commandExecution'))
        if not unfinished:
            feed('item/completed',turnId='turn',item=dict(id='tool',type='commandExecution',status='completed',exitCode=0))
        feed('item/started',turnId='turn',item=dict(id='final',type='agentMessage'))
        feed('item/completed',turnId='turn',item=dict(id='final',type='agentMessage',phase='final_answer',text=final))
        feed('turn/completed',turn=dict(id='turn',status='completed'))
        capture.mkdir(parents=True,exist_ok=True)
        (capture/'events.jsonl').write_text(''.join(json.dumps(dict(role='doer',generation=2,message=m))+'\n' for m in messages))
        return life

    def test_frozen_ack_survives_edit_but_candidate_hash_and_partial_ids_fail(self):
        (self.work/'module.py').write_text('after=2\n')
        self.engine.ack(self.task,self.ack)
        for change in (dict(source_hash=identity(tree(self.work))),dict(requirement_ids=['N01','N03','N04','N06'])):
            with self.assertRaises(Rejected):self.engine.ack(self.task,{**self.ack,**change})

    def test_harness_invalid_ack_retains_evidence_and_known_failure(self):
        capture=self.root/'harness';capture.mkdir()
        def dispatch(binding,payload,observe_execution,**kw):
            self.assertIn(self.task['content_hash'],payload[0]['text'])
            self.assertIn('N08',payload[0]['text'])
            (self.work/'module.py').write_text('after=2\n')
            life=self.lifecycle(capture,json.dumps({**self.ack,'source_hash':'wrong'}))
            observe_execution(life)
            return life.finish(kw['validate_output'],kw['independent_checks'])
        receipt={}
        with self.assertRaises(Rejected):
            repair_turn(self.engine,self.task,SimpleNamespace(dispatch=dispatch),self.binding,self.work,capture,
                dict(text='synthetic repair',allowed_paths=['module.py']),receipt,lambda:True)
        self.assertEqual(receipt['status'],'FAILED')
        self.assertTrue((capture/'observed-final.txt').exists())
        self.assertNotEqual(receipt['source_before'],receipt['source_after'])

    def adapter_run(self, final, unfinished=False, disconnect=False, role="doer", checks=True, cleanup_failure=False):
        a=NativeAdapter.__new__(NativeAdapter); a.engine=self.engine; a.store=self.store
        a.capture=None;a.capture_lock=threading.Lock();a.context_states={};a.context_order={};a.preflight=None
        a.settings=SimpleNamespace(model='gpt-6.1-sol',state_dir=str(self.root/'state'))
        a.prepare_stage=lambda *args,**kwargs:None; a.evidence_check=lambda *args:checks
        def dispatch(binding,payload,observe_execution=None,**kw):
            if disconnect:raise Rejected('synthetic disconnect')
            life=self.lifecycle(a.capture,final,unfinished)
            if observe_execution is not None:
                observe_execution(life)
            return life.finish(kw['validate_output'],kw['independent_checks'])
        def close():
            if cleanup_failure:
                raise Rejected("synthetic unresolved child cleanup")
        backend=SimpleNamespace(thread='thread',generation=2,proc=SimpleNamespace(pid=os.getpid()),
            start_identity='synthetic',phase='write',dispatch=dispatch,close=close)
        a.slots=SimpleNamespace(backends={'doer':backend},save=lambda:None)
        inputs=self.root/'inputs';inputs.mkdir(exist_ok=True)
        with self.assertRaises((Rejected,ValueError)):
            a.run(self.task['id'],role,self.work,inputs,'synthetic',ACK_SCHEMA)
        result=json.loads(self.store.db.execute('SELECT result FROM attempts ORDER BY rowid DESC LIMIT 1').fetchone()[0])
        return result

    def test_actual_adapter_known_invalid_ack_is_failed(self):
        result=self.adapter_run(json.dumps({**self.ack,'source_hash':'wrong'}))
        self.assertEqual(result['status'],'FAILED')
        self.assertTrue(result['effects_accounted'])

    def test_actual_adapter_malformed_output_is_failed(self):
        self.assertEqual(self.adapter_run('{')['status'],'FAILED')

    def test_actual_adapter_unfinished_tool_remains_uncertain(self):
        self.assertEqual(self.adapter_run(json.dumps(self.ack),unfinished=True)['status'],'DISPATCH_UNCERTAIN')

    def test_actual_adapter_disconnect_remains_uncertain(self):
        self.assertEqual(self.adapter_run('',disconnect=True)['status'],'DISPATCH_UNCERTAIN')

    def test_scope_drift_and_missing_capture_cannot_prove_effects(self):
        capture=self.root/'scope';life=self.lifecycle(capture,json.dumps(self.ack))
        (self.work/'outside.py').write_text('unexpected=1\n')
        receipt={};retain_execution(receipt,life,self.binding,capture,self.work,self.before,['module.py'],lambda:True)
        self.assertFalse(receipt['effects_accounted'])

    def test_preflight_invalid_ack_is_known_failure_and_durable(self):
        result=self.adapter_run(json.dumps({**self.ack,'source_hash':'wrong'}),role='preflight')
        self.assertEqual(result['status'],'FAILED')
        reopened=Store(self.store.home)
        try:
            saved=json.loads(reopened.db.execute('SELECT result FROM attempts').fetchone()[0])
            self.assertEqual(saved,result)
            self.assertFalse((self.store.home/'artifacts'/self.task['id']/'native-stage-state.json').exists())
        finally:
            reopened.close()

    def test_independent_effect_check_failure_remains_uncertain(self):
        result=self.adapter_run(json.dumps({**self.ack,'source_hash':'wrong'}),checks=False)
        self.assertEqual(result['status'],'DISPATCH_UNCERTAIN')
        self.assertFalse(result['effects_accounted'])

    def test_cleanup_failure_preserves_uncertainty(self):
        result=self.adapter_run(json.dumps({**self.ack,'source_hash':'wrong'}),cleanup_failure=True)
        self.assertEqual(result['status'],'DISPATCH_UNCERTAIN')
        self.assertIn('cleanup_failure',result)

    def test_captured_final_must_match_validated_response(self):
        capture=self.root/'mismatched-final'
        life=self.lifecycle(capture,json.dumps(self.ack))
        life.final=json.dumps({**self.ack,'source_hash':'wrong'})
        receipt={}
        retain_execution(receipt,life,self.binding,capture,self.work,self.before,['module.py'],lambda:True)
        self.assertFalse(receipt['effects_accounted'])

    def test_wrong_generation_capture_cannot_account_effects(self):
        capture=self.root/'stale'
        life=self.lifecycle(capture,json.dumps(self.ack))
        path=capture/'events.jsonl'
        path.write_text(path.read_text().replace('"generation": 2','"generation": 1'))
        receipt={}
        retain_execution(receipt,life,self.binding,capture,self.work,self.before,['module.py'],lambda:True)
        self.assertFalse(receipt['effects_accounted'])

    def test_missing_capture_does_not_claim_effects(self):
        capture=self.root/'missing'
        life=self.lifecycle(capture,json.dumps(self.ack))
        (capture/'events.jsonl').unlink()
        receipt={}
        with self.assertRaises(FileNotFoundError):
            retain_execution(receipt,life,self.binding,capture,self.work,self.before,['module.py'],lambda:True)
        self.assertFalse(receipt.get('effects_accounted',False))
