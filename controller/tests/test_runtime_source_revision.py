"""New source authority over an immutable stopped checkpoint; zero model calls."""
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import test_native_resume
from loop.native_resume import (inspect_resume,inspect_source_revision,prepare_source_revision,
                                projected_source_revision,source_revision_line)
from loop.native_startup import StartupJournal
from loop.util import Rejected,digest,identity,tree,write_json


class RuntimeSourceRevisionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_native_resume.RuntimeResumeTests('test_checkpoint_stops_existing_supervisor_and_check_is_read_only')
        self.fixture.setUp();f=self.fixture
        f.cfg['controller']=str(f.controller)
        f.native_binding.update(operation='revision-fixture-parent',config_hash=identity(f.cfg))
        f.journal=StartupJournal(f.store,'revision-fixture-parent',f.native_binding)
        f.operator.journal=f.journal;f.binding['fixture_revision']=True
        f.resume=f.operator.finish(dict(action='checkpoint-runtime',binding=f.binding))
        self.parent_path=Path(f.resume['receipt']);self.parent_raw=self.parent_path.read_bytes()
        self.previous=f.root/'previous-config.json';write_json(self.previous,f.cfg)
        self.controller=f.root/'repaired/controller'
        shutil.copytree(f.controller,self.controller)
        code=self.controller/'loop/native_resume.py';code.parent.mkdir();code.write_text('synthetic approved module')
        self.config=dict(f.cfg,controller=str(self.controller))
        self.approval=f.root/'owner-plan.md';self.approval.write_text('synthetic owner-approved bounded maintenance')
        self.binding=dict(schema=1,operation='approved-source-revision',
            previous_config=self.file(self.previous),previous_receipt=self.file(self.parent_path),
            approval=self.file(self.approval),source_hash=identity(tree(self.controller.parent)),
            controller_hash=identity(tree(self.controller)),config_hash=identity(self.config))
        self.parent=json.loads(self.parent_raw)
        self.process_patch=patch('loop.native_resume.process_identity',return_value=None)
        self.process_patch.start()

    def tearDown(self):
        self.process_patch.stop();self.fixture.tearDown();self.fixture.doCleanups()

    def file(self,path):
        return dict(path=str(path),sha256=digest(path.read_bytes()))

    def check(self):
        return inspect_source_revision(self.config,self.binding,self.controller)

    def prepare(self):
        return prepare_source_revision(self.fixture.store,self.config,self.binding,self.controller,
                                       source_revision_line(self.binding,self.parent))

    def test_check_only_preserves_parent_bytes_and_database(self):
        f=self.fixture;before=f.store.db.execute('SELECT count(*) FROM events').fetchone()[0]
        parent,_,records=self.check()
        self.assertEqual(parent,self.parent);self.assertEqual(records,[])
        self.assertEqual(before,f.store.db.execute('SELECT count(*) FROM events').fetchone()[0])
        self.assertEqual(self.parent_raw,self.parent_path.read_bytes())

    def test_new_authority_validates_without_rewriting_parent_or_claiming_new_checkpoint(self):
        result=self.prepare();path=Path(result['receipt'])
        saved,_=inspect_resume(self.config,path,result['receipt_sha256'],self.controller)
        self.assertEqual(saved['route'],'CHECKED_NATIVE_SOURCE_REVISION')
        self.assertEqual(saved['source_before_stop'],self.parent['source_before_stop'])
        self.assertEqual(saved['roles'],self.parent['roles'])
        self.assertEqual(saved['registry'],self.parent['registry'])
        self.assertEqual(self.parent_raw,self.parent_path.read_bytes())
        rows=StartupJournal(self.fixture.store,self.binding['operation'],saved['maintenance_binding']).records()
        self.assertEqual(rows,[])  # No fabricated RUNTIME_CHECKPOINTED milestone.

    def test_old_receipt_cannot_be_used_to_launch_new_source(self):
        with self.assertRaisesRegex(Rejected,'binding changed'):
            inspect_resume(self.config,self.parent_path,digest(self.parent_raw),self.controller)

    def test_wrong_confirmation_records_no_authority(self):
        with self.assertRaisesRegex(Rejected,'foreground'):
            prepare_source_revision(self.fixture.store,self.config,self.binding,self.controller,'yes')
        self.assertEqual(self.check()[2],[])

    def test_revision_cannot_change_models_settings_or_home(self):
        self.config['settings']=dict(self.config['settings'],model='different-model')
        self.binding['config_hash']=identity(self.config)
        with self.assertRaisesRegex(Rejected,'cannot change'):
            self.check()

    def test_revision_cannot_change_other_protected_core(self):
        (self.controller/'loop/store.py').write_text('unapproved change')
        self.binding.update(source_hash=identity(tree(self.controller.parent)),controller_hash=identity(tree(self.controller)))
        with self.assertRaisesRegex(Rejected,'exceeds'):
            self.check()

    def test_original_unresolved_maintenance_still_blocks_new_source(self):
        self.fixture.journal.append('MAINTENANCE_UNCERTAIN',dict(error='unkeyed original hold'))
        with self.assertRaisesRegex(Rejected,'Uncertain maintenance'):
            self.check()

    def test_preparation_and_restart_intents_remain_one_shot(self):
        result=self.prepare()
        with self.assertRaisesRegex(Rejected,'already recorded'):
            self.prepare()
        path=Path(result['receipt']);saved=json.loads(path.read_text())
        StartupJournal(self.fixture.store,self.binding['operation'],saved['maintenance_binding']).append(
            'RUNTIME_RESUME_INTENT',dict(receipt_sha256=result['receipt_sha256']))
        with self.assertRaisesRegex(Rejected,'intent consumed'):
            inspect_resume(self.config,path,result['receipt_sha256'],self.controller)

    def test_approval_document_drift_is_rejected(self):
        self.approval.write_text('changed')
        with self.assertRaises(Rejected):
            self.check()

    def test_projected_receipt_without_committed_authority_is_rejected(self):
        saved=projected_source_revision(self.parent,self.binding,999999)
        path=self.fixture.root/'forged.json';write_json(path,saved)
        with self.assertRaisesRegex(Rejected,'foreground authority'):
            inspect_resume(self.config,path,digest(path.read_bytes()),self.controller)

    def test_malformed_source_revision_has_a_typed_rejection(self):
        saved=projected_source_revision(self.parent,self.binding,999999)
        saved['source_revision']={}
        path=self.fixture.root/'malformed.json';write_json(path,saved)
        with self.assertRaisesRegex(Rejected,'source-revision reference'):
            inspect_resume(self.config,path,digest(path.read_bytes()),self.controller)

    def test_edited_projection_is_rejected_even_with_correct_new_hash(self):
        result=self.prepare();path=Path(result['receipt']);saved=json.loads(path.read_text())
        saved['scope']={'text':'invented successor authority'};write_json(path,saved)
        with self.assertRaisesRegex(Rejected,'foreground authority'):
            inspect_resume(self.config,path,digest(path.read_bytes()),self.controller)

    def test_current_task_human_gate_cannot_be_crossed(self):
        f=self.fixture
        for old,new in [('CANDIDATE_SEALED','REVIEWER_RUNNING'),('REVIEWER_RUNNING','REVIEW_SEALED'),
                        ('REVIEW_SEALED','REPORTING'),('REPORTING','AWAITING_HUMAN')]:
            f.store.transition(f.tid,old,new)
        with self.assertRaises(Rejected):
            self.check()

    def test_separate_security_scope_admits_only_its_exact_extra_modules(self):
        self.binding.update(schema=2,additional_modules=[
            'controller/loop/cli.py','controller/loop/contract.py','controller/loop/store.py','tools/ci_bwrap_profile.py'])
        (self.controller/'loop/store.py').write_text('synthetic separately approved module')
        self.binding.update(source_hash=identity(tree(self.controller.parent)),controller_hash=identity(tree(self.controller)))
        self.check()
        self.assertIn('approved source/state security fixes',source_revision_line(self.binding,self.parent))

    def test_security_scope_cannot_add_unrelated_modules(self):
        self.binding.update(schema=2,additional_modules=[
            'controller/loop/adapter.py','controller/loop/cli.py','controller/loop/contract.py','controller/loop/store.py'])
        with self.assertRaisesRegex(Rejected,'separately approved'):
            self.check()
