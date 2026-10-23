"""Native admission controls: synthetic fixtures only; never genuine input or a model."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from unittest.mock import patch

import test_controller
from loop.engine import Engine
from loop.cli import _prepare_recontract, _claim_recontract_thinker
from loop.native_startup import ReadOnlyState, StartupJournal, preflight, prepare, check_owner_ledger
from loop.util import Rejected, digest, identity, tree, write_json


class SyntheticTTY(io.StringIO):
    def __init__(self,text):
        super().__init__();self.answer=text
    def readline(self,*_):return self.answer+'\n'


class StartupTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp()
        self.repo=self.root/'fixtures/repo';self.repo.mkdir(parents=True)
        (self.repo/'module.py').write_text('value=1\n')
        for args in (['init','-q'],['add','.'],['-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','SYNTHETIC original']):
            subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)
        self.config['authorized_repositories']=[str(self.repo)]
        self.engine=Engine(self.store,self.config)
        tid=self.engine.submit(test_controller.proposal(),self.repo,{'text':'Synthetic original'},'prior','prior')['task']
        self.candidate=self.root/'old-candidate';shutil.copytree(self.repo,self.candidate,ignore=shutil.ignore_patterns('.git'))
        self.store.transition(tid,'READY','DOER_RUNNING',candidate=str(self.candidate))
        self.store.transition(tid,'DOER_RUNNING','BLOCKED')
        _,_,lineage=_prepare_recontract(self.store,self.engine,tid,'SYNTHETIC prior foreground fixture')
        self.owner=lineage['successor_owner'];_claim_recontract_thinker(self.store,lineage,self.owner)
        claim=self.store.db.execute("select seq from events where kind='RECONTRACT_THINKER_INTENT'").fetchone()['seq']
        self.old_controller=self.root/'old-controller';self.old_controller.mkdir();(self.old_controller/'code.py').write_text('original')
        old_binding=dict(home=str(self.root),controller_hash=identity(tree(self.old_controller)),registry=str(self.root/'old-runtime/registry.json'),candidate_hash=identity(tree(self.candidate)))
        self.prepared=self.root/'predecessor.json';write_json(self.prepared,dict(binding=old_binding,prepared=self.store.recontract_receipt(tid)))
        self.registry=self.root/'old-runtime/registry.json';self.registry.parent.mkdir()
        write_json(self.registry,{role:dict(pid=900000+i,thread='old-'+role,generation=3,empty=True) for i,role in enumerate(('thinker','doer','reviewer'))})
        self.stopped=self.root/'stopped.json';write_json(self.stopped,dict(model_turns=0,prepared_owner=self.owner,role_slots=json.loads(self.registry.read_text()),error='Native Thinker scope/source/correction drift; explicit revision required'))
        self.code=self.root/'new-source';self.controller=self.code/'controller';self.controller.mkdir(parents=True);(self.controller/'native.py').write_text('new')
        self.binary=self.root/'codex';self.binary.write_text('synthetic binary')
        self.scope=self.root/'scope.txt';self.scope.write_text('SYNTHETIC exact new maintenance scope\n')
        self.cfg=dict(home=str(self.root),workflow=self.config,controller=str(self.controller),roles={role:dict(workspace=str(self.repo),inputs=str(self.root/'fixtures')) for role in ('thinker','doer','reviewer')},settings=dict(binary=str(self.binary),binary_sha256=digest(self.binary.read_bytes()),auth_file='/not-read',state_dir=str(self.root/'new-runtime')))
        self.binding=dict(schema_version=1,route='NATIVE_MAINTENANCE_RECOVERY',operation='synthetic-startup',home=str(self.root),config_hash=identity(self.cfg),controller=str(self.controller),controller_hash=identity(tree(self.controller)),source_hash=identity(tree(self.code)),predecessor_receipt=self.file(self.prepared),predecessor_controller=str(self.old_controller),registry=self.file(self.registry),stopped_launch=self.file(self.stopped),owner=self.owner,claim_seq=claim,materials=[],scope=self.file(self.scope),workspace=str(self.root/'workspace/new'),inputs=str(self.root/'inputs/new'))

    def file(self,path):return dict(path=str(path),sha256=digest(path.read_bytes()))

    def check(self):
        with patch('loop.native_startup.process_identity',return_value=None),patch('shutil.which',side_effect=lambda name:name):
            return preflight(self.cfg,self.binding,self.controller)

    def test_read_only_preflight_preserves_claims_events_capabilities_and_destinations(self):
        before=self.store.db.execute('select count(*) from events').fetchone()[0]
        with patch('loop.native_startup.Store',side_effect=AssertionError('Store initializer forbidden during check')):
            result=self.check()
        self.assertEqual(result['owner'],self.owner)
        self.assertEqual(before,self.store.db.execute('select count(*) from events').fetchone()[0])
        for key in ('workspace','inputs'):self.assertFalse(Path(self.binding[key]).exists())
        self.assertFalse(Path(self.cfg['settings']['state_dir']).exists())
        self.assertEqual(1,self.store.db.execute("select count(*) from events where kind='RECONTRACT_THINKER_INTENT'").fetchone()[0])

    def test_read_only_state_refuses_sql_mutation_and_missing_state(self):
        with ReadOnlyState(self.root) as readonly:
            with self.assertRaises(sqlite3.OperationalError):readonly.db.execute("delete from events")
        missing=self.root/'missing'
        with self.assertRaises(sqlite3.OperationalError):ReadOnlyState(missing)
        self.assertFalse(missing.exists())

    def test_foreign_unknown_and_interrupted_owner_records_are_not_discarded(self):
        old=self.registry.parent/'thinker';old.mkdir();path=old/'owner-binding.json';path.write_text('{"unattributed":true}')
        with self.assertRaises(Rejected):self.check()
        path.write_text('{"owner":"previous","preserve":"bytes"}');prior=path.read_bytes();self.check();self.assertEqual(path.read_bytes(),prior)
        folder=Path(check_owner_ledger(self.registry.parent,self.owner)['directory']);folder.mkdir(parents=True)
        (folder/'owner-context.json').write_text('{}')
        with self.assertRaises(Rejected):self.check()

    def test_uncertain_turn_or_occupied_thread_cannot_use_pre_model_route(self):
        self.store.event(None,'NATIVE_OWNER_DISPATCH',dict(owner=self.owner,thread='lost-turn'))
        with self.assertRaises(Rejected):self.check()

    def test_pid_reuse_registry_source_and_pending_correction_reject(self):
        with patch('loop.native_startup.process_identity',return_value='reused'),patch('shutil.which',return_value='present'):
            with self.assertRaises(Rejected):preflight(self.cfg,self.binding,self.controller)
        (self.controller/'native.py').write_text('drift')
        with self.assertRaises(Rejected):self.check()

    def test_snapshot_collision_is_held_without_overwrite(self):
        p=Path(self.binding['workspace']);p.mkdir(parents=True);(p/'keep').write_text('keep')
        with self.assertRaises(Rejected):self.check()
        self.assertEqual((p/'keep').read_text(),'keep')

    def test_same_operation_different_parameters_and_duplicate_intent_reject(self):
        j=StartupJournal(self.store,'one',{'source':'a'})
        j.append('PREFLIGHT_VALIDATED');j.append('LAUNCH_INTENT')
        with self.assertRaises(Rejected):j.append('LAUNCH_INTENT')
        with self.assertRaises(Rejected):StartupJournal(self.store,'one',{'source':'b'}).records()
        self.assertEqual([r['milestone'] for r in j.records()],['PREFLIGHT_VALIDATED','LAUNCH_INTENT'])

    def test_journal_composes_atomic_scope_events_and_rolls_back_on_failure(self):
        j=StartupJournal(self.store,'atomic',{})
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                j.append('PREFLIGHT_VALIDATED');j.append('SCOPE_CAPTURED');raise RuntimeError('synthetic crash')
        self.assertEqual(j.records(),[])

    def test_synthetic_foreground_prepares_once_never_reclaims_or_starts_model(self):
        args=dict(config=self.cfg,binding=self.binding,controller=self.controller)
        with patch('loop.native_startup.process_identity',return_value=None),patch('shutil.which',side_effect=lambda name:name),patch('loop.native_startup.require_human_tty',return_value=contextlib.nullcontext(SyntheticTTY('SYNTHETIC exact new maintenance scope'))):
            result=prepare(**args)
        self.assertEqual(result['status'],'NATIVE_MAINTENANCE_PREPARED')
        with patch('loop.native_startup.process_identity',return_value=None),patch('shutil.which',side_effect=lambda name:name),patch('loop.native_startup.require_human_tty',side_effect=AssertionError('Do not repeat captured fixture input')):
            again=prepare(**args)
        self.assertEqual(result,again)
        self.assertEqual(1,self.store.db.execute("select count(*) from events where kind='RECONTRACT_THINKER_INTENT'").fetchone()[0])
        self.assertEqual(0,self.store.db.execute('select count(*) from capabilities').fetchone()[0])

    def test_capability_is_held_atomically_before_any_role_process(self):
        from loop.native import NativeAdapter
        adapter=NativeAdapter.__new__(NativeAdapter);adapter.store=self.store
        token=adapter.create_held_capability(self.owner,dict(repo=str(self.repo),request={'text':'synthetic scope'},key='one'))
        self.assertIsInstance(token,str)
        self.assertEqual(self.store.db.execute('select enabled from capabilities').fetchone()['enabled'],0)
        self.assertEqual(self.store.db.execute('select count(*) from sessions').fetchone()[0],0)

    def test_cleanup_revokes_even_after_a_pending_human_question(self):
        from loop.native import NativeAdapter
        from types import SimpleNamespace
        adapter=NativeAdapter.__new__(NativeAdapter);adapter.store=self.store
        adapter.create_held_capability(self.owner,dict(repo=str(self.repo),request={},key='one'))
        self.store.ask_question(self.owner,'one',7,'SYNTHETIC pending human question')
        closed=[];adapter.slots=SimpleNamespace(close=lambda:closed.append(True));adapter.close()
        self.assertEqual(closed,[True]);self.assertEqual(self.store.db.execute('select enabled from capabilities').fetchone()['enabled'],0)

    def test_capability_creation_failure_rolls_back_without_authority_leak(self):
        from loop.native import NativeAdapter
        adapter=NativeAdapter.__new__(NativeAdapter);adapter.store=self.store
        with patch.object(self.store,'event',side_effect=RuntimeError('SYNTHETIC crash')):
            with self.assertRaises(RuntimeError):adapter.create_held_capability(self.owner,dict(repo=str(self.repo),request={},key='one'))
        self.assertEqual(self.store.db.execute('select count(*) from capabilities').fetchone()[0],0)

    def test_concurrent_duplicate_launch_intent_records_exactly_once(self):
        import threading
        from loop.store import Store
        barrier=threading.Barrier(2);results=[]
        def contender():
            store=Store(self.root)
            try:
                barrier.wait(timeout=3)
                try:StartupJournal(store,'concurrent',{}).append('LAUNCH_INTENT');results.append('recorded')
                except Rejected:results.append('held')
            finally:store.close()
        workers=[threading.Thread(target=contender) for _ in range(2)]
        for worker in workers:worker.start()
        for worker in workers:worker.join(timeout=5);self.assertFalse(worker.is_alive())
        self.assertEqual(sorted(results),['held','recorded'])

    def test_source_change_after_preflight_is_rejected_before_authority_commit(self):
        fixture=self
        class DriftTTY(SyntheticTTY):
            def readline(self,*args):
                (fixture.controller/'native.py').write_text('SYNTHETIC concurrent source change')
                return super().readline(*args)
        with patch('loop.native_startup.process_identity',return_value=None),patch('shutil.which',side_effect=lambda name:name),patch('loop.native_startup.require_human_tty',return_value=contextlib.nullcontext(DriftTTY('SYNTHETIC exact new maintenance scope'))):
            with self.assertRaises(Rejected):prepare(self.cfg,self.binding,self.controller)
        self.assertEqual(self.store.db.execute("select count(*) from events where kind='NATIVE_STARTUP'").fetchone()[0],0)

    def test_pending_question_blocks_preflight_without_new_claim(self):
        from loop.util import NeedsInput
        self.store.ask_question(self.owner,'scope',7,'SYNTHETIC unresolved question')
        with self.assertRaises(NeedsInput):self.check()
        self.assertEqual(self.store.db.execute("select count(*) from events where kind='RECONTRACT_THINKER_INTENT'").fetchone()[0],1)

    def synthetic_prepared(self):
        with patch('loop.native_startup.process_identity',return_value=None),patch('shutil.which',side_effect=lambda name:name),patch('loop.native_startup.require_human_tty',return_value=contextlib.nullcontext(SyntheticTTY('SYNTHETIC exact new maintenance scope'))):
            return prepare(self.cfg,self.binding,self.controller)

    def run_fault(self,point):
        from types import SimpleNamespace
        import itertools
        import loop.native as native_module
        from loop.native_startup import run_recovery
        actual_adapter=native_module.NativeAdapter;prepared=self.synthetic_prepared();closed=[];calls=[]
        class Slots:
            def __init__(slots,settings):slots.root=Path(settings.state_dir);slots.root.mkdir(mode=0o700);slots.backends={};slots.mapping_changed=None
            def start_role(slots,role,workspace,inputs,controller,**kwargs):
                calls.append(role)
                if point=='partial-slots' and role=='doer':raise RuntimeError('SYNTHETIC partial slots')
                slots.backends[role]=SimpleNamespace(thread='synthetic-'+role,generation=kwargs['generation'],mcp=kwargs.get('mcp'),phase='read',runtime=slots.root/role/'runtime',clients=[] if point=='attachment' else [True],proc=SimpleNamespace(pid=900000+len(calls),poll=lambda:None),error=None)
            def save(slots):return {r:dict(thread=b.thread,generation=b.generation) for r,b in slots.backends.items()}
            def close(slots):closed.append(True)
        def adapter_factory(engine,settings,**kwargs):
            if point=='after-intent':raise RuntimeError('SYNTHETIC crash before slots')
            value=actual_adapter.__new__(actual_adapter);value.store=engine.store;value.engine=engine;value.settings=settings;value.slots=Slots(settings);value.context_states={};value.thinker_probe=lambda:(_ for _ in ()).throw(RuntimeError('SYNTHETIC lost turn/start response'));return value
        class Intake:
            def __init__(self,*args):self.path=self_root/'intake.sock'
            def start(self):pass
            def close(self):pass
        class Terminals:
            def __init__(self,*args,**kwargs):pass
            def sync(self,*args):pass
            def attach_command(self):return 'SYNTHETIC no terminal'
            def close(self):pass
        self_root=self.root;args=SimpleNamespace(prepared=Path(prepared['receipt']),prepared_sha256=prepared['receipt_sha256'],check=False,headless=True)
        with patch('loop.native_startup.process_identity',return_value=None),patch('shutil.which',side_effect=lambda name:name),patch('loop.native.NativeAdapter',side_effect=adapter_factory),patch('loop.native.NativeIntake',Intake),patch('loop.native.NativeTerminals',Terminals),patch('time.monotonic',side_effect=itertools.count(0,20).__next__):
            with self.assertRaises((RuntimeError,Rejected)):run_recovery(self.cfg,args,self.controller)
        rows=StartupJournal(self.store,self.binding['operation'],self.binding).records()
        self.assertEqual(rows[-1]['milestone'],'FAILED_OR_UNCERTAIN')
        self.assertEqual(self.store.db.execute("select count(*) from events where kind='RECONTRACT_THINKER_INTENT'").fetchone()[0],1)
        self.assertEqual(self.store.db.execute('select count(*) from capabilities where enabled=1').fetchone()[0],0)
        with patch('loop.native.NativeAdapter',side_effect=AssertionError('Must not start another process')):
            run_recovery(self.cfg,args,self.controller)
        return rows,calls,closed

    def test_crash_after_new_intent_before_slots_preserves_old_claim(self):
        rows,calls,closed=self.run_fault('after-intent');self.assertEqual(calls,[])

    def test_partial_slot_creation_revokes_capability_and_stays_held(self):
        rows,calls,closed=self.run_fault('partial-slots');self.assertEqual(calls,['thinker','doer']);self.assertEqual(closed,[True])

    def test_attachment_timeout_does_not_dispatch_a_probe(self):
        rows,calls,closed=self.run_fault('attachment');self.assertFalse(any(r['milestone']=='PROBE_DISPATCH_INTENT' for r in rows))

    def test_lost_probe_response_is_not_automatically_retried(self):
        rows,calls,closed=self.run_fault('lost-response');self.assertEqual(rows[-1]['details']['classification'],'EXECUTION_REQUIRES_RECONCILIATION')
