import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark_report', ROOT/'tools/benchmark_report.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
PRICES = json.loads((ROOT/'evaluation/benchmark-v1/prices.json').read_text())


def request(**changes):
    return dict(thread_id='t', request_id='r', role='doer', model='gpt-6.1-sol',
                usage_kind='per_request', uncached_input_tokens=1000, cached_input_tokens=0,
                cache_write_input_tokens=0, output_tokens=100, evidence='sha256:fixture', **changes)


def trial(arm, status='COMPLETED'):
    return dict(arm=arm, task='A', replicate=1, source='frozen-source', profile='frozen-profile',
                status=status, grader_pass=status=='COMPLETED', grader_evidence='parent:fixture',
                usage_complete=True, requests=[request()], wall_seconds=10,
                evidence_kind='NATIVE_MEASUREMENT')


def data():
    return dict(schema='capri-benchmark-v1', runset='unit-fixture', arms=['baseline','managed'],
                trials=[trial('baseline'),trial('managed')])


class ReceiptMetricsTests(unittest.TestCase):
    def test_cached_input_uses_its_own_rate(self):
        r=request();r.update(uncached_input_tokens=0,cached_input_tokens=1000,output_tokens=0)
        self.assertAlmostEqual(module.token_cost(r,PRICES)[0],.0001)

    def test_cache_writes_are_not_also_charged_as_uncached(self):
        r=request();r.update(uncached_input_tokens=0,cache_write_input_tokens=1000,cache_write_ttl='30m',output_tokens=0)
        self.assertAlmostEqual(module.token_cost(r,PRICES)[0],.0025)

    def test_long_prompt_applies_request_specific_multipliers(self):
        r=request();r.update(uncached_input_tokens=272001)
        self.assertAlmostEqual(module.token_cost(r,PRICES)[0],272001*4/1e6+100*15/1e6)

    def test_cumulative_snapshots_cannot_be_summed_as_requests(self):
        d=data();d['trials'][0]['requests'][0]['usage_kind']='thread_cumulative'
        with self.assertRaises(ValueError):module.summarize(d,PRICES)

    def test_duplicate_request_identity_is_rejected(self):
        d=data();d['trials'][0]['requests']*=2
        with self.assertRaises(ValueError):module.summarize(d,PRICES)

    def test_missing_usage_produces_no_savings_claim(self):
        d=data();d['trials'][1]['usage_complete']=False
        r=module.summarize(d,PRICES)
        self.assertIsNone(r['comparisons']['managed']['token_api_cost_per_pass_savings_percent'])

    def test_aborted_cost_is_included_in_cost_per_success(self):
        d=data();d['trials'] += [dict(trial('baseline','ABORTED'),task='B'),dict(trial('managed'),task='B')]
        r=module.summarize(d,PRICES)
        self.assertAlmostEqual(r['arms']['baseline']['token_api_usd_per_pass'],.006)
        self.assertAlmostEqual(r['comparisons']['managed']['token_api_cost_per_pass_savings_percent'],50)

    def test_zero_success_does_not_divide_by_zero(self):
        d=data();d['trials'][0]['status']='ABORTED'
        r=module.summarize(d,PRICES)
        self.assertIsNone(r['arms']['baseline']['token_api_usd_per_pass'])

    def test_unrun_trials_are_preserved_and_block_comparison(self):
        d=data();d['trials']=[dict(trial(a,'NOT_RUN'),requests=[]) for a in d['arms']]
        r=module.summarize(d,PRICES)
        self.assertEqual(r['arms']['baseline']['not_run'],1)
        self.assertIsNone(r['comparisons']['managed']['token_api_cost_per_pass_savings_percent'])

    def test_mismatched_schedule_is_rejected(self):
        d=data();d['trials'][1]['task']='different'
        with self.assertRaises(ValueError):module.summarize(d,PRICES)

    def test_synthetic_tests_cannot_become_native_savings(self):
        d=data();d['trials'][1]['evidence_kind']='SYNTHETIC_TEST'
        r=module.summarize(d,PRICES)
        self.assertIsNone(r['comparisons']['managed']['token_api_cost_per_pass_savings_percent'])

    def test_exact_occupancy_and_actual_billing_stay_unknown(self):
        d=data();d['arms'].append('managed-plus');d['trials'].append(trial('managed-plus'))
        r=module.summarize(d,PRICES)
        self.assertEqual(r['exact_active_occupancy'],'UNKNOWN')
        self.assertIsNone(r['actual_billed_usd'])
        self.assertEqual(r['comparisons']['managed-plus__vs__managed']['reference_arm'],'managed')


if __name__ == '__main__':unittest.main()
