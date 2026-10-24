import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from capri.projects import Projects
from capri.store import Store

class ProjectObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_switch_revokes_old_watches_and_never_rebinds_their_events(self):
        with tempfile.TemporaryDirectory(prefix='capri-project-source-') as folder:
            root=Path(folder);project=root/'project';project.mkdir();store=Store(root/'state');store.migrate_v2()
            account=['a'];events=[];watch=Projects(store,lambda *args:events.append(args),lambda:account[0])
            try:
                watch.choose(str(project),True);watch.start()
                self.assertEqual(len(watch.active_sources()),1)
                (project/'public-fixture.txt').write_text('PUBLIC SOURCE FIXTURE')
                async with asyncio.timeout(2):
                    while not events:await asyncio.sleep(.01)
                self.assertNotIn('public-fixture.txt',str(events));self.assertNotIn('PUBLIC SOURCE FIXTURE',str(events))
                events.clear();account[0]='b'
                self.assertEqual(watch.active_sources(),[])
                (project/'another-public-fixture.txt').write_text('NO CROSS-ACCOUNT EVENT')
                await asyncio.sleep(.02);self.assertEqual(events,[])
                watch.start();self.assertIsNone(watch.fd)
            finally:watch.stop();store.db.close()
