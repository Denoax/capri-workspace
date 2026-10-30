"""Synthetic before-probe recovery controls; no auth or model processes."""
from dataclasses import asdict,replace
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import test_controller
from test_native_stopped import fixture
from loop import native_startup_repair as repair
from loop.native import NativeTerminals
from loop.native_qualification import verify_clients
from loop.native_packet import prepare as packet_prepare
from loop.native_startup import StartupJournal
from loop.native_stopped import commit_fence,prepare_qualification,scope_line
from loop.store import Store
from loop.util import identity,tree,digest,atomic,Rejected,NeedsInput


class StartupRepairTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp();fixture(self)
        Path(self.config['settings']['auth_file']).write_text('synthetic auth; never mounted')
        self.data=self.root/'repair-data';self.data.mkdir()
        def bound(name,data):
            p=self.data/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode())
            return dict(path=str(p),sha256=digest(p.read_bytes()))
        self.bound=bound
        failed=self.root/'failed-source';(failed/'controller').mkdir(parents=True);(failed/'controller/old.py').write_text('synthetic failed controller')
        self.case=replace(self.case,target_root=str(failed),target_source=identity(tree(failed)))
        self.oldhome=self.root/'failed';self.oldroot=self.oldhome/'r'
        old=json.loads(json.dumps(self.config));old.update(home=str(self.oldhome),controller=str(failed/'controller'))
        old['settings']['state_dir']=str(self.oldroot)
        old['workflow'].update(notes=str(self.oldhome/'notes'),authorized_repositories=[str(self.oldhome/'fixtures/source')])
        old['roles']={r:dict(workspace=str(self.oldhome/'slots'/r/'workspace'),inputs=str(self.oldhome/'slots'/r/'inputs')) for r in ('thinker','doer','reviewer')}
        packet=self.store.task(self.tid)['packet'];core=self.case.prepared.json()['binding']['predecessor_receipt']
        originals={'REFERENCE_LED_DESIGN.md':b'Preserve original source.',
            'original-request.json':json.dumps(packet['request']).encode(),'old-packet.json':json.dumps(packet).encode(),
            'preserved-requirements.json':json.dumps(packet['requirements']).encode(),
            'historical-prepared.json':self.case.prepared.read(),'full-prepared.json':Path(core['path']).read_bytes(),
            'successor-request.json':json.dumps(dict(text=scope_line(self.case,str(self.oldroot)),human_answers=[])).encode()}
        base=dict(schema=1,kind='FRESH_NATIVE_QUALIFICATION',case=bound('case.json',asdict(self.case)),
            recovery_controller=str(self.controller),target_controller_hash=identity(tree(failed/'controller')),
            target_config=bound('old-config.json',old),request=dict(text=scope_line(self.case,str(self.oldroot)),human_answers=[]))
        base['materials']=[dict(name=n,**bound('old-material/'+n,b)) for n,b in originals.items()]
        self.base=base;owner='synthetic-failed-owner'
        f=commit_fence(self.store,self.config,self.case,self.controller)
        p=prepare_qualification(self.store,self.config,self.case,self.controller,str(self.oldroot),scope_line(self.case,str(self.oldroot)))
        intent=self.store.event(None,'NATIVE_DISPOSABLE_QUALIFICATION_INTENT',dict(case_hash=self.case.key(),binding_hash=identity(base),
            target_home=str(self.oldhome),runtime=str(self.oldroot),target_source=self.case.target_source,target_config=base['target_config'],qualification_owner=owner,
            fence_event=f['event'],prepared_event=p['event']))
        held=self.store.event(None,'NATIVE_DISPOSABLE_QUALIFICATION_HELD',dict(case_hash=self.case.key(),admission_event=intent,error_type='Rejected'))
        shutil.copytree(failed,self.oldhome/'fixtures/source');shutil.copytree(failed,self.oldhome/'snapshots/thinker')
        inputs=self.oldhome/'inputs/thinker'
        for n,b in originals.items():atomic(inputs/n,b,exclusive=True)
        reg={r:dict(pid=950000+n,thread='00000000-0000-4000-8000-00000000000'+str(n),generation=n+20,empty=True,phase='read',model='gpt-6.1-sol',effort='high' if r=='reviewer' else 'medium') for n,r in enumerate(('thinker','doer','reviewer'),1)}
        self.oldroot.mkdir(parents=True)
        def oldfile(name,data):
            p=self.oldroot/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data));return dict(path=str(p),sha256=digest(p.read_bytes()))
        registry=oldfile('registry.json',reg)
        supervisor=oldfile('supervisor.json',dict(pid=950010,source=self.case.target_source,maintenance_operation='synthetic-failed-session'))
        terminal=oldfile('terminal-registry-closed-synthetic.json',dict(_server={'pid':950011}))
        received={}
        for r,row in reg.items():
            b=(json.dumps(dict(phase='RECEIVED',role=r,generation=row['generation'],expected_thread=row['thread'],envelope={'method':'thread/started'}))+'\n').encode()
            p=self.oldroot/r/str(row['generation'])/'received-frames.jsonl';p.parent.mkdir(parents=True);p.write_bytes(b)
            received[r]=dict(path=str(p),sha256=digest(b))
        session=dict(operation='synthetic-failed-session',config_hash=identity(old),source_hash=self.case.target_source,
            controller_hash=base['target_controller_hash'],owner=owner,fresh_qualification=True,
            workspace=str(self.oldhome/'snapshots/thinker'),inputs=str(inputs),verify_visible_clients=True)
        store=Store(self.oldhome);journal=StartupJournal(store,session['operation'],session)
        journal.append('LAUNCH_INTENT',dict(source=self.case.target_source))
        with store.transaction():
            scope=dict(request=base['request'],repo=str(self.oldhome/'fixtures/source'),key='synthetic-key')
            store.db.execute('INSERT INTO capabilities(token_hash,owner,scope,enabled) VALUES(?,?,?,0)',('synthetic-token-hash',owner,json.dumps(scope)))
            store.db.execute('INSERT INTO sessions(id,owner,role,runtime) VALUES(?,?,?,?)',(reg['thinker']['thread'],owner,'thinker',str(self.oldroot/'thinker/runtime')))
            store.event(None,'NATIVE_CAPABILITY_STAGED_HELD',{'owner':owner})
            store.event(None,'NATIVE_THINKER_REGISTERED',{'owner':owner})
        journal.append('SLOTS_CREATED',dict(registry=reg))
        journal.append('FAILED_OR_UNCERTAIN',dict(classification='STARTUP_REQUIRES_EFFECT_AUDIT',error='Native visible frontend mapping differs',last_proved='SLOTS_CREATED',task=None))
        with store.transaction():store.event(None,'NATIVE_CAPABILITY_REVOKED',{'owner':owner})
        store.close()
        self.home=self.root/'repaired';target=json.loads(json.dumps(old));target.update(home=str(self.home),controller=str(self.controller));target['settings']['state_dir']=str(self.home/'r')
        target['workflow'].update(notes=str(self.home/'notes'),authorized_repositories=[str(self.home/'fixtures/source')])
        target['roles']={r:dict(workspace=str(self.home/'slots'/r/'workspace'),inputs=str(self.home/'slots'/r/'inputs')) for r in reg}
        db=self.oldhome/'state/workflow.sqlite3'
        self.binding=dict(schema=1,kind='PREMODEL_NATIVE_QUALIFICATION_REPAIR',base=bound('base.json',base),intent_event=intent,held_event=held,
            old_database=dict(path=str(db),sha256=digest(db.read_bytes())),registry=registry,supervisor=supervisor,terminals=[terminal],received=received,
            target_root=str(self.controller.parent),target_source=identity(tree(self.controller.parent)),controller_hash=identity(tree(self.controller)),config=bound('new-config.json',target))
        request=dict(text='Recover only the accounted pre-model native launch '+str(intent)+' with repaired source; preserve all original limits.',human_answers=[])
        material=dict(originals);material['successor-request.json']=json.dumps(request).encode()
        classes={n:dict(category='history',reason='Preserved original',sha256=digest(b)) for n,b in material.items()};classes['REFERENCE_LED_DESIGN.md'].update(category='current',reason='Operative policy')
        uid=str(uuid.uuid5(uuid.NAMESPACE_URL,'capri-startup-repair:'+repair.condition(self.binding)))
        index=packet_prepare(self.data/'context',originals=material,classifications=classes,requirements=packet['requirements'],proposal=dict(requirements=packet['requirements']),
            current_request=request,answers=[],binding=dict(owner=uid,repo_source_hash=self.binding['target_source'],controller_source_hash=self.binding['target_source'],
                scope_hash=digest(request['text'].encode()),active_originals=['REFERENCE_LED_DESIGN.md']))
        for p in (self.data/'context').iterdir():material['current-context/'+p.name]=p.read_bytes()
        self.binding.update(request=request,context_packet=dict(path=str(self.data/'context/INDEX.json'),sha256=digest((self.data/'context/INDEX.json').read_bytes())),
            materials=[dict(name=n,**bound('new-material/'+n,b)) for n,b in material.items()])
        self.dead=patch('loop.native_startup_repair.process_identity',return_value=None);self.dead.start();self.addCleanup(self.dead.stop)
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    def check(self,**kw):return repair.check(self.config,self.binding,self.controller,**kw)

    def prepare(self):return repair.prepare(self.store,self.config,self.binding,self.controller,repair.foreground_line(self.binding))

    def test_read_only_check_creates_no_socket_process_initializer_or_state(self):
        paths=[self.root/'state/workflow.sqlite3',self.oldhome/'state/workflow.sqlite3']
        before=[p.read_bytes() for p in paths]
        with patch('subprocess.Popen',side_effect=AssertionError('process')),patch('socket.socket',side_effect=AssertionError('socket')),patch('loop.store.Store.__init__',side_effect=AssertionError('initializer')):
            result=self.check(require_prepared=False)
        self.assertEqual(result['status'],'PREMODEL_REPAIR_NEEDS_FOREGROUND');self.assertFalse(self.home.exists())
        self.assertEqual(before,[p.read_bytes() for p in paths])

    def test_exact_new_scope_and_single_intent_preserve_old_state(self):
        before=self.store.task(self.tid)
        with self.assertRaises(Rejected):self.check()
        with self.assertRaises(Rejected):repair.prepare(self.store,self.config,self.binding,self.controller,'old scope267')
        self.prepare();result=repair.commit(self.store,self.config,self.binding,self.controller)
        self.assertGreater(result['admission_event'],self.binding['held_event']);self.assertEqual(self.store.task(self.tid),before)
        with self.assertRaisesRegex(Rejected,'consumed'):repair.commit(self.store,self.config,self.binding,self.controller)
        self.assertFalse(self.home.exists())

    def test_lost_response_or_changed_binding_cannot_replay_scope(self):
        self.prepare()
        with self.assertRaises(Rejected):self.prepare()
        changed={**self.binding,'controller_hash':'0'*64}
        with self.assertRaises(Rejected):repair.check(self.config,changed,self.controller,view=self.store,require_prepared=False)

    def test_pending_question_live_pid_or_endpoint_holds(self):
        with patch('loop.native_startup_repair.process_identity',return_value='reused'),self.assertRaises(Rejected):self.check(require_prepared=False)
        p=self.oldroot/'doer.sock';p.write_text('unknown endpoint')
        with self.assertRaises(Rejected):self.check(require_prepared=False)
        p.unlink();self.store.ask_question(self.case.owner,'scope',1,'pending behavior?')
        with self.assertRaises((Rejected,NeedsInput)):repair.check(self.config,self.binding,self.controller,view=self.store,require_prepared=False)

    def test_rebound_turn_receipt_is_rejected(self):
        spec=self.binding['received']['doer'];p=Path(spec['path']);row=json.loads(p.read_text());row['envelope']['method']='turn/started';p.write_text(json.dumps(row)+'\n');spec['sha256']=digest(p.read_bytes())
        with self.assertRaisesRegex(Rejected,'Model/lifecycle'):self.check(require_prepared=False)

    def test_new_profile_is_never_admitted(self):
        target=json.loads(Path(self.binding['config']['path']).read_text());target['settings']['model']='other';self.binding['config']=self.bound('wrong-profile.json',target)
        with self.assertRaises(Rejected):self.check(require_prepared=False)

    def test_failed_database_or_existing_repair_home_is_not_reinitialized(self):
        p=Path(self.binding['old_database']['path']);raw=p.read_bytes();p.write_bytes(raw+b'\0')
        with self.assertRaises(Rejected):self.check(require_prepared=False)
        p.write_bytes(raw);self.home.mkdir();sentinel=self.home/'preserve';sentinel.write_text('existing')
        with self.assertRaises(Rejected):self.check(require_prepared=False)
        self.assertEqual(sentinel.read_text(),'existing')

    def test_partial_startup_after_committed_repair_is_held_not_retried(self):
        self.prepare();self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        with patch.object(repair,'create_source',side_effect=RuntimeError('partial creation')),self.assertRaises(RuntimeError):repair.launch(self.config,self.binding,self.controller,SimpleNamespace(headless=False))
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        with self.assertRaisesRegex(Rejected,'consumed'):self.check(require_prepared=False)

    def test_crash_before_commit_rolls_back_repair_intent(self):
        self.prepare();original=self.store.event
        def crash(*a,**kw):original(*a,**kw);raise RuntimeError('precommit')
        with patch.object(self.store,'event',side_effect=crash),self.assertRaises(RuntimeError):repair.commit(self.store,self.config,self.binding,self.controller)
        self.assertEqual(self.check(view=self.store)['status'],'PREMODEL_REPAIR_LAUNCH_CHECKED')


class FrontendParserRegression(unittest.TestCase):
    def test_production_owned_panes_pid_text_is_accepted_without_weakening_identity(self):
        rows={};backends={};records={};lines=[]
        for n,role in enumerate(('thinker','doer','reviewer'),10):
            rows[role]=dict(pid=n,thread=role,generation=n)
            backends[role]=SimpleNamespace(clients=[object()],proc=SimpleNamespace(pid=n,poll=lambda:None),start_identity=str(n),thread=role,generation=n)
            records[role]=dict(thread=role,generation=n,pane='%'+str(n),pid=n+100,process_identity=str(n+100))
            lines.append(role+'\t%'+str(n)+'\t'+str(n+100)+'\t0')
        terminals=object.__new__(NativeTerminals);terminals.records=records;terminals.sync=lambda _:None
        terminals.tmux=lambda *a,**kw:SimpleNamespace(stdout='\n'.join(lines))
        adapter=SimpleNamespace(slots=SimpleNamespace(save=lambda:rows,backends=backends))
        with patch('loop.native.process_identity',side_effect=lambda pid:str(pid)),patch('loop.native_qualification.process_identity',side_effect=lambda pid:str(pid)):
            self.assertIsInstance(terminals.owned_panes()['doer'][1],str)
            verify_clients(adapter,terminals)
            records['doer']['process_identity']='wrong'
            with self.assertRaises(Rejected):verify_clients(adapter,terminals)


if __name__=='__main__':unittest.main()
