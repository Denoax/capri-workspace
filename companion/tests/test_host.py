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

@unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Explicit native host lifecycle run required')
class HostWatcherLifecycleTests(unittest.TestCase):
    def test_native_watcher_exits_when_its_parent_is_killed(self):
        import select
        import signal
        import subprocess
        import time
        watcher=Path(os.environ.get('CAPRI_TEST_WATCHER',str(Path(__file__).parent.parent/'capri/session_watch.py')))
        readfd,writefd=os.pipe()
        parent_code="import os,subprocess,sys,time; p=subprocess.Popen(['/usr/bin/python3',sys.argv[1],str(os.getpid())],stdout=int(sys.argv[2]),stderr=subprocess.DEVNULL); print(p.pid,flush=True); time.sleep(30)"
        parent=subprocess.Popen(['/usr/bin/python3','-u','-c',parent_code,str(watcher),str(writefd)],stdout=subprocess.PIPE,text=True,pass_fds=(writefd,))
        child=None
        try:
            child=int(parent.stdout.readline().strip())
            ready,_,_=select.select([readfd],[],[],5)
            self.assertTrue(ready,'Native watcher did not initialize')
            state=json.loads(os.read(readfd,1024));self.assertIn('locked',state)
            parent.kill();parent.wait(timeout=3)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                path=Path(f'/proc/{child}/stat')
                try:
                    state=path.read_text().rsplit(') ',1)[1].split()[0]
                except (FileNotFoundError,ProcessLookupError):
                    break
                if state=='Z':break
                time.sleep(.02)
            else:self.fail('Native session watcher survived the death of its exact parent')
        finally:
            if parent.poll() is None:parent.kill();parent.wait(timeout=3)
            parent.stdout.close();os.close(readfd);os.close(writefd)
            if child and Path(f'/proc/{child}/cmdline').exists():
                command=Path(f'/proc/{child}/cmdline').read_bytes()
                if str(watcher).encode() in command and str(parent.pid).encode() in command:
                    try:os.kill(child,signal.SIGTERM)
                    except ProcessLookupError:pass

class FocusBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_lua_expression_cannot_enter_window_address(self):
        with self.assertRaises(Denied):
            await Adapters().run('desktop.focus',{'address':'0x1"}); os.execute("touch /tmp/must-not-execute") --'})

@unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Real user-service crash check requires explicit host run')
class HostJobLifetimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_confined_job_stops_when_its_owner_process_dies(self):
        import sys
        import time
        tmp=tempfile.TemporaryDirectory(prefix='capri-job-lifetime-');self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)/'project';root.mkdir()
        code="import asyncio; from capri.adapters import Adapters\nasync def main():\n a=Adapters(); assert await a.qualify_sandbox()=='isolation-denials-pass'; print('OWNER_READY',flush=True); await a.run('work.run',{'root':"+repr(str(root))+",'argv':['/usr/bin/python3','-c','import time; time.sleep(20)']})\nasyncio.run(main())"
        owner=await asyncio.create_subprocess_exec(sys.executable,'-B','-c',code,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        unit=None
        async def command(*args):
            p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            out,_=await p.communicate();return out.decode().strip()
        try:
            self.assertEqual((await asyncio.wait_for(owner.stdout.readline(),5)).strip(),b'OWNER_READY')
            for _ in range(60):
                names=await command('systemctl','--user','list-units','capri-job-*','--no-legend','--plain')
                for line in names.splitlines():
                    candidate=line.split()[0]
                    details=await command('systemctl','--user','show',candidate,'-p','ExecStart','--value')
                    if str(root) in details:unit=candidate;break
                if unit:break
                await asyncio.sleep(.05)
            self.assertIsNotNone(unit,'Real test job did not start')
            owner.kill();await owner.wait()
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                state=await command('systemctl','--user','show',unit,'-p','ActiveState','--value')
                if state not in ('active','activating'):break
                await asyncio.sleep(.05)
            else:self.fail('Confined work service survived loss of its exact owner process')
        finally:
            if owner.returncode is None:owner.kill();await owner.wait()
            if unit:await command('systemctl','--user','stop',unit)
