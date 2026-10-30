"""Real stopped Store/checkpoint checks; synthetic process identities, zero models."""
import unittest
import test_native_resume
from loop.util import Rejected


class RecoveredRuntimeResumeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_native_resume.RuntimeResumeTests('test_checkpoint_stops_existing_supervisor_and_check_is_read_only')
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown();self.fixture.doCleanups()

    def test_explicit_completed_replacement_allows_restart_without_erasing_history(self):
        f=self.fixture;f.journal.append('MAINTENANCE_UNCERTAIN',dict(key='observed-hold',role='doer'))
        f.journal.append('MAINTENANCE_FENCED',dict(key='observed-hold'))
        f.journal.append('MAINTENANCE_RECOVERED',dict(prior_key='observed-hold',replacement=dict(status='READ_ONLY_MAINTENANCE_COMPLETED',source_unchanged=True)))
        before=f.journal.records();f.check();self.assertEqual(before,f.journal.records())
        self.assertTrue(any(r['milestone']=='MAINTENANCE_UNCERTAIN' for r in f.journal.records()))

    def test_fence_or_unrelated_recovery_does_not_release_uncertainty(self):
        f=self.fixture;f.journal.append('MAINTENANCE_UNCERTAIN',dict(key='held',role='doer'));f.journal.append('MAINTENANCE_FENCED',dict(key='held'))
        with self.assertRaises(Rejected):f.check()
        f.journal.append('MAINTENANCE_RECOVERED',dict(prior_key='unrelated'))
        with self.assertRaises(Rejected):f.check()

    def test_one_resolved_hold_never_clears_another_or_legacy_uncertainty(self):
        f=self.fixture;f.journal.append('MAINTENANCE_UNCERTAIN',dict(key='first',role='doer'));f.journal.append('MAINTENANCE_RECOVERED',dict(prior_key='first'))
        f.journal.append('MAINTENANCE_UNCERTAIN',dict(key='second',role='doer'))
        with self.assertRaises(Rejected):f.check()
        f.journal.append('MAINTENANCE_RECOVERED',dict(prior_key='second'));f.journal.append('MAINTENANCE_UNCERTAIN',dict(error='legacy without identity'))
        with self.assertRaises(Rejected):f.check()
