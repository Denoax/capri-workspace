"""Execute the actual QML position owner and JS contract without a compositor."""
import os
from pathlib import Path
import subprocess
import unittest


class PositionRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(Path('/usr/lib/qt6/bin/qml').is_file(), 'Native Qt QML runner not installed')
    def test_absolute_anchor_capture_epochs_bounds_and_one_shot_cancellation(self):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_FORCE_STDERR_LOGGING='1',
                   QT_MESSAGE_PATTERN='%{message}', QML_DISABLE_DISK_CACHE='1')
        result = subprocess.run(['/usr/lib/qt6/bin/qml', '--apptype', 'core', '-f',
                                 str(Path(__file__).with_name('PositionChecks.qml'))],
                                env=env, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('POSITION_PASS', result.stdout + result.stderr)
