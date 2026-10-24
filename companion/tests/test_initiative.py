from pathlib import Path
import tempfile
import unittest
from capri.initiative import Scheduler
from capri.profile import DEFAULTS
from capri.store import Store

class InitiativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='capri-initiative-');self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name));self.store.migrate_v2();self.addCleanup(self.store.db.close)
        self.wall=1800000000.;self.mono=100.;self.profile=dict(DEFAULTS)
        self.scheduler=self.new()
        self.attention={'unlocked':True,'input_idle':True,'desktop_dnd':False,'fullscreen':False,'busy':False,'hidden':False}
    def new(self):return Scheduler(self.store,lambda:self.profile,lambda:self.wall,lambda:self.mono)
    def advance(self,seconds):self.wall+=seconds;self.mono+=seconds
    def offer(self,topic='build',id='fixture-1'):
        return self.scheduler.offer('selected-project',topic,'project-change',{'project':'/tmp/fixture','cloud':False},id)
    def test_no_useful_event_and_random_timer_cannot_spend_or_fabricate_activity(self):
        self.advance(10000);self.assertIsNone(self.scheduler.eligible(self.attention))
        self.assertEqual(self.scheduler.state['models'],[]);self.assertEqual(self.scheduler.state['bubbles'],[])
    def test_storm_dedup_debounce_and_restart_preserve_hourly_limits(self):
        for _ in range(100):self.offer()
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM observations').fetchone()[0],1)
        self.assertIsNone(self.scheduler.eligible(self.attention));self.advance(31)
        candidate=self.scheduler.eligible(self.attention);self.assertIsNotNone(candidate)
        self.scheduler.present(candidate,'Real fixture save','Selected test root');self.scheduler.dismiss()
        self.offer('other','fixture-2');self.advance(31)
        self.scheduler.present(self.scheduler.eligible(self.attention),'Second real event','Fixture source');self.scheduler.dismiss()
        self.scheduler=self.new();self.offer('third','fixture-3');self.advance(31)
        self.assertIsNone(self.scheduler.eligible(self.attention))
        self.assertEqual(len(self.scheduler.state['bubbles']),2)
    def test_dnd_fullscreen_typing_and_missing_dnd_signal_suppress_without_model_calls(self):
        self.offer();self.advance(31)
        for changes in ({'desktop_dnd':True},{'desktop_dnd':None},{'fullscreen':True},{'input_idle':False},{'unlocked':False},{'busy':True},{'hidden':True}):
            with self.subTest(changes=changes):self.assertIsNone(self.scheduler.eligible({**self.attention,**changes}))
        self.assertIsNotNone(self.scheduler.eligible(self.attention));self.assertEqual(self.scheduler.state['models'],[])
    def test_dismiss_snooze_and_model_budget_survive_restart(self):
        self.offer();self.advance(31);self.scheduler.present(self.scheduler.eligible(self.attention),'Fixture','Fixture');self.scheduler.dismiss()
        self.offer(id='new-same-topic');self.advance(31);self.assertIsNone(self.scheduler.eligible(self.attention))
        self.scheduler.snooze(180);self.scheduler=self.new();self.offer('other','other');self.advance(31)
        self.assertIsNone(self.scheduler.eligible(self.attention))
        for _ in range(8):self.assertTrue(self.scheduler.reserve_model())
        self.scheduler=self.new();self.assertFalse(self.scheduler.reserve_model())
    def test_clock_jumps_cannot_reset_limits_or_revive_old_events(self):
        self.offer();self.advance(31);self.scheduler.present(self.scheduler.eligible(self.attention),'Fixture','Fixture');self.scheduler.dismiss()
        self.wall+=86400*100;self.scheduler=self.new();self.assertEqual(len(self.scheduler.state['bubbles']),1)
        self.wall-=86400*200;self.scheduler=self.new();self.assertEqual(len(self.scheduler.state['bubbles']),1)
        self.assertIsNone(self.scheduler.eligible(self.attention))
    def test_quiet_hours_use_explicit_civil_timezone_without_changing_budgets(self):
        self.profile.update(quiet_start='00:00',quiet_end='23:59',timezone='America/Edmonton')
        self.offer();self.advance(31);self.assertTrue(self.scheduler.quiet_hours());self.assertIsNone(self.scheduler.eligible(self.attention))
