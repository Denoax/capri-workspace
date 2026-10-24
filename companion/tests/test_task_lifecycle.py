import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from capri.task_sandbox import RootHandle,TaskSandbox

@unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Real user-manager lifecycle checks require host run')
class TaskLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='capri-lifecycle-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'project';self.root.mkdir()
        self.runner=TaskSandbox(self.base/'control');self.addAsyncCleanup(self.runner.stop)
    async def test_regular_directory_replacement_keeps_the_original_owner_grant(self):
        handle=RootHandle(str(self.root));self.addCleanup(handle.close)
        old=self.base/'original';self.root.rename(old);self.root.mkdir()
        result=await self.runner.run(['/usr/bin/python3','-c',"from pathlib import Path;Path('effect').write_text('original')"],[str(self.root)],str(self.root),held_handles=[handle])
        self.assertEqual(result['exit_code'],0,result['output'])
        self.assertEqual((old/'effect').read_text(),'original');self.assertFalse((self.root/'effect').exists())
    async def test_cancellation_stops_the_entire_scope(self):
        task=asyncio.create_task(self.runner.run(['/usr/bin/python3','-c',"import time;from pathlib import Path;Path('ready').write_text('yes');time.sleep(60);Path('escaped').write_text('no')"],[str(self.root)],str(self.root)))
        async with asyncio.timeout(10):
            while not (self.root/'ready').exists():await asyncio.sleep(.02)
        units=[v[1] for v in self.runner.children.values()]
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(self.runner.children);self.assertFalse((self.root/'escaped').exists())
        for unit in units:
            p=await asyncio.create_subprocess_exec('/usr/bin/systemctl','--user','is-active',unit,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            state,_=await p.communicate();self.assertNotEqual(state.strip(),b'active')
    async def test_sigkill_of_actual_owner_kills_its_confined_descendants(self):
        # The subprocess is the actual coordinator owner, not an asserted PID fixture.
        script=self.base/'owner.py'
        script.write_text("import asyncio,json,sys\nfrom pathlib import Path\nfrom capri.task_sandbox import TaskSandbox\nasync def main():\n r=TaskSandbox(Path(sys.argv[1])/'private')\n t=asyncio.create_task(r.run(['/usr/bin/python3','-c',\"import time;from pathlib import Path;Path('ready').write_text('yes');time.sleep(60);Path('escaped').write_text('no')\"],[sys.argv[2]],sys.argv[2]))\n while not r.children:await asyncio.sleep(.01)\n p,u,s=next(iter(r.children.values()))\n Path(sys.argv[1],'child.json').write_text(json.dumps({'pid':p.pid,'unit':u}))\n await t\nasyncio.run(main())\n")
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
        owner=await asyncio.create_subprocess_exec(sys.executable,'-B',str(script),str(self.base),str(self.root),env=env,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        try:
            async with asyncio.timeout(10):
                while not (self.root/'ready').exists():await asyncio.sleep(.02)
            child=json.loads((self.base/'child.json').read_text())
            owner.kill();await owner.wait()
            async with asyncio.timeout(8):
                while True:
                    proc=await asyncio.create_subprocess_exec('/usr/bin/systemctl','--user','is-active',child['unit'],stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                    state,_=await proc.communicate()
                    if state.strip()!=b'active':break
                    await asyncio.sleep(.05)
            self.assertFalse((self.root/'escaped').exists())
        finally:
            if owner.returncode is None:owner.kill();await owner.wait()
