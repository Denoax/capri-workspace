import os
from pathlib import Path
import subprocess
import unittest


class NativeLayoutTests(unittest.TestCase):
    @unittest.skipUnless(Path('/usr/lib/qt6/bin/qml').is_file(), 'Native Qt QML runner not installed')
    def test_activity_without_request_and_real_scope_layout_remain_responsive(self):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_FORCE_STDERR_LOGGING='1', QT_MESSAGE_PATTERN='%{message}', QML_DISABLE_DISK_CACHE='1')
        result = subprocess.run(['/usr/lib/qt6/bin/qml', '--apptype', 'gui', '-f', str(Path(__file__).with_name('PresentationChecks.qml'))], env=env, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PRESENTATION_PASS', result.stdout + result.stderr)
