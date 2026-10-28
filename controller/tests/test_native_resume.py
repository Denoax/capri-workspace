"""Checked sealed-runtime restart controls. Synthetic processes; no model calls."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_controller
import test_native_operator
from loop.context import Checkpoint,SECTIONS
from loop.native_resume import inspect_resume,run_resume
from loop.native_startup import StartupJournal
from loop.service import capability
from loop.util import Rejected,identity,tree,digest,write_json


class RuntimeResumeTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp();test_native_operator.operator_fixture(self)
        self.controller=self.root/'product/controller';self.controller.mkdir(parents=True);(self.controller/'code.py').write_text('synthetic fixed source')
        self.cfg=dict(home=str(self.root),workflow=self.config,settings=dict(binary='codex',auth_file='/not-read',state_dir=str(self.root_runtime)))
        self.native_binding=dict(operation='synthetic-runtime',owner='owner',config_hash=identity(self.cfg),controller_hash=identity(tree(self.controller)),source_hash=identity(tree(self.controller.parent)))
        self.operator.binding=self.native_binding;self.operator.controller=self.controller
        self.operator.journal=StartupJournal(self.store,'synthetic-runtime',self.native_binding)
        self.journal=self.operator.journal
        self.binding['controller_hash']=identity(tree(self.controller))
        self.binding.update(thread='old-doer',role_generation=4)
        self.inputs=self.root/'role-inputs';self.inputs.mkdir();(self.inputs/'request').write_text('exact synthetic original')
        self.rows={role:dict(pid=900000+i,thread='old-'+role,generation=4,empty=role=='reviewer') for i,role in enumerate(('thinker','doer','reviewer'))}
        def save():write_json(self.root_runtime/'registry.json',self.rows);return self.rows
        self.adapter.slots.save=save
        self.adapter.slots.backends={role:SimpleNamespace(active=None,error=None,thread=row['thread'],generation=4,phase='read',workspace=self.workspace,inputs=self.inputs) for role,row in self.rows.items()}
        scope=dict(repo=str(self.workspace),request={'text':'synthetic scope'},key='runtime')
        token=capability(self.store,'owner',scope);self.adapter.thinker_capability_hash=digest(token.encode());self.store.db.execute('UPDATE capabilities SET enabled=0')
        authority={name:{} for name in SECTIONS};authority.update(questions_answers={'pending':[]},inflight_uncertain=[],next_action={'human_gate':False})
        artifact=self.root/'original.txt';artifact.write_text('synthetic preserved original')
        cp=Checkpoint(self.root/'checkpoint.json',self.root);cp.save(authority,['original.txt'])
        self.adapter.checkpoint=lambda *_:cp;self.adapter.owner_checkpoint=lambda:cp;self.adapter.prepare_context=lambda *_:SimpleNamespace()
        self.operator.key_path.write_text('synthetic operator key')
        self.store.db.commit()
        self.binding.update(source_hash=identity(tree(self.workspace)))
        self.resume=self.operator.finish(dict(action='checkpoint-runtime',binding=self.binding))
        self.saved_path=Path(self.resume['receipt']);self.sha=self.resume['receipt_sha256']
        write_json(self.root_runtime/'supervisor.json',dict(pid=999999))

    def check(self):
        with patch('loop.native_resume.process_identity',return_value=None):return inspect_resume(self.cfg,self.saved_path,self.sha,self.controller)

    def test_checkpoint_stops_existing_supervisor_and_check_is_read_only(self):
        self.assertTrue(self.operator.stop_requested);before=self.store.db.execute('SELECT count(*) FROM events').fetchone()[0]
        value,raw=self.check();self.assertEqual(value['task'],self.tid);self.assertEqual(value['registry'],self.rows)
        self.assertEqual(before,self.store.db.execute('SELECT count(*) FROM events').fetchone()[0]);self.assertEqual(raw,(self.root_runtime/'registry.json').read_bytes())

    def test_resume_rejects_live_or_reused_process_before_startup(self):
        with patch('loop.native_resume.process_identity',return_value='reused-pid'):
            with self.assertRaises(Rejected):inspect_resume(self.cfg,self.saved_path,self.sha,self.controller)

    def test_resume_rejects_registry_source_and_input_drift(self):
        raw=(self.root_runtime/'registry.json').read_bytes();self.rows['doer']['generation']=99;write_json(self.root_runtime/'registry.json',self.rows)
        with self.assertRaises(Rejected):self.check()
        (self.root_runtime/'registry.json').write_bytes(raw);(self.inputs/'request').write_text('drift')
        with self.assertRaises(Rejected):self.check()

    def test_resume_rejects_unreconciled_maintenance(self):
        self.journal.append('MAINTENANCE_UNCERTAIN',dict(error='synthetic unresolved effect'))
        with self.assertRaises(Rejected):self.check()

    def test_resume_checks_original_checkpoint_bytes(self):
        (self.root/'original.txt').write_text('changed')
        with self.assertRaises(Rejected):self.check()

    def test_resume_intent_is_one_shot_after_preprocess_crash(self):
        args=SimpleNamespace(prepared=self.saved_path,prepared_sha256=self.sha,check=False,headless=True)
        with patch('loop.native_resume.process_identity',return_value=None),patch('loop.native.NativeAdapter',side_effect=RuntimeError('synthetic crash before any process')):
            with self.assertRaises(RuntimeError):run_resume(self.cfg,args,self.controller)
        self.assertEqual(self.journal.records()[-1]['milestone'],'RUNTIME_RESUME_FAILED')
        with self.assertRaises(Rejected):self.check()
        self.assertEqual(len([r for r in self.journal.records() if r['milestone']=='RUNTIME_RESUME_INTENT']),1)

    def test_resume_rejects_late_question_without_starting_processes(self):
        from loop.util import NeedsInput
        self.store.ask_question('owner','scope',7,'Synthetic pending correction')
        with self.assertRaises(NeedsInput):self.check()

    def test_resume_rejects_final_human_gate(self):
        self.store.transition(self.tid,'CANDIDATE_SEALED','REVIEWER_RUNNING');self.store.transition(self.tid,'REVIEWER_RUNNING','REVIEW_SEALED');self.store.transition(self.tid,'REVIEW_SEALED','REPORTING');self.store.transition(self.tid,'REPORTING','AWAITING_HUMAN')
        with self.assertRaises(Rejected):self.check()
