import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from loop import native_owner_fence as fence
from loop.store import Store
from loop.util import Rejected, NeedsInput, identity, digest, tree


def spec(path):
    return dict(path=str(path),sha256=digest(path.read_bytes()))


class OwnerFenceTests(unittest.TestCase):
    def fixture(self, root):
        home=root/'home';state=Store(home);owner='owner'
        old=root/'old';controller=old/'controller';controller.mkdir(parents=True);(controller/'entry.py').write_text('old')
        new=root/'new';current=new/'controller';current.mkdir(parents=True);(current/'entry.py').write_text('new')
        repo=root/'repo';repo.mkdir();(repo/'source.py').write_text('unchanged')
        workspace=home/'workspace';workspace.mkdir();(workspace/'source.py').write_text('unchanged')
        inputs=home/'inputs/old';inputs.mkdir(parents=True);(inputs/'policy.md').write_text('preserve')
        core=home/'core.json';core.write_text('{}')
        settings=dict(model='gpt-6.1-sol',efforts=dict(thinker='medium',doer='medium',reviewer='high'))
        old_config=dict(home=str(home),controller=str(controller),settings=settings)
        prior_config=home/'prior-config.json';prior_config.write_text(json.dumps(old_config))
        old_binding=dict(owner=owner,home=str(home),source_hash=identity(tree(old)),controller=str(controller),
            controller_hash=identity(tree(controller)),config_hash=identity(old_config),operation='old-launch',
            predecessor_receipt=spec(core),workspace=str(workspace),inputs=str(inputs))
        old_receipt=home/'old-receipt.json';old_receipt.write_text(json.dumps(dict(binding=old_binding,scope_event=2,scope_text='correct old scope')))
        runtime=home/'runtime';runtime.mkdir()
        rows={role:dict(pid=1000000000+n,process_identity='synthetic-stopped',thread='thread-'+role,
            generation=n+1,phase='read',model='gpt-6.1-sol',effort=settings['efforts'][role],
            endpoint='unix://'+str(runtime/(role+'.sock'))) for n,role in enumerate(['thinker','doer','reviewer'])}
        registry=runtime/'registry.json';registry.write_text(json.dumps(rows))
        supervisor=runtime/'supervisor.json';supervisor.write_text(json.dumps(dict(pid=1000000010)))
        owner_binding=runtime/'owner-binding.json';owner_binding.write_text(json.dumps(dict(owner=owner,workspace=str(workspace),
            source_hash=identity(tree(repo)),inputs=tree(inputs),scope=dict(repo=str(repo),request=dict(native_maintenance=dict(sha256=digest(old_receipt.read_bytes())))))))
        context=dict(identity=dict(thread=rows['thinker']['thread'],turn='work-turn'))
        owner_context=runtime/'owner-context.json';owner_context.write_text(json.dumps(dict(state=context,sha256=identity(context))))
        captures=[]
        for name in ['probe','work']:
            path=home/'captures'/name;path.mkdir(parents=True);file=path/'events.jsonl';file.write_text(json.dumps(dict(synthetic=name))+'\n');captures.append(path)
        state.event(None,'RECONTRACT_THINKER_INTENT',dict(owner=owner))
        def startup(milestone,details):
            state.event(None,'NATIVE_STARTUP',dict(operation='old-launch',parameters=old_binding,milestone=milestone,details=details))
        startup('SCOPE_CAPTURED',dict(text='correct old scope',origin='FOREGROUND_CONTROLLING_TTY'))
        startup('SLOTS_CREATED',dict(registry=rows))
        for n,path in enumerate(captures):state.event(None,'NATIVE_OWNER_DISPATCH',dict(owner=owner,probe=n==0,capture=str(path)))
        startup('FAILED_OR_UNCERTAIN',dict(classification='EXECUTION_REQUIRES_RECONCILIATION',error='Native turn exceeded exposed tool budget',last_proved='WORK_DISPATCH_INTENT',task=None))
        state.event(None,'NATIVE_CAPABILITY_REVOKED',dict(owner=owner))
        events=[dict(r) for r in state.db.execute('SELECT seq,kind,data FROM events ORDER BY seq')]
        for row in events:row['data']=json.loads(row['data'])
        state.close()
        config=dict(home=str(home),controller=str(current),settings=settings)
        binding=dict(schema=1,route='NATIVE_OWNER_INTAKE_FENCE',operation='synthetic-fence',owner=owner,
            source_hash=identity(tree(new)),controller_hash=identity(tree(current)),config_hash=identity(config),
            native_receipt=spec(old_receipt),prior_config=spec(prior_config),events_hash=identity(events),
            registry=spec(registry),supervisor=spec(supervisor),owner_binding=spec(owner_binding),owner_context=spec(owner_context),
            terminal_records=[],absent_endpoints=[str(runtime/'ui.sock')])
        profile=dict(receipt=digest(old_receipt.read_bytes()),source=identity(tree(old)),
            captures=[digest((path/'events.jsonl').read_bytes()) for path in captures],claim=1,scope=2,cutoff=7)
        return config,binding,current,profile

    @contextlib.contextmanager
    def tty(self,binding):
        # Synthetic fixture in a disposable Store; never live human authority.
        yield SimpleNamespace(write=lambda text:None,flush=lambda:None,
            readline=lambda:'fence '+binding['operation']+' '+identity(binding)+'\n')

    def test_check_is_read_only_and_has_no_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            config,binding,current,profile=self.fixture(Path(temp));db=Path(config['home'])/'state/workflow.sqlite3';before=db.read_bytes()
            with patch.object(fence,'REVIEWED',profile),patch.object(fence,'Store',side_effect=AssertionError('Check must not initialize Store')):
                result=fence.fence(config,binding,current,check_only=True)
            self.assertEqual(result['status'],'OWNER_INTAKE_FENCE_CHECKED')
            self.assertEqual(result['model_dispatch'],'NOT_STARTED')
            self.assertEqual(db.read_bytes(),before)

    def test_fence_duplicate_and_projection_crash_preserve_one_event(self):
        with tempfile.TemporaryDirectory() as temp:
            config,binding,current,profile=self.fixture(Path(temp))
            with patch.object(fence,'REVIEWED',profile),patch.object(fence,'require_human_tty',lambda:self.tty(binding)):
                with patch.object(fence,'atomic',side_effect=OSError('projection interrupted')):
                    with self.assertRaisesRegex(OSError,'interrupted'):fence.fence(config,binding,current)
                with patch.object(fence,'require_human_tty',side_effect=AssertionError('No repeated human input')):
                    first=fence.fence(config,binding,current);second=fence.fence(config,binding,current)
            self.assertEqual(first,second)
            self.assertEqual(first['new_dispatch'],'NOT_AUTHORIZED')
            state=Store(config['home'])
            self.assertEqual(state.db.execute("SELECT count(*) FROM events WHERE kind='NATIVE_OWNER_INTAKE_FENCED'").fetchone()[0],1)
            self.assertEqual(state.db.execute("SELECT count(*) FROM events WHERE kind='RECONTRACT_THINKER_INTENT'").fetchone()[0],1)
            state.close()

    def test_live_reused_process_endpoint_source_and_capture_changes_hold(self):
        for failure in ['live','endpoint','source','capture','registry','extra_turn','question']:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);config,binding,current,profile=self.fixture(root)
                if failure=='endpoint':Path(binding['absent_endpoints'][0]).touch()
                elif failure=='source':(root/'repo/source.py').write_text('unknown write')
                elif failure=='capture':(Path(config['home'])/'captures/work/events.jsonl').write_text('unknown tool')
                elif failure=='registry':Path(binding['registry']['path']).write_text('{}')
                elif failure in ('extra_turn','question'):
                    state=Store(config['home'])
                    if failure=='extra_turn':state.event(None,'NATIVE_OWNER_DISPATCH',dict(owner='owner'))
                    else:state.ask_question('owner','key',1,'Real ambiguity')
                    state.close()
                with patch.object(fence,'REVIEWED',profile),patch.object(fence,'process_identity',return_value='reused' if failure=='live' else None):
                    with self.assertRaises(Rejected):fence.fence(config,binding,current,check_only=True)

    def test_operation_key_cannot_change_parameters(self):
        with tempfile.TemporaryDirectory() as temp:
            config,binding,current,profile=self.fixture(Path(temp))
            with patch.object(fence,'REVIEWED',profile),patch.object(fence,'require_human_tty',lambda:self.tty(binding)):
                fence.fence(config,binding,current)
                binding['absent_endpoints'].append('/different-binding')
                with self.assertRaisesRegex(Rejected,'key reused'):fence.fence(config,binding,current,check_only=True)


if __name__=='__main__':
    unittest.main()
