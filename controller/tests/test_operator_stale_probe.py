"""Real context recovery gate; deterministic transport stand-ins, zero models."""
from dataclasses import replace
from types import SimpleNamespace
import test_controller
import test_context
import test_native_operator
from loop.context import Checkpoint, ContextState, SECTIONS
from loop.util import Rejected


class StaleOperatorProbeTests(test_controller.IsolatedCase):
    def setUp(self):
        super().setUp()
        test_native_operator.operator_fixture(self)
        authority={name:{} for name in SECTIONS}
        authority.update(questions_answers={'pending':[]},inflight_uncertain=[],next_action={'human_gate':False})
        artifact=self.root/'controlled-original';artifact.write_text('preserved')
        self.checkpoint=Checkpoint(self.root/'controlled-checkpoint.json',self.root)
        self.checkpoint.save(authority,['controlled-original'])
        self.authority=authority
        self.clock=[1000]
        self.state=ContextState(self.root/'context.json',test_context.binding(),clock=lambda:self.clock[0])
        self.backend=SimpleNamespace(active=None,error=None,phase='read',thread='thread',generation=2,
            proc=SimpleNamespace(pid=900001),start_identity='controlled-process',
            workspace=self.workspace,inputs=self.workspace)
        self.adapter.slots.backends={'doer':self.backend}
        self.adapter.checkpoint=lambda *a:self.checkpoint
        self.adapter.prepare_context=lambda *a:self.state
        self.probe_holds=[]
        def probe(*a):
            self.probe_holds.append(self.state.rehydrating)
            self.state.recovery_probe(self.checkpoint,self.authority,phase='read',
                payload_bytes=20,max_tools=0,max_seconds=30)
        def reread(*a):
            self.state.rehydrating=False
            self.state.persist()
            return {'scope':'CONTROLLED_TRANSPORT_STAND_IN'}
        def compact(*a):
            # Only emulate the epoch transition here. Native compaction itself
            # remains an independently required live qualification.
            self.state.identity=replace(self.state.identity,epoch=self.state.identity.epoch+1)
            self.state.rehydrating=True
            self.state.persist()
        self.adapter.probe=probe
        self.adapter.rehydrate=reread
        self.adapter.compact=compact
        self.request={**self.binding,'thread':'thread','role_generation':2}

    def test_unknown_usage_enters_explicit_read_hold_before_probe(self):
        self.assertEqual(self.state.decision()['reason'],'UNKNOWN')
        result=self.operator.maintenance('compact-role',self.request)
        self.assertEqual(result['status'],'READ_ONLY_MAINTENANCE_COMPLETED')
        self.assertEqual(self.probe_holds,[True,True])
        self.assertFalse(self.state.rehydrating)

    def test_stale_usage_enters_explicit_read_hold_without_weakening_probe(self):
        self.state.update(test_context.usage(),self.state.identity,0,1000)
        self.clock[0]=2000
        self.assertEqual(self.state.decision()['reason'],'STALE_OR_WRONG_IDENTITY')
        result=self.operator.maintenance('compact-role',self.request)
        self.assertEqual(result['status'],'READ_ONLY_MAINTENANCE_COMPLETED')
        self.assertEqual(self.probe_holds,[True,True])

    def test_unresolved_compaction_is_not_cleared_by_stale_recovery_hold(self):
        self.state.compaction={'unresolved':'observed-lifecycle'}
        self.state.persist()
        with self.assertRaisesRegex(Rejected,'reconciled recovery hold'):
            self.operator.maintenance('compact-role',self.request)
        self.assertEqual(self.state.compaction,{'unresolved':'observed-lifecycle'})
