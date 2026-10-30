"""Synthetic public execution evidence, real Store/inspectors/graders; zero models."""
import copy
from datetime import datetime, timedelta, timezone
import fcntl
import json
from pathlib import Path
import shutil
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import test_native_resume
import test_native_packet
from loop.context import Checkpoint, derive_checkpoint
from loop.native import original_read_command
from loop.native_packet import prepare
from loop.native_receipts import ReceivedReceipts
from loop.native_resume import prepare_source_revision, source_revision_line, inspect_resume, run_resume
from loop.native_startup import StartupJournal
from loop.native_read_recovery import (inspect, confirmation, reconcile, admit, publish,
    projection, inspect_launch, KINDS)
from loop.store import Store
from loop.util import Rejected, NeedsInput, digest, identity, tree, write_json


class CompletedReadRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_resume.RuntimeResumeTests(
            'test_checkpoint_stops_existing_supervisor_and_check_is_read_only')
        self.fixture.setUp()
        self.f = f = self.fixture
        self.patchers = [patch('loop.native_resume.process_identity', return_value=None),
                         patch('loop.native_read_recovery.process_identity', return_value=None)]
        for p in self.patchers:
            p.start()
        folder = f.inputs / 'current-context'
        args = test_native_packet.CurrentPacketTests().args()
        policy = b'Preserve human gates and source. ' * 40
        args['originals']['policy.md'] = policy
        args['classifications']['policy.md']['sha256'] = digest(policy)
        self.packet = prepare(folder, **args, section_limit=2048)
        self.assertGreater(len(self.packet['sections']), 1)
        # Finalize the synthetic frozen contract before its checkpoint authority.
        contract = test_native_packet.CurrentPacketTests().frozen(args)
        if getattr(self,'native_recovery_inputs',False):
            policy=b'Controlled immutable native instruction.'
            contract['instructions']=[dict(path='controlled-policy.md',sha256=digest(policy))]
            contract['instructions_hash']=identity(contract['instructions'])
            contract['allowed_paths']=['code.py']
            (f.inputs/'instruction-0.md').write_bytes(policy)
            write_json(f.inputs/'packet.json',contract)
            f.cfg['settings'].update(model='gpt-6.1-sol',context_policy={
                'checkpoint':0.6,'compact':0.75,'hold':0.85,'reserve':16000,'max_age':30})
        f.store.db.execute('UPDATE tasks SET packet=?,content_hash=? WHERE id=?',
            (json.dumps(contract),identity(contract),f.tid))
        base = json.loads(f.saved_path.read_text())
        base['packet_hash'] = identity(contract)
        base_config = dict(f.cfg, controller=str(f.controller))
        base['maintenance_binding'].update(operation='synthetic-base-checkpoint',
            config_hash=identity(base_config), predecessor_receipt={'sha256':'0'*64})
        base['registry'] = {r:dict(row, process_identity='old-'+r, phase='read',
            model='gpt-6.1-sol', effort='high' if r=='reviewer' else 'medium',
            lineage=[]) for r,row in base['registry'].items()}
        write_json(f.root_runtime/'registry.json', base['registry'])
        base['registry_sha256'] = digest((f.root_runtime/'registry.json').read_bytes())
        base['registry_hash'] = identity(base['registry'])
        for spec in base['roles'].values():
            spec['input_files'] = tree(f.inputs)
        for role, key in [('thinker','owner_checkpoint'),('doer','doer_checkpoint')]:
            prior = json.loads(Path(base[key]).read_text())['state']['authority']
            row = base['registry'][role]
            prior['questions_answers'] = dict(pending=[],answers=[])
            prior['lease_generations'] = dict(role_generation=row['generation'],
                thread=row['thread'], server=str(row['pid'])+':'+row['process_identity'],
                process=row['process_identity'], phase='read')
            cp = Checkpoint(f.root/(role+'-original.json'), f.root)
            cp.save(prior, ['original.txt'])
            base[key] = str(cp.path)
        base_path = f.root/'original-runtime.json'
        write_json(base_path, base)
        StartupJournal(f.store, 'synthetic-base-checkpoint', base['maintenance_binding']).append(
            'RUNTIME_CHECKPOINTED', dict(receipt_sha256=digest(base_path.read_bytes())))
        self.old_controller = f.root/'admitted-source/controller'
        shutil.copytree(f.controller, self.old_controller)
        (self.old_controller/'loop').mkdir()
        (self.old_controller/'loop/native_resume.py').write_text('synthetic admitted implementation')
        self.old_config = dict(base_config, controller=str(self.old_controller))
        old_config_path, base_config_path = f.root/'admitted-config.json', f.root/'base-config.json'
        write_json(base_config_path, base_config)
        write_json(old_config_path, self.old_config)
        approval = f.root/'approval.md'
        approval.write_text('CONTROLLED TEST approval; no real human-origin claim')
        source_binding = dict(schema=1, operation='synthetic-admitted-runtime',
            previous_config=self.file(base_config_path), previous_receipt=self.file(base_path),
            approval=self.file(approval), source_hash=identity(tree(self.old_controller.parent)),
            controller_hash=identity(tree(self.old_controller)), config_hash=identity(self.old_config))
        self.prepared = prepare_source_revision(f.store, self.old_config, source_binding,
            self.old_controller, source_revision_line(source_binding, base))
        self.parent = json.loads(Path(self.prepared['receipt']).read_text())
        self.journal = StartupJournal(f.store, self.parent['maintenance_binding']['operation'],
                                     self.parent['maintenance_binding'])
        self.intent = self.journal.append('RUNTIME_RESUME_INTENT',
            dict(receipt_sha256=self.prepared['receipt_sha256']))
        self.rows = copy.deepcopy(base['registry'])
        for n,(role,row) in enumerate(self.rows.items()):
            old = base['registry'][role]
            row.update(pid=1000000+n, process_identity='failed-'+role,
                generation=old['generation']+1, prior_thread=old['thread'])
            if role == 'reviewer':
                row.update(thread='fresh-reviewer', prior_thread=None)
            else:
                row['lineage'].append(dict(old_thread=old['thread'],new_thread=row['thread'],
                    old_generation=old['generation'],new_generation=row['generation']))
            receipt_root = f.root_runtime/role/str(row['generation'])
            receipt_root.mkdir(parents=True)
            writer = ReceivedReceipts(receipt_root, role, row['generation'])
            seq = writer.received(b'{"id":1,"result":{}}\n', row['thread'])
            writer.result(seq, 'VALIDATED')
        write_json(f.root_runtime/'registry.json', self.rows)
        write_json(f.root_runtime/'supervisor.json', dict(pid=1100000,
            process_identity='failed-supervisor', source=self.parent['maintenance_binding']['source_hash'],
            maintenance_operation=self.parent['maintenance_binding']['operation'],
            cmdline_hex=(b'\0'.join(x.encode() for x in ['/usr/bin/python3',
                str(self.old_controller/'native_loopctl.py'),'--config',str(old_config_path),
                'resume-runtime','--prepared',self.prepared['receipt'],'--prepared-sha256',
                self.prepared['receipt_sha256']])+b'\0').hex()))
        write_json(f.root_runtime/'terminal-registry-closed-fixture.json',
            {**{r:dict(pid=1200000+n,process_identity='closed-'+r,thread=row['thread'],
                generation=row['generation']) for n,(r,row) in enumerate(self.rows.items())},
                '_server':dict(pid=1300000,process_identity='closed-server')})
        old = base['registry']['thinker']; row = self.rows['thinker']
        parent_cp = Checkpoint(Path(base['owner_checkpoint']), f.root)
        old_authority = json.loads(parent_cp.path.read_text())['state']['authority']
        authority = copy.deepcopy(old_authority)
        authority['lease_generations'].update(role_generation=row['generation'],
            server=str(row['pid'])+':'+row['process_identity'], process=row['process_identity'])
        fields = ('role_generation','thread','server','process','phase')
        cp = Checkpoint(parent_cp.path.parent/'controller-restart-owner.json', f.root)
        derive_checkpoint(parent_cp, cp, authority, dict(kind='restart',
            old={k:old_authority['lease_generations'][k] for k in fields},
            new={k:authority['lease_generations'][k] for k in fields}))
        self.originals = {'/inputs/current-context/'+s['name']:s['sha256'] for s in self.packet['sections']}
        self.expected = dict(owner='owner', checkpoint=cp.validate(authority), originals=self.originals)
        self.command = original_read_command(self.originals)
        self.capture_paths = {}
        for label, second in [('probe',0),('read',2)]:
            folder = f.root/'artifacts/setup/native'/label
            folder.mkdir(parents=True)
            text = 'No tools. Final exactly READY.' if label=='probe' else (
                'Read originals using '+self.command+'\nReturn exactly '+json.dumps(self.expected))
            final = 'READY' if label=='probe' else json.dumps(self.expected)
            messages = [('turn/started',dict(turn=dict(id=label+'-turn',status='inProgress'))),
                ('item/completed',dict(item=dict(id='user',type='userMessage',
                    content=[dict(type='text',text=text)])))]
            if label == 'read':
                files = {p:dict(sha256=h,content=(f.inputs/p.removeprefix('/inputs/')).read_text())
                         for p,h in self.originals.items()}
                item = dict(type='commandExecution',id='read-1',command=self.command,
                    exitCode=0,status='completed',aggregatedOutput=json.dumps(dict(files=files)))
                messages += [(method,dict(item=item)) for method in ('item/started','item/completed')]
            messages += [('item/completed',dict(item=dict(id='final',type='agentMessage',
                phase='final_answer',text=final))),
                ('turn/completed',dict(turn=dict(id=label+'-turn',status='completed',error=None)))]
            records = []
            for method,params in messages:
                params.update(threadId=self.rows['thinker']['thread'],turnId=label+'-turn')
                records.append(dict(role='thinker',generation=self.rows['thinker']['generation'],
                    time=(datetime(2026,10,29,tzinfo=timezone.utc)+timedelta(seconds=second)).isoformat(),
                    message=dict(method=method,params=params)))
            path = folder/'events.jsonl'
            path.write_text(''.join(json.dumps(r)+'\n' for r in records))
            self.capture_paths[label] = path
        f.store.event(None,'NATIVE_CAPABILITY_STAGED_HELD',dict(owner='owner'))
        f.store.event(None,'NATIVE_THINKER_REGISTERED',dict(owner='owner',
            thread=self.rows['thinker']['thread'],generation=self.rows['thinker']['generation']))
        f.store.event(None,'NATIVE_THINKER_CAPABILITY_HELD',dict(owner='owner'))
        for label in ('probe','read'):
            f.store.event(None,'NATIVE_OWNER_DISPATCH',dict(owner='owner',
                thread=self.rows['thinker']['thread'],probe=label=='probe',
                capture=str(self.capture_paths[label].parent)))
        self.failure = self.journal.append('RUNTIME_RESUME_FAILED',
            dict(receipt_sha256=self.prepared['receipt_sha256'],classification='RECONCILIATION_REQUIRED',
                 error='Diagnostic text alone is deliberately not the classification proof'))
        f.store.event(None,'NATIVE_CAPABILITY_REVOKED',dict(owner='owner'))
        self.controller = f.root/'corrected-source/controller'
        shutil.copytree(self.old_controller,self.controller)
        (self.controller/'loop/native_read_recovery.py').write_text('synthetic corrected implementation')
        self.config = dict(self.old_config,controller=str(self.controller))
        self.binding = dict(schema=1,parent_config=self.file(old_config_path),
            parent_receipt=self.file(Path(self.prepared['receipt'])),
            review={},approval=self.file(approval),intent_event=self.intent,failure_event=self.failure,
            checkpoints={'owner':self.file(Path(self.parent['owner_checkpoint'])),
                'doer':self.file(Path(self.parent['doer_checkpoint'])),
                'observed_owner':self.file(cp.path)},
            registry=self.file(f.root_runtime/'registry.json'),supervisor=self.file(f.root_runtime/'supervisor.json'),
            captures={},source_hash=identity(tree(self.controller.parent)),
            controller_hash=identity(tree(self.controller)),config_hash=identity(self.config))
        self.seal_captures()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def file(self, path):
        return dict(path=str(path),sha256=digest(path.read_bytes()))

    def seal_captures(self):
        """A new synthetic reviewed fixture, not rewriting real historical proof."""
        review = self.f.root/'synthetic-prior-review.zip'
        manifest = {}
        with zipfile.ZipFile(review,'w') as archive:
            for label,name in [('probe','probe'),('read','reread')]:
                spec = self.file(self.capture_paths[label])
                self.binding['captures'][label] = spec
                raw = json.dumps(dict(original_path=spec['path'],original_sha256=spec['sha256'])).encode()
                member = 'actual-native/'+name+'-capture-reference.json'
                archive.writestr(member,raw)
                manifest[member] = dict(sha256=digest(raw))
            archive.writestr('MANIFEST.json',json.dumps(dict(files=manifest)))
        self.binding['review'] = self.file(review)

    def check(self):
        return inspect(self.config,self.binding,self.controller)

    def ready(self):
        result = self.check()
        reconcile(self.f.store,self.config,self.binding,self.controller)
        admit(self.f.store,self.config,self.binding,self.controller,confirmation(self.binding,result))
        return publish(self.f.store,self.binding)

    def test_inspection_has_no_state_file_or_process_effects(self):
        # SQLite read-only connections may update transient shared-memory read marks;
        # authoritative DB/WAL bytes and all project/proof files must stay fixed.
        snapshot = lambda: {p:v for p,v in tree(self.f.root).items() if not p.endswith('-shm')}
        before = snapshot()
        events = self.f.store.db.execute('SELECT count(*) FROM events').fetchone()[0]
        result = self.check()
        self.assertEqual(result['proof']['classification'],'COMPLETED_READ_VALIDATION_FAILURE')
        self.assertFalse(result['proof']['rehydration_completed'])
        self.assertEqual(events,self.f.store.db.execute('SELECT count(*) FROM events').fetchone()[0])
        self.assertEqual(before,snapshot())

    def test_exact_admission_publishes_new_launch_preserving_old_failure(self):
        old = Path(self.prepared['receipt']).read_bytes()
        outcome = self.ready()
        saved,_ = inspect_resume(self.config,Path(outcome['receipt']),outcome['receipt_sha256'],self.controller)
        self.assertEqual(saved['registry'],self.rows)
        self.assertEqual(saved['source_before_stop'],self.parent['source_before_stop'])
        self.assertEqual(saved['maintenance_binding']['source_hash'],self.binding['source_hash'])
        self.assertEqual(old,Path(self.prepared['receipt']).read_bytes())
        self.assertEqual(self.journal.records()[-1]['milestone'],'RUNTIME_RESUME_FAILED')
        self.assertEqual(self.f.store.task(self.f.tid)['state'],'CANDIDATE_SEALED')

    def test_missing_terminal_and_wrong_turn_remain_uncertain_even_when_reviewed(self):
        path = self.capture_paths['read'];original = path.read_text()
        for change in ('missing','wrong'):
            rows = [json.loads(line) for line in original.splitlines()]
            if change == 'missing':rows = rows[:-1]
            else:rows[-1]['message']['params']['turn']['id'] = 'other-turn'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.seal_captures()
            with self.subTest(change=change),self.assertRaises(Rejected):self.check()

    def test_unrecognized_command_or_mcp_effect_cannot_be_admitted(self):
        path=self.capture_paths['read'];original=path.read_text()
        for kind in ('command','mcp'):
            rows=[json.loads(line) for line in original.splitlines()]
            for row in rows:
                item=row['message'].get('params',{}).get('item',{})
                if item.get('type')=='commandExecution':
                    if kind=='command':item['command']='touch /workspace/unauthorized'
                    else:item['type']='mcpToolCall'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.seal_captures()
            with self.subTest(kind=kind),self.assertRaises(Rejected):self.check()

    def test_missing_capture_dead_processes_do_not_authorize(self):
        self.capture_paths['read'].unlink()
        with self.assertRaises(Rejected):self.check()

    def test_candidate_input_and_old_source_drift_reject(self):
        for target in [self.f.workspace/'code.py',self.f.inputs/'request',self.old_controller/'loop/native_resume.py']:
            old=target.read_bytes();target.write_bytes(old+b'drift')
            with self.subTest(path=target),self.assertRaises(Rejected):self.check()
            target.write_bytes(old)

    def test_question_decision_and_active_capability_hold(self):
        self.f.store.ask_question('owner','scope',1,'Controlled unresolved question')
        with self.assertRaises(NeedsInput):self.check()

    def test_task_version_owner_packet_and_decision_changes_hold(self):
        task = self.f.store.task(self.f.tid)
        for field,value in [('version',task['version']+1),('owner','different-owner'),
                            ('content_hash','different-packet')]:
            self.f.store.db.execute('UPDATE tasks SET '+field+'=? WHERE id=?',(value,self.f.tid))
            with self.subTest(field=field),self.assertRaises(Rejected):self.check()
            self.f.store.db.execute('UPDATE tasks SET '+field+'=? WHERE id=?',(task[field],self.f.tid))
        self.f.store.db.execute('INSERT INTO decisions(id,task,time,action,binding,origin) VALUES(?,?,?,?,?,?)',
            ('controlled',self.f.tid,'test-time','reject','{}','CONTROLLED_TEST'))
        with self.assertRaisesRegex(Rejected,'decision'):self.check()

    def test_spawn_intent_and_uncertain_attempt_are_not_safe_reads(self):
        for status in ('SPAWN_INTENT','RUNNING','DISPATCH_UNCERTAIN'):
            self.f.store.db.execute('INSERT INTO attempts(id,task,generation,role,status,output) VALUES(?,?,?,?,?,?)',
                ('controlled-'+status,self.f.tid,1,'doer',status,'{}'))
            with self.subTest(status=status),self.assertRaises(Rejected):self.check()
            self.f.store.db.execute('DELETE FROM attempts WHERE id=?',('controlled-'+status,))

    def test_changed_checkpoint_or_unreviewed_capture_bytes_hold(self):
        for path in [Path(self.parent['doer_checkpoint']),self.capture_paths['read']]:
            raw=path.read_bytes();path.write_bytes(raw+b' ')
            with self.subTest(path=path),self.assertRaises(Rejected):self.check()
            path.write_bytes(raw)

    def test_incomplete_frame_receipt_or_dormant_role_turn_holds(self):
        row=self.rows['doer']
        path=self.f.root_runtime/'doer'/str(row['generation'])/'received-frames.jsonl'
        raw=path.read_bytes();rows=[json.loads(line) for line in path.read_text().splitlines()]
        path.write_text(json.dumps(rows[0])+'\n')
        with self.assertRaisesRegex(Rejected,'frame'):self.check()
        rows[0]['envelope']['method']='turn/started'
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with self.assertRaisesRegex(Rejected,'dormant'):self.check()
        path.write_bytes(raw)

    def test_live_terminal_or_extra_post_failure_effect_holds(self):
        path=self.f.root_runtime/'terminal-registry.json'
        path.write_text('{}')
        with self.assertRaisesRegex(Rejected,'Terminal'):self.check()
        path.unlink()
        self.f.store.event(self.f.tid,'CONTROLLED_UNRECOGNIZED_EFFECT',dict(owner='owner'))
        with self.assertRaisesRegex(Rejected,'Unexpected effects'):self.check()

    def test_owned_intake_service_lock_or_endpoint_holds(self):
        path=self.f.root/'state/service.lock'
        with path.open('a+b') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(Rejected,'intake service'):self.check()
        endpoint=self.f.root/'state/intake.sock'
        endpoint.write_text('controlled unresolved endpoint')
        with self.assertRaises(Rejected):self.check()

    def test_changed_model_profile_and_protected_module_reject(self):
        config=copy.deepcopy(self.config);config['settings']['model']='other-model'
        binding=copy.deepcopy(self.binding);binding['config_hash']=identity(config)
        with self.assertRaisesRegex(Rejected,'cannot change'):inspect(config,binding,self.controller)
        (self.controller/'loop/store.py').write_text('out-of-scope mutation')
        binding=copy.deepcopy(self.binding);binding.update(source_hash=identity(tree(self.controller.parent)),
            controller_hash=identity(tree(self.controller)))
        with self.assertRaisesRegex(Rejected,'bounded'):inspect(self.config,binding,self.controller)

    def test_active_capability_cannot_enter_known_read_route(self):
        self.f.store.db.execute('UPDATE capabilities SET enabled=1')
        with self.assertRaisesRegex(Rejected,'capability'):self.check()

    def test_live_or_reused_pid_and_changed_phase_reject(self):
        with patch('loop.native_read_recovery.process_identity',return_value='new-pid-owner'):
            with self.assertRaises(Rejected):self.check()
        rows=copy.deepcopy(self.rows);rows['doer']['phase']='write'
        write_json(self.f.root_runtime/'registry.json',rows)
        self.binding['registry']=self.file(self.f.root_runtime/'registry.json')
        with self.assertRaises(Rejected):self.check()

    def test_symlinked_or_escaping_proof_path_rejects(self):
        link=self.f.root/'capture-link';link.symlink_to(self.capture_paths['read'])
        self.binding['captures']['read']=dict(path=str(link),sha256=digest(link.read_bytes()))
        with self.assertRaises(Rejected):self.check()

    def test_stable_parent_allows_one_successor_not_fresh_nonce(self):
        result=self.check();first=reconcile(self.f.store,self.config,self.binding,self.controller)
        self.assertEqual(first,reconcile(self.f.store,self.config,self.binding,self.controller))
        relocated=self.f.root/'same-parent-new-path.json'
        relocated.write_bytes(Path(self.prepared['receipt']).read_bytes())
        copied=copy.deepcopy(self.binding);copied['parent_receipt']=self.file(relocated)
        with self.assertRaisesRegex(Rejected,'different successor'):
            inspect(self.config,copied,self.controller)
        changed=copy.deepcopy(self.binding);changed['operation']='fresh-uuid-label'
        with self.assertRaises(Rejected):inspect(self.config,changed,self.controller)
        (self.controller/'loop/native_read_recovery.py').write_text('another proposed successor')
        changed.pop('operation');changed.update(source_hash=identity(tree(self.controller.parent)),
            controller_hash=identity(tree(self.controller)))
        with self.assertRaisesRegex(Rejected,'different successor'):inspect(self.config,changed,self.controller)

    def test_wrong_foreground_text_does_not_admit_source(self):
        reconcile(self.f.store,self.config,self.binding,self.controller)
        with self.assertRaises(Rejected):admit(self.f.store,self.config,self.binding,self.controller,'yes')
        self.assertNotIn(KINDS[1],self.check()['records'])

    def test_concurrent_admissions_commit_one_successor(self):
        line=confirmation(self.binding,self.check());barrier=threading.Barrier(2);results=[]
        def contender():
            store=Store(self.f.root)
            try:
                barrier.wait()
                reconcile(store,self.config,self.binding,self.controller)
                results.append(admit(store,self.config,self.binding,self.controller,line))
            except Rejected:
                results.append('held')
            finally:store.close()
        threads=[threading.Thread(target=contender) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertTrue(any(isinstance(x,int) for x in results))
        self.assertEqual(len(self.check()['records']),2)
        self.assertLessEqual(len({x for x in results if isinstance(x,int)}),1)

    def test_drift_after_inspection_rechecked_before_commit(self):
        self.check();self.f.inputs.joinpath('request').write_text('changed after pure check')
        with self.assertRaises(Rejected):reconcile(self.f.store,self.config,self.binding,self.controller)
        self.assertEqual(self.f.store.db.execute('SELECT count(*) FROM events WHERE kind=?',(KINDS[0],)).fetchone()[0],0)

    def test_orphan_projection_cannot_launch_without_committed_authority(self):
        result=self.check();data=dict(parent_key=result['parent_key'],binding=self.binding,
            proof=result['proof'],proof_hash=result['proof_hash'],origin='FOREGROUND_CONTROLLING_TTY',
            text=confirmation(self.binding,result))
        value=projection(self.f.root,dict(seq=999,data=data));path=self.f.root/'orphan.json'
        write_json(path,value)
        with self.assertRaisesRegex(Rejected,'Orphan'):
            inspect_launch(self.config,path,digest(path.read_bytes()),self.controller)

    def test_commit_then_lost_publication_reconstructs_without_new_authority(self):
        result=self.check();reconcile(self.f.store,self.config,self.binding,self.controller)
        seq=admit(self.f.store,self.config,self.binding,self.controller,confirmation(self.binding,result))
        before=self.f.store.db.execute('SELECT count(*) FROM events').fetchone()[0]
        with patch('loop.native_read_recovery.atomic',side_effect=OSError('controlled lost publication')):
            with self.assertRaises(OSError):publish(self.f.store,self.binding)
        self.assertEqual(seq,admit(self.f.store,self.config,self.binding,self.controller,None))
        first=publish(self.f.store,self.binding);second=publish(self.f.store,self.binding)
        self.assertEqual(first,second)
        self.assertEqual(before,self.f.store.db.execute('SELECT count(*) FROM events').fetchone()[0])

    def test_crash_before_admission_commit_rolls_back_authority(self):
        result=self.check();reconcile(self.f.store,self.config,self.binding,self.controller)
        original=self.f.store.event
        def fail(task,kind,data):
            seq=original(task,kind,data)
            if kind==KINDS[1]:raise RuntimeError('controlled precommit crash')
            return seq
        with patch.object(self.f.store,'event',side_effect=fail):
            with self.assertRaises(RuntimeError):
                admit(self.f.store,self.config,self.binding,self.controller,confirmation(self.binding,result))
        self.assertNotIn(KINDS[1],self.check()['records'])
        with self.assertRaises(Rejected):publish(self.f.store,self.binding)

    def test_tampered_receipt_and_changed_source_reject(self):
        result=self.ready();path=Path(result['receipt']);raw=path.read_bytes()
        value=json.loads(raw);value['route']='unsupported';write_json(path,value)
        with self.assertRaises(Rejected):inspect_launch(self.config,path,digest(path.read_bytes()),self.controller)
        path.write_bytes(raw);(self.controller/'loop/native_read_recovery.py').write_text('source drift')
        with self.assertRaises(Rejected):inspect_launch(self.config,path,result['receipt_sha256'],self.controller)

    def test_valid_route_with_forged_authority_reference_still_rejects(self):
        result=self.ready();path=Path(result['receipt']);original=json.loads(path.read_text())
        for changed in ('owner','admission'):
            value=copy.deepcopy(original)
            if changed=='owner':value['owner']='different-owner'
            else:value['completed_read_recovery']['admission_event']+=1
            write_json(path,value)
            with self.subTest(changed=changed),self.assertRaises(Rejected):
                inspect_launch(self.config,path,digest(path.read_bytes()),self.controller)

    def test_consumed_launch_after_preprocess_crash_cannot_retry(self):
        result=self.ready();args=SimpleNamespace(prepared=Path(result['receipt']),
            prepared_sha256=result['receipt_sha256'],check=False,headless=True)
        with patch('loop.native.NativeAdapter',side_effect=RuntimeError('controlled external-start uncertainty')):
            with self.assertRaises(RuntimeError):run_resume(self.config,args,self.controller)
        with self.assertRaisesRegex(Rejected,'consumed'):
            inspect_resume(self.config,args.prepared,args.prepared_sha256,self.controller)
        self.assertEqual(len(StartupJournal(self.f.store,
            'completed-read-'+self.check()['parent_key'],
            json.loads(args.prepared.read_text())['maintenance_binding']).records()),2)

    def test_original_consumed_receipt_still_rejects(self):
        with self.assertRaises(Rejected):inspect_resume(self.old_config,
            Path(self.prepared['receipt']),self.prepared['receipt_sha256'],self.old_controller)


if __name__=='__main__':
    unittest.main()
