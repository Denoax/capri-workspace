import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest

from capri.adapters import Adapters
from capri.broker import Denied


@unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Explicit host integration run required')
class HostIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'project';self.root.mkdir()
        self.adapters=Adapters()
        self.assertEqual(await self.adapters.qualify_sandbox(),'isolation-denials-pass')

    async def test_real_namespace_denies_credential_sentinel_and_desktop_sockets(self):
        secret=Path(self.tmp.name)/'owner-credential-sentinel';secret.write_text('never read this')
        code=f"import os; assert not os.path.exists({str(secret)!r}); assert not os.path.exists('/run/user'); assert not os.path.exists('/home'); print('denied')"
        result=await self.adapters.command(self.adapters.sandbox_argv(str(self.root),['/usr/bin/python3','-c',code]))
        self.assertEqual(result,'denied')

    async def test_real_network_denial_includes_loopback(self):
        code="import socket\nfor a in [('1.1.1.1',443),('127.0.0.1',42424)]:\n s=socket.socket();s.settimeout(.3)\n try:s.connect(a)\n except OSError:pass\n else:raise AssertionError('egress escaped')\nprint('denied')"
        result=await self.adapters.command(self.adapters.sandbox_argv(str(self.root),['/usr/bin/python3','-c',code]))
        self.assertEqual(result,'denied')

    async def test_inheritable_secret_fd_is_not_available_to_job(self):
        secret=Path(self.tmp.name)/'secret';secret.write_text('SENTINEL-NOT-FOR-JOB')
        fd=os.open(secret,os.O_RDONLY);os.set_inheritable(fd,True)
        try:
            code=f"import os\ntry:r=os.read({fd},100)\nexcept OSError:r=b''\nassert b'SENTINEL-NOT-FOR-JOB' not in r\nprint('denied')"
            result=await self.adapters.command(self.adapters.sandbox_argv(str(self.root),['/usr/bin/python3','-c',code]))
            self.assertEqual(result,'denied')
        finally:os.close(fd)

    async def test_selected_project_is_read_only_and_home_not_mounted(self):
        code="from pathlib import Path\ntry:Path('/work/forbidden').write_text('bad')\nexcept OSError:pass\nelse:raise AssertionError('write escaped')\nprint('denied')"
        result=await self.adapters.command(self.adapters.sandbox_argv(str(self.root),['/usr/bin/python3','-c',code]))
        self.assertEqual(result,'denied');self.assertFalse((self.root/'forbidden').exists())

    async def test_resource_bounded_real_work_job_returns_verified_output(self):
        result=await self.adapters.run('work.run',{'root':str(self.root),'argv':['/usr/bin/python3','-c','print("real isolated work")']})
        self.assertEqual(result['exit_code'],0);self.assertEqual(result['output'],'real isolated work')

    async def test_shell_metacharacters_in_app_argument_do_not_expand(self):
        target=self.root/'must-not-exist'
        with self.assertRaises(Denied):
            await self.adapters.run('desktop.open',{'app':f'$(touch {target})'})
        self.assertFalse(target.exists())

class MediaBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_player_acknowledgement_waits_for_observed_state_change(self):
        class DeferredPlayer(Adapters):
            def __init__(self):
                super().__init__();self.player='fixture';self.playback='Playing'
            async def players(self):return ['fixture']
            async def command(self,argv,**kwargs):
                if argv[-1]=='pause':
                    asyncio.get_running_loop().call_later(.01,setattr,self,'playback','Paused')
                    return ''
                return self.playback
        result=await DeferredPlayer().run('media.control',{'command':'pause'})
        self.assertEqual(result['status'],'Paused')
