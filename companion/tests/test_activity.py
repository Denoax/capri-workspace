import tempfile
import unittest
from capri.store import Store


class ActivityProjectionTests(unittest.TestCase):
    def test_projection_is_partition_bound_read_only_and_explicit_about_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder); store.migrate_v2()
            store.create_task('a', 'account-a', 'Public task A', {})
            store.create_task('b', 'account-b', 'Private task B', {})
            store.task_event('a', 'action-start', 'x' * 9000)
            store.task_event('b', 'action-result', 'other account')
            before = store.db.total_changes
            result = store.task_activity('account-a')
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['task'], 'a')
            self.assertTrue(result[0]['truncated'])
            self.assertEqual(len(result[0]['detail']), 8000)
            self.assertNotIn('other account', str(result))
            self.assertEqual(store.task_activity('missing'), [])
            with self.assertRaises(ValueError): store.task_activity('a', 0)
            store.db.close()
