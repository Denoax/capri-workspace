"""Synthetic complete restart/no-dispatch failure with real authority paths."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import test_completed_read_recovery
import test_context
from loop.context import Checkpoint, ContextState, derive_checkpoint
from loop.native import rehydration_payload, original_read_command
from loop.native_packet import read_guide, read_commands
from loop.native_receipts import ReceivedReceipts
from loop.native_startup import StartupJournal
from loop.native_read_recovery import (inspect, reconcile, admit, publish, confirmation,
    inspect_launch, observed_authority, KINDS)
from loop.util import Rejected, digest, identity, tree, write_json


class MaintenancePreconditionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.first=test_completed_read_recovery.CompletedReadRecoveryTests(
            'test_inspection_has_no_state_file_or_process_effects')
        self.first.native_recovery_inputs=True
        self.first.setUp()
        f=self.first;self.store=f.f.store;self.root=f.f.root;self.runtime=f.f.root_runtime
        self.process=patch('loop.native_maintenance_recovery.process_identity',return_value=None)
        self.process.start()
        # All timestamps are a deterministic logical schedule relative to one
        # setup instant; no sleep or real inference is required.
        self.base=datetime.now(timezone.utc)
        self.clock=[0]
        self.time_patch=patch('loop.store.now',side_effect=lambda:(self.base+timedelta(seconds=self.clock[0])).isoformat())
        self.time_patch.start()
        self.prepared=f.ready();self.parent=json.loads(Path(self.prepared['receipt']).read_text())
        self.old_config=copy.deepcopy(f.config)
        self.old_config_path=self.root/'completed-runtime-config.json'
        write_json(self.old_config_path,self.old_config)
        self.journal=StartupJournal(self.store,self.parent['maintenance_binding']['operation'],self.parent['maintenance_binding'])
        self.journal.append('RUNTIME_RESUME_INTENT',dict(receipt_sha256=self.prepared['receipt_sha256']))
        self.rows=copy.deepcopy(self.parent['registry'])
        for n,(role,row) in enumerate(self.rows.items()):
            old=self.parent['registry'][role]
            row.update(generation=old['generation']+1,pid=2000000+n,process_identity='completed-'+role)
            if role=='reviewer':row['thread']='next-empty-reviewer'
            else:row['lineage']=old['lineage']+[dict(old_thread=old['thread'],new_thread=row['thread'],
                old_generation=old['generation'],new_generation=row['generation'])]
        write_json(self.runtime/'registry.json',self.rows)
        supervisor=dict(pid=2100000,process_identity='completed-supervisor',
            source=self.parent['maintenance_binding']['source_hash'],
            maintenance_operation=self.parent['maintenance_binding']['operation'],
            cmdline_hex=(b'\0'.join(x.encode() for x in ['/usr/bin/python3',
                str(f.controller/'native_loopctl.py'),'--config',str(self.old_config_path),'resume-runtime',
                '--prepared',self.prepared['receipt'],'--prepared-sha256',self.prepared['receipt_sha256']])+b'\0').hex())
        write_json(self.runtime/'supervisor.json',supervisor)
        (self.runtime/'operator.key').write_text('CONTROLLED_NEW_OPERATOR_KEY')
        write_json(self.runtime/'terminal-registry-closed-after-resume.json',
            {**{r:dict(pid=2200000+n,process_identity='closed-new-'+r,thread=v['thread'],generation=v['generation'])
                for n,(r,v) in enumerate(self.rows.items())},'_server':dict(pid=2300000,process_identity='closed-new-server')})
        self.cps={}
        for role,key in [('thinker','owner_checkpoint'),('doer','doer_checkpoint')]:
            parent=Checkpoint(Path(self.parent[key]),self.root)
            authority,transition=observed_authority(json.loads(parent.path.read_text()),
                self.parent['registry'][role],self.rows[role])
            name=('controller-restart-owner-'+identity(authority)+'.json') if role=='thinker' else 'derived-completed.json'
            target=Checkpoint(parent.path.parent/name,self.root)
            receipt=derive_checkpoint(parent,target,authority,transition)
            self.cps[role]=(target,authority,receipt)
        self.task=self.store.task(f.f.tid)
        self.originals=f.originals
        self.owner_expected=dict(owner='owner',checkpoint=self.cps['thinker'][0].validate(self.cps['thinker'][1]),
            originals=self.originals)
        self.ids={name:f'00000000-0000-0000-0000-{n:012d}' for n,name in enumerate(
            ['probe','read','doer_probe','doer_read'],1)}
        self.paths={}
        self.messages={}
        self.make_capture('probe','thinker','No tools. Final exactly READY.','READY',[],1)
        commands=read_commands(f.packet)
        bodies=[(f.f.inputs/'current-context'/s['name']).read_text() for s in f.packet['sections']]
        self.make_capture('read','thinker',read_guide(f.packet)+'\nReturn exactly '+json.dumps(self.owner_expected),
            json.dumps(self.owner_expected),list(zip(commands,bodies)),2)
        sessions=self.runtime/'thinker/runtime/sessions';sessions.mkdir(parents=True)
        rows=[dict(type='turn_context',payload=dict(turn_id=self.ids['read']))]+[
            dict(type='response_item',payload=dict(type='function_call_output',output=json.dumps(dict(output=body))))
            for body in bodies]
        (sessions/('rollout-'+self.rows['thinker']['thread']+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        expected=dict(packet_hash=self.task['content_hash'],source_hash=identity(self.parent['source_before_stop']),
            requirements_hash=self.task['packet']['requirements_hash'],thread=self.rows['doer']['thread'],
            role_generation=self.rows['doer']['generation'],task_generation=self.task['generation'])
        prompt='First send commentary ACK:'+self.task['content_hash']+'\nRead-only telemetry probe. Use no tools. Then final answer must be only this exact JSON: '+json.dumps(expected)
        self.make_capture('doer_probe','doer',prompt,json.dumps(expected),[],4)
        cp,authority,_=self.cps['doer']
        backend=SimpleNamespace(inputs=f.f.inputs,workspace=f.f.workspace)
        payload,expected,originals=rehydration_payload(self.task,backend,authority,cp.validate(authority))
        files={p:dict(sha256=h,content=(f.f.inputs/p.removeprefix('/inputs/')).read_text()) for p,h in originals.items()}
        self.make_capture('doer_read','doer',payload[0]['text'],json.dumps(expected),
            [(original_read_command(originals),json.dumps(dict(files=files)))],6)
        for role,row in self.rows.items():
            folder=self.runtime/role/str(row['generation']);folder.mkdir(parents=True)
            writer=ReceivedReceipts(folder,role,row['generation'])
            seq=writer.received(b'{"id":1,"result":{}}\n',row['thread']);writer.result(seq,'VALIDATED')
            for label in self.paths:
                if ('doer' if label.startswith('doer') else 'thinker')!=role:continue
                for record in self.messages[label]:
                    raw=(json.dumps(record['message'])+'\n').encode()
                    seq=writer.received(raw,row['thread']);writer.result(seq,'VALIDATED')
        self.store.event(None,'NATIVE_CAPABILITY_STAGED_HELD',dict(owner='owner'))
        self.store.event(None,'NATIVE_THINKER_REGISTERED',dict(owner='owner',thread=self.rows['thinker']['thread'],generation=self.rows['thinker']['generation']))
        self.store.event(None,'NATIVE_THINKER_CAPABILITY_HELD',dict(owner='owner'))
        for label in ['probe','read']:
            self.store.event(None,'NATIVE_OWNER_DISPATCH',dict(owner='owner',probe=label=='probe',
                thread=self.rows['thinker']['thread'],capture=str(self.paths[label].parent)))
        self.store.event(self.task['id'],'RECOVERY_CHECKPOINT_DERIVED',self.cps['doer'][2])
        self.store.event(self.task['id'],'READ_ONLY_PROBE_INTENT',dict(role='doer',thread=self.rows['doer']['thread'],capture=str(self.paths['doer_probe'].parent)))
        for kind in ['REHYDRATION_INTENT','REHYDRATION_VALIDATED']:
            self.store.event(self.task['id'],kind,dict(role='doer',checkpoint=self.cps['doer'][0].validate(self.cps['doer'][1]),capture=str(self.paths['doer_read'].parent)))
        self.clock[0]=10
        self.resumed=self.journal.append('RUNTIME_RESUMED',dict(roles=self.rows))
        ledger=self.runtime/'doer/tasks'/digest(self.task['id'].encode())/'context-ledger.json'
        binding=test_context.binding(thread=self.rows['doer']['thread'],turn=self.ids['doer_read'],task=self.task['id'],
            role_generation=self.rows['doer']['generation'],server=str(self.rows['doer']['pid'])+':'+self.rows['doer']['process_identity'],
            process=self.rows['doer']['process_identity'],producer='codex-cli/0.163.0',
            schema='CLI_SCHEMA_PROFILE:d7bf28b381dacc32a837abd2c4829e9fe28f78e6c8e8380dff7112eb8d9d1b9f')
        state=ContextState(ledger,binding,clock=lambda:(self.base+timedelta(seconds=6)).timestamp())
        usage=test_context.usage();usage['params'].update(threadId=binding.thread,turnId=binding.turn)
        state.update(usage,binding,0,(self.base+timedelta(seconds=6)).timestamp())
        self.request=dict(task=self.task['id'],version=self.task['version'],owner=self.task['owner'],
            packet_hash=self.task['content_hash'],source_hash=identity(self.parent['source_before_stop']),
            controller_hash=self.parent['maintenance_binding']['controller_hash'],supervisor_pid=supervisor['pid'],
            supervisor_identity=supervisor['process_identity'],role='doer',thread=self.rows['doer']['thread'],
            role_generation=self.rows['doer']['generation'])
        request_path=self.root/'maintenance-request.json';write_json(request_path,self.request)
        key=identity(dict(action='compact-role',binding=self.request));self.clock[0]=100
        self.intent=self.journal.append('MAINTENANCE_INTENT',dict(key=key,action='compact-role',role='doer',
            thread=self.rows['doer']['thread'],generation=self.rows['doer']['generation']))
        self.failure=self.journal.append('MAINTENANCE_UNCERTAIN',dict(key=key,role='doer',error='Not classification authority'))
        self.store.event(None,'NATIVE_CAPABILITY_REVOKED',dict(owner='owner'))
        self.controller=self.root/'maintenance-source/controller';shutil.copytree(f.controller,self.controller)
        (self.controller/'loop/native_operator.py').write_text('controlled repaired operator')
        (self.controller/'loop/native_maintenance_recovery.py').write_text('controlled bounded recovery')
        self.config=dict(self.old_config,controller=str(self.controller))
        self.binding=dict(schema=2,parent_config=f.file(self.old_config_path),parent_receipt=f.file(Path(self.prepared['receipt'])),
            review={},approval=f.binding['approval'],intent_event=self.intent,failure_event=self.failure,resume_event=self.resumed,
            registry=f.file(self.runtime/'registry.json'),supervisor=f.file(self.runtime/'supervisor.json'),captures={},
            checkpoints=dict(owner=f.file(Path(self.parent['owner_checkpoint'])),doer=f.file(Path(self.parent['doer_checkpoint'])),
                observed_owner=f.file(self.cps['thinker'][0].path),completed_doer=f.file(self.cps['doer'][0].path)),
            maintenance_request=f.file(request_path),context_ledger=f.file(ledger),operator_key=f.file(self.runtime/'operator.key'),
            source_hash=identity(tree(self.controller.parent)),controller_hash=identity(tree(self.controller)),config_hash=identity(self.config))
        self.seal()

    def make_capture(self,label,role,prompt,final,commands,second):
        turn=self.ids[label];row=self.rows[role]
        values=[('turn/started',dict(turn=dict(id=turn,status='inProgress'))),
            ('item/completed',dict(item=dict(type='userMessage',id='user',content=[dict(type='text',text=prompt)])))]
        for n,(command,body) in enumerate(commands):
            item=dict(type='commandExecution',id='read-'+str(n),command=command,exitCode=0,status='completed',aggregatedOutput=body)
            values.extend((method,dict(item=item)) for method in ['item/started','item/completed'])
        values.extend([('item/completed',dict(item=dict(type='agentMessage',id='final',phase='final_answer',text=final))),
            ('turn/completed',dict(turn=dict(id=turn,status='completed',error=None)))])
        records=[]
        for method,params in values:
            params.update(threadId=row['thread'],turnId=turn)
            records.append(dict(role=role,generation=row['generation'],time=(self.base+timedelta(seconds=second)).isoformat(),
                message=dict(method=method,params=params)))
        folder=self.root/'artifacts/setup/native'/('completed-'+label);folder.mkdir(parents=True)
        path=folder/'events.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in records))
        self.paths[label]=path;self.messages[label]=records

    def seal(self):
        path=self.root/'maintenance-proof-review.zip';manifest={}
        with zipfile.ZipFile(path,'w') as archive:
            for label,capture in self.paths.items():
                spec=self.first.file(capture);self.binding['captures'][label]=spec
                raw=json.dumps(dict(original_path=spec['path'],original_sha256=spec['sha256'])).encode()
                name='actual-native/'+label+'-capture-reference.json';archive.writestr(name,raw);manifest[name]=dict(sha256=digest(raw))
            archive.writestr('MANIFEST.json',json.dumps(dict(files=manifest)))
        self.binding['review']=self.first.file(path)

    def tearDown(self):
        self.time_patch.stop();self.process.stop();self.first.tearDown()

    def check(self):return inspect(self.config,self.binding,self.controller)

    def ready(self):
        result=self.check();reconcile(self.store,self.config,self.binding,self.controller)
        admit(self.store,self.config,self.binding,self.controller,confirmation(self.binding,result))
        return publish(self.store,self.binding)

    def test_proved_precondition_failure_is_pure_and_does_not_resolve_history(self):
        before=self.store.db.execute('select count(*) from events').fetchone()[0]
        result=self.check();self.assertEqual(result['proof']['classification'],'READ_MAINTENANCE_PRECONDITION_REJECTION_NO_NEW_MODEL_TURN')
        self.assertEqual(before,self.store.db.execute('select count(*) from events').fetchone()[0])
        self.assertEqual(self.journal.records()[-1]['milestone'],'MAINTENANCE_UNCERTAIN')

    def test_new_source_publication_keeps_completed_checkpoints_and_correct_operator_key(self):
        result=self.ready();saved,_=inspect_launch(self.config,Path(result['receipt']),result['receipt_sha256'],self.controller)
        self.assertEqual(saved['registry'],self.rows)
        self.assertEqual(saved['operator_key_sha256'],self.binding['operator_key']['sha256'])
        self.assertNotEqual(saved['operator_key_sha256'],self.parent['operator_key_sha256'])
        self.assertEqual(self.journal.records()[-1]['milestone'],'MAINTENANCE_UNCERTAIN')

    def test_unexpected_new_model_turn_is_not_a_precondition_only_failure(self):
        row=self.rows['doer'];path=self.runtime/'doer'/str(row['generation'])/'received-frames.jsonl'
        value=dict(schema=1,sequence=9999,phase='RECEIVED',time=(self.base+timedelta(seconds=101)).isoformat(),
            role='doer',generation=row['generation'],envelope=dict(method='turn/started',turn=dict(id='untracked')))
        with path.open('a') as stream:
            stream.write(json.dumps(value)+'\n'+json.dumps(dict(schema=1,sequence=9999,phase='VALIDATED',time=value['time']))+'\n')
        with self.assertRaisesRegex(Rejected,'new model'):self.check()

    def test_missing_completed_read_terminal_cannot_be_reclassified(self):
        path=self.paths['doer_read'];rows=path.read_text().splitlines();path.write_text('\n'.join(rows[:-1])+'\n');self.seal()
        with self.assertRaises(Rejected):self.check()

    def test_nonstale_or_pending_compaction_ledger_cannot_use_this_profile(self):
        path=Path(self.binding['context_ledger']['path']);raw=path.read_bytes()
        for kind in ['fresh','compaction']:
            value=json.loads(raw)
            if kind=='fresh':value['state']['reading']['observed_at']=(self.base+timedelta(seconds=99)).timestamp()
            else:value['state']['compaction']={'unresolved':'compaction'}
            value['sha256']=identity(value['state']);write_json(path,value);self.binding['context_ledger']=self.first.file(path)
            with self.subTest(kind=kind),self.assertRaises(Rejected):self.check()

    def test_changed_request_or_wrong_readonly_phase_reject(self):
        path=Path(self.binding['maintenance_request']['path']);value=json.loads(path.read_text());value['role']='thinker';write_json(path,value)
        self.binding['maintenance_request']=self.first.file(path)
        with self.assertRaises(Rejected):self.check()

    def test_missing_or_rejected_received_frame_is_not_no_effect_proof(self):
        row=self.rows['reviewer'];path=self.runtime/'reviewer'/str(row['generation'])/'received-frames.jsonl'
        rows=[json.loads(x) for x in path.read_text().splitlines()];rows[-1]['phase']='REJECTED';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with self.assertRaisesRegex(Rejected,'frame'):self.check()

    def test_changed_source_or_active_writer_hold(self):
        self.store.db.execute('UPDATE capabilities SET enabled=1')
        with self.assertRaises(Rejected):self.check()

    def test_same_failed_parent_cannot_get_second_source(self):
        reconcile(self.store,self.config,self.binding,self.controller)
        (self.controller/'loop/native_operator.py').write_text('different successor')
        self.binding.update(source_hash=identity(tree(self.controller.parent)),controller_hash=identity(tree(self.controller)))
        with self.assertRaisesRegex(Rejected,'different successor'):self.check()

    def test_lost_publication_is_recoverable_without_repeating_authority(self):
        result=self.check();reconcile(self.store,self.config,self.binding,self.controller)
        admit(self.store,self.config,self.binding,self.controller,confirmation(self.binding,result))
        before=self.store.db.execute('select count(*) from events').fetchone()[0]
        with patch('loop.native_read_recovery.atomic',side_effect=OSError('controlled publish loss')):
            with self.assertRaises(OSError):publish(self.store,self.binding)
        first=publish(self.store,self.binding);second=publish(self.store,self.binding)
        self.assertEqual(first,second);self.assertEqual(before,self.store.db.execute('select count(*) from events').fetchone()[0])


if __name__=='__main__':unittest.main()
