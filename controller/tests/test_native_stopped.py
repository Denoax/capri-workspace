"""Synthetic-only stopped compaction fixtures. No actual workflow/auth/model I/O."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import test_controller
from loop.context import Checkpoint, SECTIONS
from loop.native_stopped import FileBinding, StoppedCompaction, inspect, commit_fence, qualification_plan, prepare_qualification, scope_line, run_cli
from loop.settings import Settings
from loop.util import identity, tree, digest, Rejected


def fixture(self):
    # This is a synthetic product, not the operator's entire checkout. Keep its
    # exact controller bytes without inheriting local venv symlinks, presentation
    # exports or unrelated files from the checkout's parent source inventory.
    self.controller=self.root/'current-source/controller'
    shutil.copytree(Path(__file__).resolve().parents[1],self.controller,
                    ignore=shutil.ignore_patterns('__pycache__'))
    old=self.root/'old-source';(old/'controller').mkdir(parents=True)
    (old/'controller/old.py').write_text('historical controller')
    self.workspace=self.root/'candidate';shutil.copytree(old,self.workspace)
    packet=dict(request={'text':'preserve exact answers'},requirements=[dict(id=f'N{i:02d}') for i in range(1,9)]+[dict(id='SCOPE')])
    t=self.store.create('synthetic-key',packet,'synthetic-owner');self.tid=t['id']
    self.store.transition(self.tid,'READY','DOER_RUNNING',candidate=str(self.workspace))
    self.store.transition(self.tid,'DOER_RUNNING','CANDIDATE_SEALED',seal=json.dumps(dict(source_hash=identity(tree(old)),files=tree(old))))
    t=self.store.task(self.tid)
    root=self.root/'runtime';root.mkdir()
    self.config=dict(home=str(self.root),controller=str(old/'controller'),settings=dict(binary='/bin/false',binary_sha256=digest(Path('/bin/false').read_bytes()),auth_file=str(self.root/'absent-auth'),state_dir=str(root)))
    self.config['workflow']=dict(notes=str(self.root/'notes'),authorized_repositories=[],production_automation='DISABLED')
    core=self.root/'core-receipt.json';core.write_text(json.dumps(dict(prepared=dict(lineage=dict(human_answers=[])))))
    binding=dict(owner=t['owner'],home=str(self.root),source_hash=identity(tree(old)),controller=str(old/'controller'),controller_hash=identity(tree(old/'controller')),config_hash=identity(self.config))
    binding['predecessor_receipt']=dict(path=str(core),sha256=digest(core.read_bytes()))
    operation='synthetic-startup'
    request_binding=dict(task=self.tid,version=t['version'],owner=t['owner'],packet_hash=t['content_hash'],source_hash=identity(tree(old)),controller_hash=identity(tree(old/'controller')),supervisor_pid=900010,supervisor_identity='supervisor-start',role='doer',thread='synthetic-thread',role_generation=107)
    request=dict(action='compact-role',binding=request_binding);key=identity(request)
    self.store.event(self.tid,'NATIVE_ATTEMPT_RESULT',dict(role='doer',role_generation=107,status='COMPLETED',thread='synthetic-thread',pid=900001,start_identity='old-start',source_after=identity(tree(old))))
    def startup(milestone,details):return self.store.event(None,'NATIVE_STARTUP',dict(operation=operation,parameters_hash=identity(binding),milestone=milestone,details=details))
    scope=startup('SCOPE_CAPTURED',dict(old_core_claim='PRESERVED',origin='FOREGROUND_CONTROLLING_TTY',text='synthetic previous scope'))
    intent=startup('MAINTENANCE_INTENT',dict(action='compact-role',generation=107,key=key,role='doer',thread='synthetic-thread'))
    inputs=self.root/'inputs'/self.tid/'last-bounded-step';inputs.mkdir(parents=True);(inputs/'packet.json').write_text(json.dumps(packet))
    authority={n:{} for n in SECTIONS}
    authority.update(contract_requirements=packet,request_corrections=packet['request'],inflight_uncertain=[],questions_answers={'pending':[],'answers':[]},next_action={'human_gate':False},
        source_instructions=dict(candidate=tree(self.workspace),inputs=tree(inputs)),
        lease_generations=dict(task=self.tid,task_generation=t['generation'],role_generation=108,role='doer',thread='synthetic-thread',lease='native-writer:'+self.tid,server='900002:new-start',process='new-start',phase='read'))
    original=self.root/'authority.json';original.write_text(json.dumps(authority));cp=Checkpoint(self.root/'checkpoint.json',self.root);cp.save(authority,['authority.json'])
    capture=self.root/'rehydration';capture.mkdir()
    records=[dict(role='doer',generation=108,message=dict(method='turn/started',params=dict(threadId='synthetic-thread',turn=dict(id='read-turn')))),dict(role='doer',generation=108,message=dict(method='turn/completed',params=dict(threadId='synthetic-thread',turn=dict(id='read-turn',status='completed'))))]
    (capture/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    self.store.event(self.tid,'REHYDRATION_VALIDATED',dict(checkpoint=json.loads(cp.path.read_text())['sha256'],capture=str(capture),role='doer'))
    bound=startup('MAINTENANCE_READ_ONLY_BOUND',dict(key=key,action='compact-role',role='doer',old_thread='synthetic-thread',generation=107,pid=900001,process='old-start',source=tree(self.workspace),inputs=tree(inputs),checkpoint=str(cp.path),checkpoint_sha256=digest(cp.path.read_bytes())))
    uncertain=startup('MAINTENANCE_UNCERTAIN',dict(key=key,role='doer',error='Native turn exceeded wall budget; reconcile effects'))
    registry={r:dict(pid=900003+i,process_identity='other',thread=r,generation=1,phase='read',model='gpt-6.1-sol',effort='high' if r=='reviewer' else 'medium') for i,r in enumerate(('thinker','doer','reviewer'))}
    registry['doer']=dict(pid=900002,process_identity='new-start',thread='synthetic-thread',generation=108,phase='read',model='gpt-6.1-sol',effort='medium',lineage=[dict(old_thread='synthetic-thread',new_thread='synthetic-thread',old_generation=107,new_generation=108)])
    def put(path,value):
        path=Path(path);path.parent.mkdir(exist_ok=True,parents=True);path.write_text(value if isinstance(value,str) else json.dumps(value));return FileBinding(str(path),digest(path.read_bytes()))
    config=put(self.root/'config.json',self.config)
    prepared=put(self.root/'prepared.json',dict(binding=binding,scope_event=scope,scope_text='synthetic previous scope'))
    reg=put(root/'registry.json',registry)
    supervisor=put(root/'supervisor.json',dict(pid=900010,process_identity='supervisor-start',source=identity(tree(old)),maintenance_operation=operation))
    runtime=put(root/'doer/runtime/config.toml',Settings(**self.config['settings']).config('doer','read'))
    context=put(self.root/'public-rollout.jsonl',json.dumps(dict(type='turn_context',payload=dict(turn_id='read-turn',sandbox_policy={'type':'read-only'},permission_profile={'file_system':{'entries':[{'access':'read'}]}})))+'\n')
    frames=put(self.root/'frames.jsonl',json.dumps(dict(phase='RECEIVED',role='doer',generation=108,expected_thread='synthetic-thread'))+'\n')
    receipt=put(self.root/'compaction-receipt.json',dict(status='UNCERTAIN',role='doer',thread='synthetic-thread'))
    compact=put(self.root/'compaction-events.jsonl',json.dumps(dict(role='doer',generation=108,message=dict(method='turn/started',params=dict(threadId='synthetic-thread',turn={'id':'compact-turn'}))))+'\n')
    terminal=put(root/'terminal-closed.json',{'_server':{'pid':900011}})
    parent_request=put(self.root/'maintenance-request.json',request)
    self.case=StoppedCompaction(1,'STOPPED_READ_ONLY_COMPACTION',str(self.root),str(root),str(inputs),self.tid,t['owner'],t['version'],t['generation'],t['content_hash'],identity(tree(old)),identity(tree(self.controller.parent)),identity(tree(self.controller.parent)),str(self.controller.parent),operation,key,scope,intent,bound,uncertain,prepared,config,reg,supervisor,FileBinding(str(cp.path),digest(cp.path.read_bytes())),FileBinding(str(capture/'events.jsonl'),digest((capture/'events.jsonl').read_bytes())),context,runtime,frames,receipt,compact,parent_request,(terminal,))
    self.stopped=patch('loop.native_stopped.process_identity',return_value=None);self.stopped.start();self.addCleanup(self.stopped.stop)
    self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')


class StoppedTests(test_controller.IsolatedCase):
    def setUp(self):super().setUp();fixture(self)

    def snapshot(self):
        return {str(p.relative_to(self.root)):digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}

    def test_typed_pure_inspection_proves_generic_remount_without_authority(self):
        before=self.snapshot()
        with patch('subprocess.Popen',side_effect=AssertionError('child process')),patch('socket.socket',side_effect=AssertionError('socket')),patch('loop.store.Store.__init__',side_effect=AssertionError('state initializer')):
            result=inspect(self.config,self.case,self.controller)
        self.assertEqual(result['actual_identity']['generation'],108)
        self.assertEqual(result['compaction'],'INCOMPLETE');self.assertEqual(result['new_dispatch'],'NOT_AUTHORIZED')
        self.assertEqual(before,self.snapshot())

    def test_invalid_inspection_and_public_check_create_nothing(self):
        before=self.snapshot();path=self.root/'case.json';path.write_text(json.dumps(asdict(self.case)));before=self.snapshot()
        args=SimpleNamespace(binding=path,command='inspect-stopped-maintenance',check=True)
        with patch('subprocess.Popen',side_effect=AssertionError('process')),patch('socket.socket',side_effect=AssertionError('socket')),patch('loop.store.Store.__init__',side_effect=AssertionError('init')):
            with patch('builtins.print'):run_cli(self.config,args,self.controller)
            with self.assertRaises(Rejected):inspect(self.config,replace(self.case,version=self.case.version+1),self.controller)
        self.assertEqual(before,self.snapshot())

    def test_live_or_reused_process_holds_without_signal(self):
        with patch('loop.native_stopped.process_identity',return_value='reused'),patch('os.kill',side_effect=AssertionError('signal')):
            with self.assertRaises(Rejected):inspect(self.config,self.case,self.controller)

    def test_wrong_owner_packet_generation_and_source_reject(self):
        for key,value in [('owner','unrelated'),('packet_hash','wrong'),('task_generation',88),('candidate_source','wrong'),('target_source',self.case.candidate_source)]:
            with self.subTest(key=key),self.assertRaises(Rejected):inspect(self.config,replace(self.case,**{key:value}),self.controller)

    def test_missing_readonly_proof_checkpoint_inputs_and_config_drift_reject(self):
        for spec in (self.case.checkpoint,self.case.turn_context,self.case.runtime_config,self.case.rehydration_events):
            path=Path(spec.path);old=path.read_bytes();path.write_bytes(old+b' ')
            with self.subTest(path=path.name),self.assertRaises(Rejected):inspect(self.config,self.case,self.controller)
            path.write_bytes(old)
        (Path(self.case.inputs)/'packet.json').write_text('changed')
        with self.assertRaises(Rejected):inspect(self.config,self.case,self.controller)

    def test_pending_input_and_newer_owner_gate_reject(self):
        self.store.db.execute("INSERT INTO human_inputs(owner,time,text,origin) VALUES(?,?,?,?)",(self.case.owner,'synthetic','correction','synthetic'))
        with self.assertRaisesRegex(Rejected,'pending'):inspect(self.config,self.case,self.controller,view=self.store)

    def test_atomic_fence_is_single_use_and_never_dispatches_or_finishes_recovery(self):
        result=commit_fence(self.store,self.config,self.case,self.controller)
        self.assertEqual(result['new_dispatch'],'NOT_AUTHORIZED')
        self.assertIsNotNone(inspect(self.config,self.case,self.controller,view=self.store)['fence_event'])
        with self.assertRaises(Rejected):commit_fence(self.store,self.config,self.case,self.controller)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='NATIVE_STOPPED_MAINTENANCE_FENCED'").fetchone()[0],1)
        self.assertEqual(self.store.task(self.tid)['state'],'CANDIDATE_SEALED')
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events WHERE kind='NATIVE_STARTUP' AND data LIKE '%MAINTENANCE_UNCERTAIN%'").fetchone()[0],1)

    def test_crash_before_commit_rolls_back_event_and_outbox(self):
        before=self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        outbox=self.store.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]
        original=self.store.event
        def interrupted(*args):original(*args);raise RuntimeError('synthetic precommit crash')
        with patch.object(self.store,'event',side_effect=interrupted),self.assertRaises(RuntimeError):commit_fence(self.store,self.config,self.case,self.controller)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],before)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],outbox)
        self.assertIsNone(inspect(self.config,self.case,self.controller)['fence_event'])

    def test_lost_response_is_inspected_not_replayed(self):
        commit_fence(self.store,self.config,self.case,self.controller)
        # A caller losing its response cannot change committed authority.
        with self.assertRaises(Rejected):commit_fence(self.store,self.config,self.case,self.controller)
        self.assertIsNotNone(inspect(self.config,self.case,self.controller,view=self.store)['fence_event'])

    def test_new_source_preparation_needs_fence_exact_scope_and_unused_runtime(self):
        runtime=str(self.root/'new-disposable-runtime')
        with self.assertRaises(Rejected):qualification_plan(self.config,self.case,self.controller,runtime)
        commit_fence(self.store,self.config,self.case,self.controller)
        plan=qualification_plan(self.config,self.case,self.controller,runtime,view=self.store)
        self.assertEqual(plan['new_dispatch'],'NOT_AUTHORIZED')
        with self.assertRaises(Rejected):prepare_qualification(self.store,self.config,self.case,self.controller,runtime,'old scope')
        result=prepare_qualification(self.store,self.config,self.case,self.controller,runtime,scope_line(self.case,runtime))
        self.assertEqual(result['new_dispatch'],'NOT_AUTHORIZED');self.assertFalse(Path(runtime).exists())
        with self.assertRaises(Rejected):prepare_qualification(self.store,self.config,self.case,self.controller,runtime,scope_line(self.case,runtime))

    def test_case_parser_rejects_unknown_type_fields_and_changed_id(self):
        value=asdict(self.case)
        self.assertEqual(StoppedCompaction.parse(value),self.case)
        for changed in ({**value,'kind':'RESUME_ANYWAY'},{**value,'extra':True},{**value,'version':True}):
            with self.assertRaises(Rejected):StoppedCompaction.parse(changed)

    def test_uncheckpointed_wal_holds_without_touching_shared_memory(self):
        self.store.event(None,'SYNTHETIC_LATER_EVENT',{})
        before=self.snapshot()
        with self.assertRaisesRegex(Rejected,'uncheckpointed WAL'):inspect(self.config,self.case,self.controller)
        self.assertEqual(before,self.snapshot())

    def test_rebound_writable_native_permission_proof_is_rejected(self):
        path=Path(self.case.turn_context.path)
        value=json.loads(path.read_text());value['payload']['sandbox_policy']['type']='workspace-write'
        path.write_text(json.dumps(value)+'\n')
        changed=replace(self.case,turn_context=FileBinding(str(path),digest(path.read_bytes())))
        with self.assertRaisesRegex(Rejected,'native read-only permissions'):inspect(self.config,changed,self.controller)

    def test_registry_rebound_to_an_unrelated_thread_is_rejected(self):
        path=Path(self.case.registry.path);value=json.loads(path.read_text());value['doer']['thread']='unrelated-thread';path.write_text(json.dumps(value))
        changed=replace(self.case,registry=FileBinding(str(path),digest(path.read_bytes())))
        with self.assertRaisesRegex(Rejected,'remount identity'):inspect(self.config,changed,self.controller)

    def test_existing_human_gate_is_preserved(self):
        self.store.db.execute("UPDATE tasks SET state='AWAITING_HUMAN' WHERE id=?",(self.tid,))
        with self.assertRaises(Rejected):inspect(self.config,self.case,self.controller,view=self.store)

    def test_original_contract_still_rejects_duplicate_requirement_ids(self):
        from loop.contract import validate
        proposal=test_controller.proposal();proposal['requirements']*=2
        with patch('subprocess.Popen',side_effect=AssertionError('process')),self.assertRaisesRegex(Rejected,'requirement ledger'):
            validate(proposal,self.root,{'text':'synthetic'},[])

    def test_other_native_owner_lock_prevents_fence_before_any_event(self):
        before=self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        with self.store.lock('native-startup'),self.assertRaisesRegex(Rejected,'active owner'):
            commit_fence(self.store,self.config,self.case,self.controller)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],before)

    def test_repeated_fence_cli_rejects_before_foreground_input_or_initializer(self):
        commit_fence(self.store,self.config,self.case,self.controller)
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        path=self.root/'case.json';path.write_text(json.dumps(asdict(self.case)))
        args=SimpleNamespace(binding=path,command='fence-stopped-maintenance',check=False)
        with patch('loop.cli.require_human_tty',side_effect=AssertionError('repeated input')),patch('loop.store.Store.__init__',side_effect=AssertionError('init')):
            with self.assertRaisesRegex(Rejected,'already committed'):run_cli(self.config,args,self.controller)
