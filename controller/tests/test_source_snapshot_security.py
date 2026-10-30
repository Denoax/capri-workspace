"""Benign source canaries never enter an admitted role workspace."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_controller  # Existing test harness resolves the selected controller.
from loop.cli import snapshot
from loop.contract import source
from loop.util import Rejected


class SourceSnapshotSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        (self.repo/'.gitignore').write_text('auth.json\n*.sqlite3\n.env\n__pycache__/\n')
        (self.repo/'main.py').write_text('value = 1\n')
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        self.commit()
        self.policy=self.root/'policy.md';self.policy.write_text('synthetic policy')

    def commit(self):
        subprocess.run(['git','-C',str(self.repo),'-c','core.hooksPath=/dev/null','add','--all'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','core.hooksPath=/dev/null','-c','user.name=Fixture',
                        '-c','user.email=fixture@invalid','commit','-qm','synthetic tracked source'],check=True)

    def test_ignored_auth_canary_is_rejected_before_admission(self):
        (self.repo/'auth.json').write_text('{"dummy":"NOT_A_REAL_SECRET"}')
        with self.assertRaises(Rejected):source(self.repo)

    def test_ignored_private_state_canary_is_rejected_before_admission(self):
        (self.repo/'private.sqlite3').write_text('synthetic data, not a real database')
        with self.assertRaises(Rejected):source(self.repo)

    def test_rejected_private_input_is_not_copied_before_validation(self):
        (self.repo/'.env').write_text('DUMMY_ONLY=synthetic')
        with self.assertRaises(Rejected):
            snapshot(self.root/'home',self.repo,'owner',{'reference_policy':str(self.policy)})
        self.assertFalse((self.root/'home/workspace/thinker/owner').exists())

    def test_tracked_quoted_filename_and_mode_are_preserved(self):
        name=" a 'quoted' $name.py";path=self.repo/name
        path.write_text('print(1)\n');path.chmod(0o755);self.commit()
        workspace,inputs=snapshot(self.root/'home',self.repo,'owner',{'reference_policy':str(self.policy)})
        self.assertEqual((workspace/name).read_bytes(),path.read_bytes())
        self.assertEqual((workspace/name).stat().st_mode&0o777,0o755)
        saved=json.loads((inputs/'source.json').read_text())
        self.assertEqual(saved['files'],source(self.repo)['files'])

    def test_ignored_python_cache_remains_excluded_without_blocking_source(self):
        cache=self.repo/'__pycache__';cache.mkdir();(cache/'main.pyc').write_bytes(b'synthetic cache')
        admitted=source(self.repo)
        self.assertEqual(set(admitted['files']),{'.gitignore','main.py'})

    def test_assume_unchanged_does_not_hide_different_source_bytes(self):
        subprocess.run(['git','-C',str(self.repo),'update-index','--assume-unchanged','main.py'],check=True)
        (self.repo/'main.py').write_text('synthetic unexpected content\n')
        with self.assertRaises(Rejected):source(self.repo)
