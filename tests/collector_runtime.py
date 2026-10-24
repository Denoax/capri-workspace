"""Repeat runtime cases inside the collector without attempting nested sandboxes.

Every case runs first in the required full host suite. The four named integration
cases test the collector launcher itself and belong outside its no-capabilities
child profile. No unittest skip or weaker child profile is used.
"""
from pathlib import Path
import unittest

HOST_ONLY = frozenset({
    'test_collector_regression.RegressionEvidenceTests.test_actual_collector_runs_identical_assertion_on_both_sources',
    'test_controller.LiveLocalRunnerTests.test_timeout_terminates_the_private_process_tree_F05_F11_F27',
    'test_controller.LiveLocalRunnerTests.test_trusted_runner_has_no_network_or_host_source_F28',
    'test_portability.NamespacePrerequisiteTests.test_required_collector_namespaces',
})


def flatten(suite):
    for case in suite:
        if isinstance(case, unittest.TestSuite):yield from flatten(case)
        else:yield case


def load_tests(loader, tests, pattern):
    root = Path(__file__).resolve().parents[1]
    cases = list(flatten(loader.discover(str(root/'controller/tests'))))
    ids = [case.id() for case in cases]
    if len(ids) < 343 or len(ids) != len(set(ids)) or not HOST_ONLY.issubset(ids):
        raise ValueError('Runtime discovery changed; review the explicit host/collector coverage mapping')
    selected = [case for case in cases if case.id() not in HOST_ONLY]
    if len(selected) != len(cases)-len(HOST_ONLY):
        raise ValueError('Collector suite lost an unclassified runtime case')
    return unittest.TestSuite(selected)
