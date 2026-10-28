"""Regression proof rejects test absence/setup failures rather than manufacturing PASS."""
from pathlib import Path
import tempfile
import unittest
import test_controller
from loop.collector import assess_check,check_command,unittest_evidence


class RegressionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.argv=['python3','-m','unittest','-v']
        self.spec=dict(expected_exit=0,baseline_must_fail=True)
    def run_record(self,text,exit):
        return dict(exit=exit,timeout=False,source_unchanged=True,skip_detected=False,test_run=unittest_evidence(self.argv,'',text))
    def passing(self):return self.run_record('test_behavior (fixture.C.test_behavior) ... ok\nRan 1 test in 0.001s\nOK\n',0)

    def test_archived_zero_test_exit_five_is_unverified(self):
        baseline=self.run_record('Ran 0 tests in 0.001s\nNO TESTS RAN\n',5)
        self.assertEqual(assess_check(self.spec,baseline,self.passing()),'UNVERIFIED')

    def test_behavioral_assertion_failure_matches_same_executed_control(self):
        baseline=self.run_record('test_behavior (fixture.C.test_behavior) ... FAIL\nAssertionError: required behavior\nRan 1 test in 0.001s\nFAILED (failures=1)\n',1)
        self.assertEqual(assess_check(self.spec,baseline,self.passing()),'PASS')

    def test_import_or_setup_error_is_not_a_behavioral_regression(self):
        baseline=self.run_record('test_behavior (fixture.C.test_behavior) ... ERROR\nModuleNotFoundError: missing dependency\nRan 1 test in 0.001s\nFAILED (errors=1)\n',1)
        self.assertEqual(assess_check(self.spec,baseline,self.passing()),'UNVERIFIED')

    def test_different_discovered_case_or_missing_receipt_is_unverified(self):
        baseline=self.run_record('test_different (fixture.C.test_different) ... FAIL\nAssertionError: mismatch\nRan 1 test in 0.001s\nFAILED (failures=1)\n',1)
        self.assertEqual(assess_check(self.spec,baseline,self.passing()),'UNVERIFIED')
        del baseline['test_run'];self.assertEqual(assess_check(self.spec,baseline,self.passing()),'UNVERIFIED')

    def test_unknown_test_framework_is_not_guessed_from_output(self):
        self.assertIsNone(unittest_evidence(['sh','-c','false'],'','Ran 1 test in 1s\nFAILED (failures=1)'))

    def test_actual_collector_runs_identical_assertion_on_both_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'baseline';candidate=root/'candidate';base.mkdir();candidate.mkdir()
            test='import unittest\nfrom behavior import value\nclass C(unittest.TestCase):\n def test_behavior(self):self.assertEqual(value(),2)\n'
            for path,value in [(base,1),(candidate,2)]:
                (path/'behavior.py').write_text('def value():return '+str(value)+'\n');(path/'test_behavior.py').write_text(test)
            before=check_command(base,self.argv,root/'before');after=check_command(candidate,self.argv,root/'after')
            self.assertEqual(before['test_run']['count'],1);self.assertEqual(after['test_run']['count'],1)
            self.assertEqual(assess_check(self.spec,before,after),'PASS')
