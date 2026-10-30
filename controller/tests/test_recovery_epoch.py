"""Actual reread journal/context path; synthetic backend/read grader, zero models."""
import contextlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import test_context
from loop.context import Checkpoint,ContextState,SECTIONS
from loop.native import NativeAdapter,rehydration_payload
from loop.util import Rejected,identity


class RecoveryEpochTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        workspace=self.root/'workspace';workspace.mkdir();(workspace/'code.py').write_text('sealed')
        inputs=self.root/'inputs';inputs.mkdir();(inputs/'packet.json').write_text('{}');(inputs/'instruction-0.md').write_text('exact original')
        self.authority={name:{} for name in SECTIONS};self.authority.update(questions_answers={'pending':[]},inflight_uncertain=[],next_action={'human_gate':False})
        original=self.root/'original';original.write_text('exact original')
        self.checkpoint=Checkpoint(self.root/'checkpoint.json',self.root);self.checkpoint.save(self.authority,['original'])
        self.state=ContextState(self.root/'context.json',test_context.binding(epoch=0),clock=lambda:1000.)
        self.state.update(test_context.usage(),self.state.identity,1,1000.)
        self.task=dict(revision=1,content_hash='a'*64,packet=dict(requirements_hash='b'*64,instructions_hash='c'*64))
        self.backend=SimpleNamespace(phase='read',active=None,error=None,mcp=None,thread='thread',generation=2,workspace=workspace,inputs=inputs,admission=None,output_schema=None)
        self.adapter=NativeAdapter.__new__(NativeAdapter);self.adapter.settings=SimpleNamespace(state_dir=str(self.root/'runtime'))
        (self.root/'runtime/doer').mkdir(parents=True)
        self.events=[];self.calls=0
        self.adapter.store=SimpleNamespace(task=lambda _:self.task,home=self.root,lock=lambda _:contextlib.nullcontext(),event=lambda *args:self.events.append(args))
        self.adapter.slots=SimpleNamespace(backends={'doer':self.backend},save=lambda:None)
        self.adapter.capture=None;self.adapter.prepare_context=lambda *_:self.state
        self.adapter.checkpoint_authority=lambda *_:self.authority;self.adapter.verify_read_profile=lambda _:None
        self.adapter.remaining=lambda:240;self.adapter.remaining_tools=lambda:12
        def dispatch(*args,**kwargs):
            self.calls+=1
            with self.backend.admission():
                _,expected,_=rehydration_payload(self.task,self.backend,self.authority,self.checkpoint.validate(self.authority))
                result=json.dumps(expected);assert kwargs['validate_output'](result) and kwargs['independent_checks']()
                return result
        self.backend.dispatch=dispatch

    def tearDown(self):self.temp.cleanup()

    def reread(self):return self.adapter.rehydrate('task','doer',self.checkpoint,verify_reads=lambda *_:True)

    def completed_compaction_and_probe(self):
        self.state.compaction_event('item/started','thread','turn','compaction-item')
        self.state.compaction_event('item/completed','thread','turn','compaction-item')
        # Synthetic successful bounded post-compaction probe; no model call.
        self.state.restart=False
        self.state.update(test_context.usage(cumulative=8_000_000),self.state.identity,self.state.order+1,1000.)

    def test_completed_new_epoch_allows_reread_of_same_checkpoint_once(self):
        self.reread();self.completed_compaction_and_probe();self.reread()
        self.assertEqual(self.calls,2)
        with self.assertRaises(Rejected):self.reread()
        self.assertEqual(self.calls,2)
        records=[json.loads(path.read_text()) for path in (self.root/'runtime/doer').glob('*.intent')]
        self.assertEqual(sorted(row['epoch'] for row in records),[0,1])

    def test_probe_refresh_without_epoch_change_never_replays_reread(self):
        self.reread();self.state.update(test_context.usage(cumulative=8_000_000),self.state.identity,self.state.order+1,1000.)
        with self.assertRaises(Rejected):self.reread()
        self.assertEqual(self.calls,1)

    def test_incomplete_compaction_blocks_before_reread(self):
        self.reread();self.state.compaction_event('item/started','thread','turn','unfinished')
        with self.assertRaises(Rejected):self.reread()
        self.assertEqual(self.calls,1)

    def test_failed_reread_retains_single_use_intent(self):
        def failure(*args,**kwargs):raise RuntimeError('synthetic failed read')
        self.backend.dispatch=failure
        with self.assertRaises(RuntimeError):self.reread()
        with self.assertRaises(Rejected):self.reread()
        self.assertEqual(len(list((self.root/'runtime/doer').glob('*.intent'))),1)

    def test_legacy_unknown_epoch_intent_stays_blocking_and_unchanged(self):
        seal=self.checkpoint.validate(self.authority)
        old=identity(dict(checkpoint=seal,role='doer',thread='thread',generation=2))
        path=self.root/'runtime/doer'/('rehydration-'+old+'.intent');path.write_text('preserved legacy intent')
        self.completed_compaction_and_probe()
        with self.assertRaises(Rejected):self.reread()
        self.assertEqual(path.read_text(),'preserved legacy intent');self.assertEqual(self.calls,0)
