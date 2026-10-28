"""Idle policy integration with disposable source and synthetic lifecycle; no model."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import time
from unittest.mock import Mock
import test_controller
from test_context import usage
from loop.native import NativeAdapter,Binding
from loop.settings import Settings
from loop.engine import Engine
from loop.util import Rejected,identity,tree


class IdleMaintenanceTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp();self.repo=self.root/'fixtures/repo';self.repo.mkdir(parents=True);(self.repo/'code.py').write_text('source')
        import subprocess
        for args in [('init','-q'),('add','.'),('-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','Synthetic')]:subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)
        self.config['authorized_repositories']=[str(self.repo)];self.engine=Engine(self.store,self.config)
        self.tid=self.engine.submit(test_controller.proposal(),self.repo,{'text':'synthetic'},'owner','task')['task'];work=self.root/'work';shutil.copytree(self.repo,work,ignore=shutil.ignore_patterns('.git'))
        self.store.transition(self.tid,'READY','DOER_RUNNING',candidate=str(work));inputs=self.engine.inputs(self.tid,'preflight')
        b=SimpleNamespace(thread='thread',generation=0,proc=SimpleNamespace(pid=os.getpid()),start_identity='fixture-start',workspace=work,inputs=inputs,phase='read',active=None,error=None)
        a=NativeAdapter.__new__(NativeAdapter);a.store=self.store;a.home=self.root;a.engine=self.engine;a.settings=Settings('codex','/not-read',str(self.root/'private'));a.slots=SimpleNamespace(backends={'doer':b});a.context_states={};a.context_order={};a.context_policy=None;a.planned_compactions=set();a.capture=None;a.operation_deadline=time.monotonic()+10;a.operation_tools=7;a.observe=lambda *args:None
        self.adapter=a;self.backend=b;self.state=a.prepare_context(self.tid,'doer');self.state.clock=lambda:1000;self.state.identity=replace(self.state.identity,turn='turn');self.state.update(usage(285000),self.state.identity,1,1000)
        self.binding=Binding('doer','thread',0,self.store.task(self.tid)['content_hash'],identity(tree(work)),1,'synthetic','read')

    def test_soft_checkpoint_allows_bounded_next_turn_once_per_reading_authority(self):
        result=self.adapter.idle_maintenance(self.tid,'doer',[{'text':'bounded'}]);self.assertEqual(result['action'],'CHECKPOINT')
        before=self.state.soft_checkpoint.copy();self.assertTrue(self.adapter.context_admission(self.binding,[{'text':'bounded'}]))
        self.adapter.idle_maintenance(self.tid,'doer',[{'text':'bounded'}]);self.assertEqual(self.state.soft_checkpoint,before)
        self.assertEqual(1,self.store.db.execute("select count(*) from events where kind='CONTEXT_SOFT_CHECKPOINT'").fetchone()[0])

    def test_pending_growth_and_source_drift_cannot_use_old_checkpoint(self):
        self.adapter.idle_maintenance(self.tid,'doer',[])
        with self.assertRaises(Rejected):self.adapter.context_admission(self.binding,[{'text':'x'*200000}])
        (self.backend.workspace/'code.py').write_text('drift')
        with self.assertRaises(Rejected):self.adapter.context_admission(self.binding,[])

    def test_compaction_keeps_combined_deadline_and_tools_then_rereads(self):
        self.state.update(usage(350000),self.state.identity,2,1000);deadline=self.adapter.operation_deadline
        def compact(**kwargs):
            self.assertLessEqual(kwargs['max_seconds'],10);self.state.rehydrating=self.state.restart=True;self.state.persist();return 'synthetic-completed-turn'
        self.backend.compact=Mock(side_effect=compact)
        def probe(*_):self.state.update(usage(10000),self.state.identity,3,1000)
        def rehydrate(*_):self.state.rehydrating=False;self.state.persist()
        self.adapter.probe=Mock(side_effect=probe);self.adapter.rehydrate=Mock(side_effect=rehydrate)
        result=self.adapter.idle_maintenance(self.tid,'doer',[])
        self.assertEqual(result['action'],'ALLOW');self.backend.compact.assert_called_once();self.adapter.rehydrate.assert_called_once()
        self.assertEqual(self.adapter.operation_deadline,deadline);self.assertEqual(self.adapter.operation_tools,7)

    def test_compaction_timeout_is_uncertain_and_never_retried(self):
        self.state.update(usage(350000),self.state.identity,2,1000);self.backend.compact=Mock(side_effect=Rejected('synthetic timeout'))
        with self.assertRaises(Rejected):self.adapter.idle_maintenance(self.tid,'doer',[])
        self.backend.compact.assert_called_once();receipts=list((self.root/'artifacts'/self.tid/'compactions').glob('*/receipt.json'))
        self.assertEqual(len(receipts),1);self.assertEqual(json.loads(receipts[0].read_text())['status'],'UNCERTAIN');self.assertEqual(self.adapter.operation_tools,7)

    def test_checked_dead_compaction_replacement_preserves_budget_and_old_ledger(self):
        from unittest.mock import patch
        from loop.util import digest
        cp=self.adapter.checkpoint(self.tid,'doer');old=self.backend
        self.state.compaction={'thread':old.thread,'item':'synthetic-uncertain'};self.state.probe_used=True;self.state.recovery_probes=['prior'];self.state.persist();raw=self.state.path.read_bytes()
        old.proc.poll=lambda:1;old.controller=self.root/'controller';old.mcp=old.intake_socket=None
        self.adapter.slots.admission=lambda *_:None;self.adapter.slots.observer=lambda *_:None;self.adapter.slots.save=lambda:None
        fresh=SimpleNamespace(**vars(old));fresh.thread='fresh-thread';fresh.generation=old.generation+1;fresh.start_identity='fresh-process';fresh.proc=SimpleNamespace(pid=900001,poll=lambda:None)
        proof=dict(key='synthetic-fence',old_thread=old.thread,pid=old.proc.pid,process=old.start_identity)
        with patch('loop.native.process_identity',return_value=None),patch('loop.native.Backend',return_value=fresh):
            result=self.adapter.replace_fenced_readonly(self.tid,'doer',cp,proof)
        state=self.adapter.context_states['doer'];self.assertEqual(result['new_thread'],'fresh-thread');self.assertEqual(state.order,self.state.order);self.assertEqual(state.recovery_probes,['prior']);self.assertTrue(state.probe_used);self.assertTrue(state.restart);self.assertIsNone(state.compaction)
        saved=Path(state.reconciliations[-1]['proof']['preserved']);self.assertEqual(saved.read_bytes(),raw);self.assertEqual(digest(raw),state.reconciliations[-1]['proof']['sha256'])
