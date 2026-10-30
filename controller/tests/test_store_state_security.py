"""Store rejects unsafe disposable state paths before SQLite opens them."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

import test_controller  # Existing test harness resolves the selected controller.
from loop.store import Store
from loop.util import Rejected


class StoreStateSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)/'home';self.home.mkdir()

    def test_existing_permissive_state_directory_is_rejected_without_creating_database(self):
        state=self.home/'state';state.mkdir(mode=0o755);state.chmod(0o755)
        with self.assertRaises(Rejected):
            store=Store(self.home);store.close()
        self.assertFalse((state/'workflow.sqlite3').exists())

    def test_symlinked_state_directory_is_rejected_without_redirecting_writes(self):
        target=Path(self.temp.name)/'other';target.mkdir(mode=0o700)
        (self.home/'state').symlink_to(target,target_is_directory=True)
        with self.assertRaises(Rejected):
            store=Store(self.home);store.close()
        self.assertFalse((target/'workflow.sqlite3').exists())

    def test_symlinked_database_is_rejected_before_sqlite_mutates_target(self):
        state=self.home/'state';state.mkdir(mode=0o700)
        target=Path(self.temp.name)/'other.sqlite3';sqlite3.connect(target).close()
        before=target.read_bytes();(state/'workflow.sqlite3').symlink_to(target)
        with self.assertRaises(Rejected):
            store=Store(self.home);store.close()
        self.assertEqual(before,target.read_bytes())

    def test_new_private_state_and_database_remain_usable(self):
        store=Store(self.home)
        try:
            self.assertEqual((self.home/'state').stat().st_mode&0o777,0o700)
            self.assertEqual((self.home/'state/workflow.sqlite3').stat().st_mode&0o777,0o600)
            store.event(None,'SYNTHETIC_CONTROL',{'no_private_data':True})
        finally:store.close()
        store=Store(self.home)
        try:self.assertEqual(store.db.execute("SELECT count(*) FROM events WHERE kind='SYNTHETIC_CONTROL'").fetchone()[0],1)
        finally:store.close()
