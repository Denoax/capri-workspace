import os
from pathlib import Path
import subprocess
import unittest

@unittest.skipUnless(os.environ.get('CAPRI_HOST_INTEGRATION')=='1','Native D-Bus fixture requires explicit host run')
class PortalHandoffTests(unittest.TestCase):
    def helper(self):
        return Path(os.environ.get('CAPRI_TEST_PORTAL_HELPER',str(Path(__file__).parent.parent/'capri/portal_open.py')))
    def test_portal_rejection_is_not_reported_as_browser_success(self):
        fixture=Path(__file__).with_name('portal_fixture.py')
        result=subprocess.run(['/usr/bin/dbus-run-session','--','/usr/bin/python3',str(fixture),str(self.helper())],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(result.stdout.strip(),'2')
    def test_browser_helper_denies_non_authorization_destinations(self):
        result=subprocess.run(['/usr/bin/python3',str(self.helper())],input='https://evil.invalid/collect',capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,2)
