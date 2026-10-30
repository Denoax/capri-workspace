"""Real Store controls; mocks explicitly replace stopped-proof I/O, never models."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import test_controller
from loop import native_input_repair as repair
from loop import native_startup_repair as admission
from loop.util import Rejected,digest


class PreDispatchInputRepairTests(test_controller.IsolatedCase):
    def test_plain_and_redacted_lifecycle_methods_or_turn_ids_block_repair(self):
        for name in ('turn/started','turn/completed','thread/tokenUsage/updated','item/started','item/completed','model/rerouted'):
            for method in (name,dict(bytes=len(name),sha256=digest(name.encode()))):
                with self.subTest(method=method),self.assertRaises(Rejected):
                    repair.require_no_model_frames([dict(envelope=dict(method=method,turnId=None))])
        with self.assertRaises(Rejected):repair.require_no_model_frames([dict(envelope=dict(method=None,turnId='unexpected'))])
        repair.require_no_model_frames([dict(envelope=dict(method=None,turnId=None))])

    def test_new_kind_still_requires_exact_foreground_scope_in_real_store(self):
        binding=dict(kind=repair.KIND,intent_event=273,target_source='e'*64)
        plan=dict(prepared_event=None,proof=dict(kind='SYNTHETIC_NO_MODEL_PROOF'))
        with patch.object(admission,'check',return_value=plan):
            with self.assertRaises(Rejected):admission.prepare(self.store,{},binding,self.root,'old scope272')
            self.assertEqual(admission.records(self.store,binding,admission.PREPARED),[])
            result=admission.prepare(self.store,{},binding,self.root,admission.foreground_line(binding))
        self.assertEqual(result['model_dispatch'],'NOT_STARTED')
        self.assertEqual(len(admission.records(self.store,binding,admission.PREPARED)),1)
        with self.assertRaises(Rejected):admission.records(self.store,dict(binding,target_source='f'*64),admission.PREPARED)

    def test_real_new_intent_commits_before_source_effect_and_failure_is_retained(self):
        binding=dict(kind=repair.KIND,intent_event=273,target_source='e'*64,target_root=str(self.root/'target'))
        plan=dict(prepared_event=99,home=str(self.root/'fresh'),owner='new-owner')
        def stopped(*_):
            self.assertEqual(len(admission.records(self.store,binding,admission.INTENT)),1)
            self.assertFalse((self.root/'fresh').exists())
            raise RuntimeError('synthetic stop after committed intent')
        with patch.object(repair,'check',return_value=plan),patch.object(admission,'check',return_value=plan),patch.object(repair,'ancestry',return_value=(None,None,SimpleNamespace(home=self.root))),patch.object(repair,'create_source',side_effect=stopped),self.assertRaises(RuntimeError):
            repair.launch({},binding,self.root,None)
        self.assertEqual(len(admission.records(self.store,binding,admission.INTENT)),1)
        row=self.store.db.execute("SELECT data FROM events WHERE kind='NATIVE_PREMODEL_STARTUP_REPAIR_HELD'").fetchone()
        self.assertEqual(json.loads(row[0])['retry'],'FORBIDDEN')
        self.assertFalse((self.root/'fresh').exists())
