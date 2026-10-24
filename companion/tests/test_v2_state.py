import json
from pathlib import Path
import tempfile
import unittest
from capri.store import Store
from capri.profile import update,validate,load
from capri.broker import Denied

class V2StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'state'
        self.store=Store(self.path);self.store.migrate_v2();self.addCleanup(lambda:self.store.db.close())

    def test_additive_migration_preserves_history_correction_and_private_account_reference(self):
        turn=self.store.turn('account-a','user','Preferred project name is Silver')
        self.store.remember('account-a','Preferred project name is Silver',turn)
        self.store.save_draft('account-a','Unsent draft\nwith another line')
        account=Path(self.tmp.name)/'account.json';account.write_text('{"reference":"fixture-only"}')
        before=account.read_bytes()
        self.store.db.close();self.store=Store(self.path);self.store.migrate_v2()
        self.assertEqual(self.store.history('account-a')[0]['text'],'Preferred project name is Silver')
        self.assertEqual(self.store.memories('account-a')[0]['text'],'Preferred project name is Silver')
        self.assertEqual(self.store.draft('account-a'),'Unsent draft\nwith another line')
        self.assertEqual(account.read_bytes(),before)
        self.assertEqual(self.store.draft('other-account'),'')

    def test_draft_never_creates_a_turn_or_action(self):
        self.store.save_draft('account-a','/open audio-settings')
        self.assertEqual(self.store.history('account-a'),[])
        self.assertEqual(self.store.db.execute('select count(*) from actions').fetchone()[0],0)

    def test_crashed_task_is_interrupted_and_not_requeued(self):
        self.store.create_task('task','account-a','Fix fixture',{'roots':[]})
        self.store.update_task('task',status='running',thread='thread-fixture')
        self.store.db.close();self.store=Store(self.path);self.store.migrate_v2()
        row=self.store.tasks('account-a')[0]
        self.assertEqual(row['status'],'interrupted');self.assertEqual(row['thread'],'thread-fixture')

    def test_only_bounded_data_preferences_can_be_adjusted(self):
        update(self.store,{'quiet':True,'character_size':320})
        self.assertTrue(load(self.store)['quiet'])
        for value in ({'hook':'import os'},{'character_size':'https://evil.invalid'},{'sound_volume':101},{'quiet':1},{'quiet_start':'25:00'},{'roots':['/home']}):
            with self.subTest(value=value),self.assertRaises(Denied):validate(value)
        self.assertEqual(load(self.store)['character_size'],320)

    def test_invalid_cadence_does_not_replace_saved_profile(self):
        before=load(self.store)
        with self.assertRaises(Denied):update(self.store,{'min_gap_minutes':240,'max_gap_minutes':30})
        self.assertEqual(load(self.store),before)
