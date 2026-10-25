import os
from pathlib import Path
import subprocess
import unittest


class MotionRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(Path('/usr/lib/qt6/bin/qml').is_file(), 'Native Qt QML runner not installed')
    def test_actual_js_constraints_joint_lengths_rolls_novelty_and_interruptions(self):
        script = Path(__file__).with_name('MotionChecks.qml')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QML_XHR_ALLOW_FILE_READ='1', QT_FORCE_STDERR_LOGGING='1', QT_MESSAGE_PATTERN='%{message}', QML_DISABLE_DISK_CACHE='1')
        result = subprocess.run(['/usr/lib/qt6/bin/qml', '--apptype', 'core', '-f', str(script)], env=env, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('MOTION_PASS', output)
