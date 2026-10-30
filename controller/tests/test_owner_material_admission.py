"""Real Store mutation controls with an explicit synthetic proof boundary."""
import json
from pathlib import Path
from unittest.mock import patch

import test_controller
from loop import native_owner_material as material
from loop.native_startup_repair import records
from loop.util import Rejected


class OwnerMaterialAdmissionTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp()
        self.binding=dict(intent_event=271,target_source='a'*64,target_root=str(self.root/'target'))
        self.plan=dict(prepared_event=None,proof={'kind':'SYNTHETIC_PROOF'},home=str(self.root/'new-home'))

    def test_wrong_scope_writes_nothing_and_exact_scope_commits_without_dispatch(self):
        before=self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        with patch.object(material,'check',return_value=self.plan):
            with self.assertRaises(Rejected):material.prepare(self.store,{},self.binding,self.root,'old scope270')
            self.assertEqual(before,self.store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])
            result=material.prepare(self.store,{},self.binding,self.root,material.foreground_line(self.binding))
        self.assertEqual(result['model_dispatch'],'NOT_STARTED')
        rows=records(self.store,self.binding,material.PREPARED);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['new_dispatch'],'NOT_AUTHORIZED');self.assertFalse((self.root/'new-home').exists())
        with self.assertRaises(Rejected):records(self.store,{**self.binding,'target_source':'b'*64},material.PREPARED)

    def test_precommit_crash_rolls_back_scope_event(self):
        original=self.store.event
        def crash(*a,**kw):original(*a,**kw);raise RuntimeError('synthetic precommit')
        with patch.object(material,'check',return_value=self.plan),patch.object(self.store,'event',side_effect=crash),self.assertRaises(RuntimeError):
            material.prepare(self.store,{},self.binding,self.root,material.foreground_line(self.binding))
        self.assertEqual(records(self.store,self.binding,material.PREPARED),[])

    def test_real_intent_precedes_source_creation_and_failed_effect_is_retained(self):
        plan={**self.plan,'prepared_event':123}
        def before_source(*_):
            rows=records(self.store,self.binding,material.INTENT)
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['replay'],'FORBIDDEN')
            raise RuntimeError('synthetic stop before source creation')
        with patch.object(material,'check',return_value=plan),patch.object(material,'create_source',side_effect=before_source),self.assertRaises(RuntimeError):
            material.launch(dict(home=str(self.root)),self.binding,self.root,None)
        self.assertEqual(len(records(self.store,self.binding,material.INTENT)),1)
        held=self.store.db.execute("SELECT data FROM events WHERE kind='NATIVE_OWNER_MATERIAL_HELD'").fetchone()
        self.assertEqual(json.loads(held[0])['retry'],'FORBIDDEN');self.assertFalse((self.root/'new-home').exists())
