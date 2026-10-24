import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from capri.broker import Denied
from capri.inference_relay import InferenceRelay
from capri.task_sandbox import TaskSandbox,validate_roots

class RelayPolicyTests(unittest.TestCase):
    def setUp(self):self.relay=InferenceRelay(None,'selected-model',{'exec'},lambda:True,max_requests=2)
    def request(self):return {'model':'selected-model','store':False,'stream':True,'input':[{'type':'additional_tools','tools':[{'type':'namespace','name':'collaboration','tools':[{'type':'function','name':'spawn_agent'}]},{'type':'namespace','name':'capri','tools':[{'type':'function','name':'exec'},{'type':'function','name':'forged'}]}]}]}
    def test_only_registered_native_tools_reach_the_model(self):
        data=self.relay.prepare(self.request())
        self.assertEqual(data['input'][0]['tools'][0]['name'],'capri')
        self.assertEqual([t['name'] for t in data['input'][0]['tools'][0]['tools']],['exec'])
    def test_forbidden_tool_and_forged_role_are_rejected_before_harness_dispatch(self):
        for item in ({'type':'function_call','namespace':'collaboration','name':'spawn_agent'},{'type':'custom_tool_call','namespace':'functions','name':'exec'},{'type':'function_call','namespace':'capri','name':'forged'},{'type':'message','role':'user'}):
            with self.subTest(item=item),self.assertRaises(Denied):self.relay.check_event({'type':'response.output_item.done','item':item})
        self.relay.check_event({'item':{'type':'function_call','namespace':'capri','name':'exec'}})
    def test_model_storage_budget_and_revocation_are_enforced(self):
        wrong=self.request();wrong['model']='other-model'
        with self.assertRaises(Denied):self.relay.prepare(wrong)
        self.relay.prepare(self.request());self.relay.prepare(self.request())
        with self.assertRaises(Denied):self.relay.prepare(self.request())
        self.relay.valid=lambda:False
        with self.assertRaises(Denied):self.relay.prepare(self.request())
    def test_root_lease_cannot_include_home_credentials_or_live_authority(self):
        for root in (str(Path.home()),str(Path.home()/'.codex'),str(Path(__file__).parent.parent)):
            with self.subTest(root=root),self.assertRaises(Denied):validate_roots([root])

@unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Actual user-manager/namespace qualification requires host run')
class HostTaskBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='capri-v2-boundary-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'project';self.root.mkdir()
        self.runner=TaskSandbox(self.base/'private-control')
        self.addAsyncCleanup(self.runner.stop)
    async def test_actual_read_write_job_cannot_read_credentials_fds_or_network(self):
        sentinel=self.base/'outside-secret';sentinel.write_text('FIXTURE-SENSITIVE-FD')
        fd=os.open(sentinel,os.O_RDONLY);os.set_inheritable(fd,True)
        try:
            code=f"import os,socket;from pathlib import Path; assert not Path({str(sentinel)!r}).exists();assert not Path('/home').exists();assert 'ACCESS_TOKEN' not in os.environ;assert 'CAPRI_UI_TOKEN' not in os.environ\ntry:data=os.read({fd},100)\nexcept OSError:data=b''\nassert b'FIXTURE-SENSITIVE-FD' not in data\ns=socket.socket();s.settimeout(.1)\ntry:s.connect(('127.0.0.1',443))\nexcept OSError:pass\nelse:raise AssertionError('network escaped')\nPath('fixed.txt').write_text('verified edit');assert Path('fixed.txt').read_text()=='verified edit';print('BOUNDARY-PASS')"
            result=await self.runner.run(['/usr/bin/python3','-c',code],[str(self.root)],str(self.root))
            self.assertEqual(result['exit_code'],0,result['output']);self.assertIn('BOUNDARY-PASS',result['output'])
            self.assertEqual((self.root/'fixed.txt').read_text(),'verified edit')
        finally:os.close(fd)
    async def test_swapping_a_root_to_a_symlink_does_not_redirect_the_bound_handle(self):
        outside=self.base/'outside';outside.mkdir();moved=self.base/'original-selected'
        original_spawn=self.runner.spawn
        async def swap(*args,**kwargs):
            self.root.rename(moved);self.root.symlink_to(outside,target_is_directory=True)
            return await original_spawn(*args,**kwargs)
        self.runner.spawn=swap
        result=await self.runner.run(['/usr/bin/python3','-c',"from pathlib import Path;Path('effect.txt').write_text('scoped')"],[str(self.root)],str(self.root))
        self.assertEqual(result['exit_code'],0,result['output'])
        self.assertFalse((outside/'effect.txt').exists());self.assertEqual((moved/'effect.txt').read_text(),'scoped')
    async def test_actual_command_cannot_write_outside_the_granted_mount(self):
        code="from pathlib import Path\nfor name in ['/not-granted','/usr/not-granted','/home/not-granted']:\n try:Path(name).write_text('denied')\n except OSError:pass\n else:raise AssertionError(name)\nprint('WRITE-DENIED')"
        result=await self.runner.run(['/usr/bin/python3','-c',code],[str(self.root)],str(self.root))
        self.assertEqual(result['exit_code'],0,result['output']);self.assertIn('WRITE-DENIED',result['output'])

    async def test_existing_hardlink_and_host_socket_are_rejected_before_execution(self):
        sentinel=self.base/'outside';sentinel.write_text('OUTSIDE-UNCHANGED')
        os.link(sentinel,self.root/'hardlink')
        with self.assertRaises(Denied):await self.runner.run(['/usr/bin/true'],[str(self.root)],str(self.root))
        self.assertEqual(sentinel.read_text(),'OUTSIDE-UNCHANGED');(self.root/'hardlink').unlink()
        import socket
        sock=socket.socket(socket.AF_UNIX)
        try:
            sock.bind(str(self.root/'host-control.sock'))
            with self.assertRaises(Denied):await self.runner.run(['/usr/bin/true'],[str(self.root)],str(self.root))
        finally:sock.close()
