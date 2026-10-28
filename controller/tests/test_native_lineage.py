"""Scope-proposal fixtures only. No synthetic input proves a real operator."""
import copy
import json
from pathlib import Path
import unittest

import test_controller
import test_native_continuation as fixtures
from loop.cli import capture_human_answer
from loop.util import Rejected, NeedsInput, digest, identity, tree


class NativeLineageTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.NativeContinuationTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)

    def prepare(self):
        result=self.f.prepare()
        self.path=Path(result['receipt'])
        self.saved=self.f.store.recontract_receipt(self.f.tid)
        self.full=self.saved['lineage']
        keys=('parent_task','parent_packet_hash','revision','human_answers','human_corrections','correction',
              'prior_candidate','prior_candidate_files','recontract_operation','successor_owner')
        self.projected={k:self.full[k] for k in keys}
        self.projected['full_core_lineage']=dict(path=str(self.path),sha256=digest(self.path.read_bytes()),origin='ACTUAL_COMMITTED_CORE_FOREGROUND_RECONTRACT')
        return self.projected

    def submit(self,lineage=None,owner=None,key='successor'):
        return self.f.engine.submit(test_controller.proposal(),self.f.repo,
            dict(text='SYNTHETIC scoped continuation; full originals preserved',lineage=lineage or self.projected),
            owner or self.full['successor_owner'],key)

    def assert_no_successor(self):
        self.assertEqual(1,self.f.store.db.execute('SELECT count(*) FROM tasks').fetchone()[0])

    def test_reference_freeze_reuses_exact_core_and_source_without_duplicate_prose(self):
        self.prepare();before=copy.deepcopy(self.saved)
        result=self.submit();task=self.f.store.task(result['task']);packet=task['packet']
        self.assertEqual(packet['lineage'],self.projected)
        self.assertNotIn('lineage',packet['request'])
        self.assertEqual('/lineage',packet['request']['lineage_reference']['packet_pointer'])
        self.assertEqual(before,self.f.store.recontract_receipt(self.f.tid))
        self.assertEqual(self.f.original['packet']['source'],packet['source'])
        self.assertEqual(2,packet['task_revision'])
        self.assertLessEqual(len(json.dumps(packet).encode()),60000)
        inputs=self.f.engine.inputs(task['id'],'preflight')
        self.assertEqual((inputs/'recovery-source/module.py').read_bytes(),(self.f.candidate/'module.py').read_bytes())
        self.assertEqual(result['task'],self.submit()['task'])
        with self.assertRaises(Rejected):self.submit(key='duplicate-owner')

    def test_reference_rejects_changed_fields_or_receipt_without_creating_a_task(self):
        self.prepare()
        for changes in ({'correction':'forged'},{'revision':99},{'human_answers':[{'answer':'forged'}]},
                        {'prior_candidate_files':{}},{'extra':'unbound'}):
            with self.subTest(changes=changes),self.assertRaises(Rejected):self.submit({**self.projected,**changes})
        for changes in ({'sha256':'0'*64},{'path':str(self.f.root/'elsewhere.json')},{'origin':'MODEL_ASSERTION'}):
            modified=copy.deepcopy(self.projected);modified['full_core_lineage'].update(changes)
            with self.subTest(ref=changes),self.assertRaises(Rejected):self.submit(modified)
        self.assert_no_successor()

    def test_reference_rejects_artifact_tampering_and_symlinks(self):
        self.prepare();raw=self.path.read_bytes()
        value=json.loads(raw);value['prepared']['lineage']['correction']='forged'
        self.path.write_text(json.dumps(value))
        with self.assertRaises(Rejected):self.submit()
        self.path.write_bytes(raw);target=self.path.with_name('preserved-actual.json');self.path.rename(target);self.path.symlink_to(target)
        with self.assertRaises(Rejected):self.submit()
        self.assert_no_successor()

    def test_reference_cannot_skip_wrong_owner_parent_source_or_revision(self):
        self.prepare()
        with self.assertRaises(Rejected):self.submit(owner='other-owner')
        from loop.contract import validate
        packet=validate(test_controller.proposal(),self.f.repo,{'text':'SYNTHETIC'},self.f.engine.instructions(self.f.repo))
        packet.update(lineage=self.projected,task_revision=2)
        for changes in ({'task_revision':3},{'source':{**packet['source'],'head':'stale'}}):
            with self.subTest(changes=changes),self.assertRaises(Rejected):
                self.f.store.create('successor',{**packet,**changes},self.full['successor_owner'])
        self.f.store.transition(self.f.tid,'SUPERSEDED','BLOCKED')
        with self.assertRaises(Rejected):self.submit()
        self.assert_no_successor()

    def test_reference_preserves_pending_question_hold_and_exact_new_owner_answer(self):
        self.prepare();owner=self.full['successor_owner']
        q=self.f.store.ask_question(owner,'successor',2,'SYNTHETIC exact-label question?')
        with self.assertRaises(NeedsInput):self.submit()
        args={k:q[k] for k in ('question_id','owner','scope_key','task_id','revision','packet_hash')}
        capture_human_answer(self.f.store,**args,text='Return "Untitled"',origin='FOREGROUND_HUMAN_STDIN',source_ref='SYNTHETIC_SCOPE_PROPOSAL_NOT_HUMAN')
        result=self.submit();packet=self.f.store.task(result['task'])['packet']
        self.assertEqual('Return "Untitled"',packet['request']['human_answers'][0]['answer'])
        self.assertEqual(self.saved,self.f.store.recontract_receipt(self.f.tid))

    def test_full_inline_legacy_receipt_still_passes_exact_existing_checks(self):
        self.prepare();result=self.submit(self.full)
        self.assertEqual(self.full,self.f.store.task(result['task'])['packet']['lineage'])

    def test_complete_packet_budget_includes_lineage_appended_after_validation(self):
        # Enlarge only disposable recovery metadata. Original source stays tiny.
        index=0
        while len(json.dumps(tree(self.f.candidate)).encode())<33000:
            (self.f.candidate/(('a'*100)+str(index)+'.py')).write_text('synthetic=1\n');index+=1
        self.f.binding['candidate_hash']=identity(tree(self.f.candidate))
        self.prepare()
        with self.assertRaisesRegex(Rejected,'Complete frozen contract exceeds byte budget'):
            self.submit(self.full)
        self.assert_no_successor()
