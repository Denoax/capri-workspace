import tempfile
import unittest
from capri.broker import Denied
from capri.profile import load, update, validate
from capri.store import Store


class PresentationCompatibilityTests(unittest.TestCase):
    def test_new_preferences_persist_without_making_legacy_profile_unreadable(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder); store.migrate_v2()
            update(store, {'follow': False, 'ui_text_scale': 200, 'quiet': True})
            legacy = store.value('local-owner', 'profile')
            self.assertNotIn('follow', legacy)
            self.assertNotIn('ui_text_scale', legacy)
            self.assertTrue(legacy['quiet'])
            self.assertEqual(store.value('local-owner', 'presentation-profile-v3'), {'follow': False, 'ui_text_scale': 200})
            self.assertEqual(load(store)['ui_text_scale'], 200)
            self.assertFalse(load(store)['follow'])
            for changes in ({'ui_text_scale': 201}, {'ui_text_scale': True}, {'follow': 1}):
                with self.assertRaises(Denied): update(store, changes)
            self.assertEqual(load(store)['ui_text_scale'], 200)
            store.db.close()
