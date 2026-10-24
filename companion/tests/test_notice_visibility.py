import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from capri.initiative import Scheduler
from capri.service import Service

class NoticeVisibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_presented_notice_keeps_its_controls_during_pointer_activity_and_snooze(self):
        with tempfile.TemporaryDirectory(prefix='capri-notice-') as folder:
            root=Path(folder)
            with patch.dict(os.environ,{'XDG_RUNTIME_DIR':str(root/'runtime'),'XDG_STATE_HOME':str(root/'state'),'XDG_CONFIG_HOME':str(root/'config'),'XDG_DATA_HOME':str(root/'data'),'CAPRI_RUNTIME_NAME':'capri-test-notice'}):
                core=Service()
            try:
                core.ui=object();core.session_verified=True;core.broker.connect_ui();core.broker.set_locked(False)
                core.input_idle=True;core.desktop_dnd=False
                elapsed=[0.]
                core.scheduler=Scheduler(core.store,lambda:core.profile,lambda:1800000000+elapsed[0],lambda:100+elapsed[0],partition=lambda:core.provider.partition)
                core.scheduler.offer('selected-project','public-fixture','project-change',{'cloud':False},'public-save')
                elapsed[0]=31;candidate=core.scheduler.eligible(core.attention());self.assertIsNotNone(candidate)
                core.scheduler.present(candidate,'Public selected save','Actual fixture source')
                notice=core.snapshot()['notice'];self.assertIsNotNone(notice)
                core.input_idle=False
                self.assertEqual(core.snapshot()['notice'],notice,'Pointer activity must not remove the displayed Snooze controls')
                self.assertIsNone(core.scheduler.eligible(core.attention()))
                self.assertEqual(len(core.scheduler.state['bubbles']),1)
                core.desktop_dnd=True;self.assertIsNone(core.snapshot()['notice']);core.desktop_dnd=False
                core.scheduler.snooze(180);self.assertIsNone(core.snapshot()['notice'])
                self.assertGreater(core.scheduler.state['snooze'],core.scheduler.now()+10799)
            finally:
                core.store.db.close();os.close(core.lockfd)
