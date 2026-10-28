"""Policy/status behavior on disposable ledgers; no model or runtime initialization."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from test_context import binding,usage
from loop.context import ContextState,Policy,persisted_status
from loop.native_status import native_status
from loop.settings import Settings
from loop.util import Rejected,digest


class PolicyProductTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_context_policy_validated_and_window_cannot_be_overridden(self):
        s=Settings('codex','/not-read',str(self.root),context_policy=dict(checkpoint=.5,compact=.7,hold=.9,reserve=8000,max_age=15))
        self.assertEqual(s.policy().reserve,8000);self.assertEqual(s.policy().expected_window,475000)
        with self.assertRaises(TypeError):s.context_policy['reserve']=0
        for policy in [dict(expected_window=1000000),dict(checkpoint=True),dict(compact=.4),dict(max_age=False),dict(reserve=-1)]:
            with self.subTest(policy=policy),self.assertRaises(Rejected):Settings('codex','/not-read',str(self.root),context_policy=policy)

    def test_persisted_policy_change_is_not_a_budget_reset(self):
        p=self.root/'ledger.json';state=ContextState(p,binding(),Policy(reserve=8000));state.persist();before=p.read_bytes()
        with self.assertRaises(Rejected):ContextState(p,binding(),Policy(reserve=16000))
        self.assertEqual(p.read_bytes(),before)

    def test_persisted_task_revision_profile_cannot_be_relabelled(self):
        p=self.root/'ledger.json';ContextState(p,binding()).persist()
        for changed in [binding(task='new'),binding(revision=2),binding(producer='other'),binding(schema='unqualified')]:
            with self.subTest(identity=changed),self.assertRaises(Rejected):ContextState(p,changed)

    def test_read_only_status_retains_raw_cache_and_old_timestamp(self):
        p=self.root/'ledger.json';state=ContextState(p,binding(),clock=lambda:1000);state.update(usage(),state.identity,1,1000);before=p.read_bytes()
        result=persisted_status(p,clock=lambda:1031)
        self.assertEqual(result['observed_at'],1000);self.assertEqual(result['freshness_seconds'],31)
        self.assertEqual(result['action']['reason'],'STALE_OR_WRONG_IDENTITY')
        self.assertEqual(result['cumulative_billing']['totalTokens'],4000000);self.assertEqual(result['cached_input'],19000)
        self.assertEqual(result['exact_active_occupancy'],'UNKNOWN');self.assertEqual(result['native_ui_baseline'],12000)
        self.assertEqual(p.read_bytes(),before)

    def test_missing_runtime_status_does_not_create_it(self):
        missing=self.root/'missing';s=Settings('codex','/not-read',str(missing));result=native_status(missing,s)
        self.assertEqual(result['status'],'UNINITIALIZED');self.assertFalse(missing.exists())
