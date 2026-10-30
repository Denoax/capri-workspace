"""Synthetic admission controls. No authentication, model or actual task writes."""
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import test_controller
from test_native_stopped import fixture
from loop.native_stopped import commit_fence, prepare_qualification, scope_line
from loop import native_qualification as qualification
from loop.native_packet import prepare
from loop.util import Rejected, digest, identity, tree


class QualificationTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp(); fixture(self)
        Path(self.config['settings']['auth_file']).write_text('synthetic auth placeholder; never used')
        self.home=self.root/'a4'; runtime=str(self.home/'r')
        self.target=json.loads(json.dumps(self.config));self.target.update(home=str(self.home),controller=str(self.controller))
        self.target['settings']['state_dir']=runtime
        self.target['workflow'].update(notes=str(self.home/'notes'),authorized_repositories=[str(self.home/'fixtures/source')])
        self.target['roles']={r:dict(workspace=str(self.home/'slots'/r/'workspace'),inputs=str(self.home/'slots'/r/'inputs')) for r in ('thinker','doer','reviewer')}
        self.folder=self.root/'launch-data';self.folder.mkdir()
        def put(name,value):
            p=self.folder/name;p.write_text(json.dumps(value));return dict(path=str(p),sha256=digest(p.read_bytes()))
        self.put=put
        self.binding=dict(schema=1,kind=qualification.KIND,case=put('case.json',asdict(self.case)),
            recovery_controller=str(self.controller),target_controller_hash=identity(tree(self.controller)),
            target_config=put('target.json',self.target))
        owner=str(uuid.uuid5(uuid.NAMESPACE_URL,'capri-qualification:'+self.case.key()+':'+runtime))
        request=dict(text=scope_line(self.case,runtime),origin='DERIVED_DISTINCT_FOREGROUND_QUALIFICATION',human_answers=[])
        packet=self.store.task(self.tid)['packet'];core=json.loads(self.case.prepared.read())['binding']['predecessor_receipt']
        raw={'REFERENCE_LED_DESIGN.md':b'Preserve real source; nonvisual.',
             'preserved-requirements.json':json.dumps(packet['requirements']).encode(),
             'original-request.json':json.dumps(packet['request']).encode(),
             'old-packet.json':json.dumps(packet).encode(),
             'successor-request.json':json.dumps(request).encode(),
             'historical-prepared.json':self.case.prepared.read(),
             'full-prepared.json':Path(core['path']).read_bytes()}
        classes={n:dict(category='history',reason='Exact historical original retained',sha256=digest(v)) for n,v in raw.items()}
        classes['REFERENCE_LED_DESIGN.md'].update(category='current',reason='Current nonvisual policy')
        index=prepare(self.folder/'context',originals=raw,classifications=classes,requirements=packet['requirements'],
            proposal=dict(requirements=packet['requirements'],scope_note='Preserve exact SCOPE; current source preparation is distinct.'),
            current_request=request,answers=[],binding=dict(owner=owner,repo_source_hash=self.case.target_source,
                controller_source_hash=self.case.target_source,scope_hash=digest(request['text'].encode()),
                active_originals=['REFERENCE_LED_DESIGN.md']))
        for p in (self.folder/'context').iterdir():raw['current-context/'+p.name]=p.read_bytes()
        materials=[]
        for name,data in raw.items():
            p=self.folder/'material'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            materials.append(dict(name=name,path=str(p),sha256=digest(data)))
        self.binding.update(materials=materials,request=request,context_packet=dict(path=str(self.folder/'context/INDEX.json'),sha256=digest((self.folder/'context/INDEX.json').read_bytes())))

    def prepared(self):
        commit_fence(self.store,self.config,self.case,self.controller)
        prepare_qualification(self.store,self.config,self.case,self.controller,str(self.home/'r'),scope_line(self.case,str(self.home/'r')))
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    def check(self,**kwargs):return qualification.check(self.config,self.binding,self.controller,**kwargs)

    def test_unprepared_public_check_is_pure_and_cannot_start_anything(self):
        p=self.folder/'binding.json';p.write_text(json.dumps(self.binding))
        before={str(f):digest(f.read_bytes()) for f in self.root.rglob('*') if f.is_file()}
        with patch('subprocess.Popen',side_effect=AssertionError('process')),patch('socket.socket',side_effect=AssertionError('socket')),patch('loop.store.Store.__init__',side_effect=AssertionError('initializer')),patch('sys.stdout',new_callable=io.StringIO) as out:
            qualification.run_cli(self.config,SimpleNamespace(binding=p,check=True),self.controller)
        self.assertEqual(json.loads(out.getvalue())['status'],'FRESH_QUALIFICATION_NEEDS_FOREGROUND')
        self.assertEqual(before,{str(f):digest(f.read_bytes()) for f in self.root.rglob('*') if f.is_file()})
        self.assertFalse(self.home.exists())

    def test_launch_requires_exact_preparation_and_never_replays_old_scope(self):
        with self.assertRaisesRegex(Rejected,'preparation'):self.check()
        self.prepared();self.assertEqual(self.check()['status'],'FRESH_QUALIFICATION_LAUNCH_CHECKED')

    def test_intent_is_committed_once_before_any_fresh_home_or_process(self):
        self.prepared();old=self.store.task(self.tid)
        result=qualification.commit_launch(self.store,self.config,self.binding,self.controller)
        self.assertGreater(result['admission_event'],self.case.uncertain_event)
        self.assertFalse(self.home.exists());self.assertEqual(self.store.task(self.tid),old)
        with self.assertRaisesRegex(Rejected,'consumed'):qualification.commit_launch(self.store,self.config,self.binding,self.controller)

    def test_crash_before_intent_commit_rolls_back_and_allows_exact_admission(self):
        self.prepared();before=self.store.db.execute('select count(*) from events').fetchone()[0]
        original=self.store.event
        def crash(*a,**kw):original(*a,**kw);raise RuntimeError('before commit')
        with patch.object(self.store,'event',side_effect=crash),self.assertRaises(RuntimeError):qualification.commit_launch(self.store,self.config,self.binding,self.controller)
        self.assertEqual(self.store.db.execute('select count(*) from events').fetchone()[0],before)
        self.assertEqual(self.check()['status'],'FRESH_QUALIFICATION_LAUNCH_CHECKED')

    def test_lost_response_after_intent_cannot_relaunch_even_without_a_home(self):
        self.prepared();qualification.commit_launch(self.store,self.config,self.binding,self.controller)
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        with patch('subprocess.Popen',side_effect=AssertionError('replay')),self.assertRaisesRegex(Rejected,'consumed'):qualification.launch(self.config,self.binding,self.controller,SimpleNamespace(headless=False))
        self.assertFalse(self.home.exists())

    def test_pending_question_blocks_atomic_admission(self):
        self.prepared();self.store.ask_question(self.case.owner,'scope',1,'Actual unresolved behavior?')
        with self.assertRaises(Rejected):qualification.commit_launch(self.store,self.config,self.binding,self.controller)

    def test_pid_reuse_or_endpoint_prevents_dispatch_without_signalling(self):
        self.prepared()
        with patch('loop.native_stopped.process_identity',return_value='reused'),patch('os.kill',side_effect=AssertionError('signal')),self.assertRaises(Rejected):self.check()
        p=Path(self.case.runtime)/'doer.sock';p.write_text('foreign endpoint')
        with self.assertRaises(Rejected):self.check()

    def test_stale_case_source_or_config_holds_before_effects(self):
        self.prepared()
        for key in ('case','target_config'):
            p=Path(self.binding[key]['path']);data=p.read_bytes();p.write_bytes(data+b' ')
            with self.subTest(key=key),self.assertRaises(Rejected):self.check()
            p.write_bytes(data)
        broken={**self.binding,'target_controller_hash':'0'*64}
        with self.assertRaises(Rejected):qualification.check(self.config,broken,self.controller)

    def test_rebound_wrong_profile_scope_or_history_is_rejected(self):
        self.prepared()
        target=json.loads(json.dumps(self.target));target['settings']['efforts']={'thinker':'low','doer':'medium','reviewer':'high'}
        broken={**self.binding,'target_config':self.put('wrong-profile.json',target)}
        with self.assertRaises(Rejected):qualification.check(self.config,broken,self.controller)
        broken={**self.binding,'request':{**self.binding['request'],'text':'old scope220'}}
        with self.assertRaises(Rejected):qualification.check(self.config,broken,self.controller)
        p=Path(self.binding['materials'][0]['path']);p.write_bytes(b'changed original')
        with self.assertRaises(Rejected):self.check()

    def test_partial_home_or_reused_destination_is_never_overwritten(self):
        self.prepared();self.home.mkdir();(self.home/'unknown').write_text('preserve')
        with self.assertRaisesRegex(Rejected,'destination exists'):self.check()
        self.assertEqual((self.home/'unknown').read_text(),'preserve')

    def test_source_creation_failure_after_intent_is_held_without_replay(self):
        self.prepared()
        with patch.object(qualification,'create_source',side_effect=RuntimeError('partial startup')),self.assertRaises(RuntimeError):qualification.launch(self.config,self.binding,self.controller,SimpleNamespace(headless=False))
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        with self.assertRaisesRegex(Rejected,'consumed'):self.check()
        row=self.store.db.execute("select data from events where kind='NATIVE_DISPOSABLE_QUALIFICATION_HELD'").fetchone()
        self.assertEqual(json.loads(row[0])['retry'],'FORBIDDEN')

    def test_real_source_fixture_and_shared_session_receive_exact_bound_inputs(self):
        self.prepared();old=self.store.task(self.tid);seen=[]
        def session(config,args,controller,receipt,plan,binding,material,request,admit):
            admit();seen.append(binding)
            self.assertTrue((self.home/'fixtures/source/.git').is_dir())
            self.assertEqual(identity(tree(self.home/'fixtures/source')),self.case.target_source)
            self.assertEqual(json.loads(material['old-packet.json']),old['packet'])
            self.assertEqual(binding['required_requirements'],old['packet']['requirements'])
            self.assertEqual(set(config['roles']),{'thinker','doer','reviewer'})
            self.assertEqual(config['settings']['state_dir'],str(self.home/'r'))
            self.assertEqual(binding['config_hash'],identity(config))
            self.assertEqual(binding['predecessor_receipt'],self.case.prepared.json()['binding']['predecessor_receipt'])
            self.assertTrue(binding['fresh_qualification'])
        with patch.object(qualification,'run_session',side_effect=session):qualification.launch(self.config,self.binding,self.controller,SimpleNamespace(headless=False))
        self.assertEqual(len(seen),1);self.assertEqual(self.store.task(self.tid),old)

    def test_target_drift_between_intent_and_session_holds(self):
        self.prepared()
        def drift(*a,**kw):
            p=Path(self.binding['target_config']['path']);p.write_text('{}')
        with patch.object(qualification,'create_source',side_effect=drift),self.assertRaises(Rejected):qualification.launch(self.config,self.binding,self.controller,SimpleNamespace(headless=False))

    def test_shared_engine_initialization_failure_is_journaled_after_admission(self):
        self.prepared();old=self.store.task(self.tid)
        with patch('loop.native.NativeAdapter',side_effect=RuntimeError('pre-model adapter failure')),self.assertRaises(RuntimeError):
            qualification.launch(self.config,self.binding,self.controller,SimpleNamespace(headless=False))
        import sqlite3
        db=sqlite3.connect(self.home/'state/workflow.sqlite3')
        rows=[json.loads(r[0]) for r in db.execute("select data from events where kind='NATIVE_STARTUP'")];db.close()
        self.assertEqual([r['milestone'] for r in rows],['LAUNCH_INTENT','FAILED_OR_UNCERTAIN'])
        self.assertEqual(rows[-1]['details']['classification'],'STARTUP_REQUIRES_EFFECT_AUDIT')
        self.assertEqual(self.store.task(self.tid),old)
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        with self.assertRaisesRegex(Rejected,'consumed|destination exists'):self.check()

    def test_headless_cli_cannot_dispatch(self):
        self.prepared();p=self.folder/'binding.json';p.write_text(json.dumps(self.binding))
        with self.assertRaisesRegex(Rejected,'visible'):qualification.run_cli(self.config,SimpleNamespace(binding=p,check=False,headless=True),self.controller)

    def test_exact_three_frontend_backend_thread_generation_mapping(self):
        rows={};backends={};records={};panes={}
        for n,role in enumerate(('thinker','doer','reviewer'),10):
            rows[role]=dict(pid=n,thread=role,generation=n)
            backends[role]=SimpleNamespace(clients=[object()],proc=SimpleNamespace(pid=n,poll=lambda:None),start_identity=str(n),thread=role,generation=n)
            records[role]=dict(thread=role,generation=n,pane='%'+str(n),pid=n+100,process_identity=str(n+100))
            panes[role]=('%'+str(n),str(n+100),'0')
        adapter=SimpleNamespace(slots=SimpleNamespace(save=lambda:rows,backends=backends))
        terminals=SimpleNamespace(sync=lambda _:None,owned_panes=lambda:panes,records=records)
        with patch.object(qualification,'process_identity',side_effect=lambda pid:str(pid)):
            qualification.verify_clients(adapter,terminals)
            records['doer']['generation']+=1
            with self.assertRaises(Rejected):qualification.verify_clients(adapter,terminals)
            records['doer']['generation']-=1;backends['doer'].clients.append(object())
            with self.assertRaises(Rejected):qualification.verify_clients(adapter,terminals)


if __name__=='__main__':unittest.main()
