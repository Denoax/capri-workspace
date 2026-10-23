"""Temporary synthetic re-contract fixtures; mocked input never proves a human."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

import test_controller
from loop.engine import Engine
from loop.native_continuation import prepare_native_revision, claim_native_revision
from loop.util import Rejected, digest, identity, tree


class SyntheticTTY:
    def __init__(self, text):
        self.input=io.StringIO(text)
        self.output=io.StringIO()

    def write(self, text):return self.output.write(text)
    def flush(self):return None
    def readline(self):return self.input.readline()


class NativeContinuationTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp()
        self.repo=self.root/'fixtures/repo'
        self.repo.mkdir(parents=True)
        (self.repo/'module.py').write_text('value=1\n')
        for args in (['init','-q'],['add','.'],['-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','Synthetic baseline']):
            subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)
        self.config['authorized_repositories']=[str(self.repo)]
        self.engine=Engine(self.store,self.config)
        self.tid=self.engine.submit(test_controller.proposal(),self.repo,
            {'text':'SYNTHETIC original request; no human origin claim'},'owner','key')['task']
        self.candidate=self.root/'candidate'
        shutil.copytree(self.repo,self.candidate,ignore=shutil.ignore_patterns('.git'))
        self.store.transition(self.tid,'READY','DOER_RUNNING',candidate=str(self.candidate))
        self.store.transition(self.tid,'DOER_RUNNING','BLOCKED',outcome='UNVERIFIED')
        self.original=self.store.task(self.tid)
        self.controller=self.root/'maintenance-controller'
        self.controller.mkdir()
        (self.controller/'native.txt').write_text('SYNTHETIC source')
        self.instruction=self.root/'correction.md'
        self.text='SYNTHETIC scoped native continuation; preserve exact requirements.'
        self.instruction.write_text(self.text+'\n')
        self.prior=self.root/'prior-roles'
        self.prior.mkdir()
        self.registry=self.prior/'registry.json'
        self.registry.write_text(json.dumps({r:{'pid':900000+i} for i,r in enumerate(('thinker','doer','reviewer'))}))
        self.binding=dict(home=str(self.root),controller_hash=identity(tree(self.controller)),
            workflow_hash=identity(self.config),task=self.tid,version=self.original['version'],
            generation=self.original['generation'],packet_hash=self.original['content_hash'],
            candidate=str(self.candidate),candidate_hash=identity(tree(self.candidate)),
            correction_file=str(self.instruction),correction_sha256=digest(self.text.encode()),
            registry=str(self.registry),registry_sha256=digest(self.registry.read_bytes()),
            materials=[dict(name='CONTINUATION.md',path=str(self.instruction),sha256=digest(self.instruction.read_bytes()))])

    def prepare(self, text=None, check_only=False):
        with patch('loop.native_continuation.process_identity',return_value=None), \
             patch('loop.native_continuation.require_human_tty',
                 return_value=contextlib.nullcontext(SyntheticTTY((text if text is not None else self.text)+'\n'))), \
             patch('loop.cli.start_service',side_effect=AssertionError('No legacy service')), \
             patch('loop.cli.thinker_cycle',side_effect=AssertionError('No legacy inference')):
            return prepare_native_revision(self.store,self.engine,self.binding,self.controller,check_only=check_only)

    def test_check_only_never_reads_input_or_commits_recontract(self):
        with patch('loop.native_continuation.require_human_tty',side_effect=AssertionError('No input in check')), \
             patch('loop.native_continuation.process_identity',return_value=None):
            result=prepare_native_revision(self.store,self.engine,self.binding,self.controller,check_only=True)
        self.assertEqual(result['status'],'NATIVE_RECONTRACT_CHECKED')
        self.assertEqual(self.store.task(self.tid),self.original)
        self.assertIsNone(self.store.recontract_receipt(self.tid))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)

    def test_wrong_or_unavailable_foreground_input_preserves_hold(self):
        with self.assertRaisesRegex(Rejected,'instruction did not match'):
            self.prepare('SYNTHETIC different scope')
        with patch('loop.native_continuation.process_identity',return_value=None), \
             patch('loop.native_continuation.require_human_tty',side_effect=Rejected('No actual terminal')):
            with self.assertRaisesRegex(Rejected,'terminal'):
                prepare_native_revision(self.store,self.engine,self.binding,self.controller)
        self.assertEqual(self.store.task(self.tid),self.original)

    def test_preparation_reuses_core_lineage_material_and_idempotent_receipt(self):
        result=self.prepare()
        self.assertEqual(result['model_dispatch'],'NOT_STARTED')
        self.assertEqual(result['legacy_service'],'NOT_STARTED')
        self.assertEqual(self.store.task(self.tid)['state'],'SUPERSEDED')
        receipt=json.loads(Path(result['receipt']).read_text())
        saved=self.store.recontract_receipt(self.tid)
        self.assertEqual(receipt['prepared'],saved)
        self.assertEqual(saved['lineage']['preserved_requirements'],self.original['packet']['requirements'])
        self.assertEqual(saved['lineage']['prior_candidate_files'],tree(self.candidate))
        self.assertEqual((Path(receipt['material_root'])/'CONTINUATION.md').read_bytes(),self.instruction.read_bytes())
        with patch('loop.native_continuation.process_identity',return_value=None), \
             patch('loop.native_continuation.require_human_tty',side_effect=AssertionError('Do not repeat input')):
            again=prepare_native_revision(self.store,self.engine,self.binding,self.controller)
        self.assertEqual(result,again)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='HUMAN_RECONTRACT'").fetchone()[0],1)

    def test_core_derived_owner_can_be_claimed_only_once_without_a_model_job(self):
        result=self.prepare()
        with patch('loop.native_continuation.process_identity',return_value=None):
            saved=claim_native_revision(self.store,self.engine,result['receipt'],self.controller)
            self.assertEqual(saved['lineage']['successor_owner'],result['successor_owner'])
            with self.assertRaisesRegex(Rejected,'already started'):
                claim_native_revision(self.store,self.engine,result['receipt'],self.controller)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='RECONTRACT_THINKER_INTENT'").fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)

    def test_clipboard_padding_is_preserved_in_actual_core_correction(self):
        entered=self.text+' \t'
        result=self.prepare(entered)
        saved=self.store.recontract_receipt(self.tid)
        self.assertEqual(saved['lineage']['correction'],entered)
        with patch('loop.native_continuation.process_identity',return_value=None), \
             patch('loop.native_continuation.require_human_tty',side_effect=AssertionError('Do not repeat input')):
            again=prepare_native_revision(self.store,self.engine,self.binding,self.controller)
        self.assertEqual(result,again)
        self.assertEqual(json.loads(Path(result['receipt']).read_text())['prepared'],saved)

    def test_binding_or_live_process_drift_rejects_before_input(self):
        with patch('loop.native_continuation.process_identity',return_value='REUSED'), \
             patch('loop.native_continuation.require_human_tty',side_effect=AssertionError('No input after drift')):
            with self.assertRaisesRegex(Rejected,'PID exists'):
                prepare_native_revision(self.store,self.engine,self.binding,self.controller)
        self.binding['version']-=1
        with self.assertRaisesRegex(Rejected,'version changed'):
            self.prepare(check_only=True)
        self.assertEqual(self.store.task(self.tid),self.original)

    def test_post_preparation_material_drift_cannot_claim_owner(self):
        result=self.prepare()
        receipt=json.loads(Path(result['receipt']).read_text())
        (Path(receipt['material_root'])/'CONTINUATION.md').write_text('SYNTHETIC tamper')
        with patch('loop.native_continuation.process_identity',return_value=None):
            with self.assertRaisesRegex(Rejected,'material drift'):
                claim_native_revision(self.store,self.engine,result['receipt'],self.controller)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='RECONTRACT_THINKER_INTENT'").fetchone()[0],0)


class ProductContinuationTests(NativeContinuationTests):
    def product(self):
        from types import SimpleNamespace
        from loop.native_continuation import PreparedNativeContinuation
        rows={r:dict(pid=900000+i,thread='old-'+r,generation=3,empty=(r!='doer'))
              for i,r in enumerate(('thinker','doer','reviewer'))}
        self.registry.write_text(json.dumps(rows))
        self.binding['registry_sha256']=digest(self.registry.read_bytes())
        config=dict(roles={r:dict(workspace=str(self.candidate),inputs=str(self.root/'inputs')) for r in rows})
        self.binding['config_hash']=identity(config)
        prepared=self.prepare()
        calls=[];backends={}
        def start(role,workspace,inputs,controller,**kw):
            calls.append((role,kw))
            backends[role]=SimpleNamespace(thread='new-'+role,generation=kw['generation'],phase='read')
        def restore(role,workspace,inputs,controller,**kw):
            calls.append((role,kw))
            backends[role]=SimpleNamespace(thread='old-'+role,generation=4,phase='read')
        slots=SimpleNamespace(root=self.prior,backends=backends,start_role=start,restore_saved_role=restore,save=lambda:rows)
        adapter=SimpleNamespace(slots=slots,register_thinker=lambda *args:None)
        product=PreparedNativeContinuation(self.store,self.engine,adapter,config,prepared['receipt'],prepared['receipt_sha256'],self.controller)
        return product,calls,prepared

    def test_product_claim_once_restores_slot_and_keeps_fresh_reviewer(self):
        product,calls,prepared=self.product()
        with patch('loop.native_continuation.process_identity',return_value=None):
            product.launch(self.candidate,self.root/'inputs','synthetic-token',self.root/'intake.sock')
            with self.assertRaises(Rejected):
                product.launch(self.candidate,self.root/'inputs','synthetic-token',self.root/'intake.sock')
        self.assertEqual([r for r,_ in calls],['thinker','doer','reviewer'])
        self.assertIn('frozen_registry',calls[1][1])
        self.assertNotIn('prior',calls[2][1])
        self.assertEqual(calls[2][1]['phase'],'read')
        self.assertEqual(product.adapter.prepared_hash,prepared['receipt_sha256'])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM events WHERE kind='RECONTRACT_THINKER_INTENT'").fetchone()[0],1)

    def test_product_config_drift_cannot_claim_or_start(self):
        product,calls,_=self.product();product.config['changed']=True
        with patch('loop.native_continuation.process_identity',return_value=None):
            with self.assertRaisesRegex(Rejected,'configuration drift'):product.check()
        self.assertEqual(calls,[])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM events WHERE kind='RECONTRACT_THINKER_INTENT'").fetchone()[0],0)

    def test_product_live_supervisor_blocks_launch(self):
        product,calls,_=self.product()
        (self.prior/'supervisor.json').write_text(json.dumps(dict(pid=777)))
        with patch('loop.native_continuation.process_identity',side_effect=lambda pid:'live' if pid==777 else None):
            with self.assertRaisesRegex(Rejected,'supervisor still exists'):product.check()
        self.assertEqual(calls,[])

    def test_product_partial_start_cannot_automatically_retry(self):
        product,calls,_=self.product()
        product.adapter.slots.start_role=lambda *a,**kw: (_ for _ in ()).throw(Rejected('synthetic startup failure'))
        with patch('loop.native_continuation.process_identity',return_value=None):
            with self.assertRaisesRegex(Rejected,'startup failure'):product.launch(self.candidate,self.root/'inputs','token',None)
            with self.assertRaisesRegex(Rejected,'Already claimed'):product.check()

    def test_restart_requires_bound_owner_and_preserves_checked_arguments(self):
        product,_,_=self.product();product.owner='new-owner'
        from unittest.mock import Mock
        product.adapter.restart_backend=Mock(return_value='REHYDRATION_REQUIRED')
        with patch.object(self.store,'task',return_value=dict(owner='other')):
            with self.assertRaisesRegex(Rejected,'owner mismatch'):
                product.restart('task','doer','checkpoint',expected_pid=1,expected_process='process')
        product.adapter.restart_backend.assert_not_called()
        with patch.object(self.store,'task',return_value=dict(owner='new-owner')):
            self.assertEqual(product.restart('task','doer','checkpoint',expected_pid=1,expected_process='process'),'REHYDRATION_REQUIRED')
        product.adapter.restart_backend.assert_called_once_with('task','doer','checkpoint',expected_pid=1,expected_process='process')

class DeferredReviewTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp()
        self.engine = Engine(self.store, self.config)
        self.candidate = self.root / 'candidate'
        self.candidate.mkdir()
        (self.candidate / 'module.py').write_text('value=1\n')

    def test_defer_review_holds_exact_seal_and_default_still_reviews(self):
        task=self.store.create('sealed',dict(requirements=[]),'owner')
        self.store.transition(task['id'],'READY','DOER_RUNNING',candidate=str(self.candidate))
        seal=dict(files=tree(self.candidate),source_hash=identity(tree(self.candidate)))
        self.store.transition(task['id'],'DOER_RUNNING','CANDIDATE_SEALED',seal=json.dumps(seal))
        self.engine.verify_inputs=lambda _:None
        from unittest.mock import Mock
        self.engine.review=Mock()
        self.engine.finish_candidate(task['id'])
        self.engine.review.assert_called_once_with(task['id'])
        self.engine.review.reset_mock();self.engine.defer_review=True
        self.engine.finish_candidate(task['id'])
        self.engine.review.assert_not_called()
        self.assertEqual(self.store.task(task['id'])['state'],'CANDIDATE_SEALED')
        (self.candidate/'module.py').write_text('drift=1')
        with self.assertRaisesRegex(Rejected,'Exact sealed'):self.engine.finish_candidate(task['id'])
