"""Synthetic context controls. No live model/compaction quality claim."""
from dataclasses import replace
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loop.context import Checkpoint, ContextState, Policy, SECTIONS, UsageIdentity
from loop.util import Rejected


def binding(**changes):
    value = UsageIdentity('doer', 'thread', 'turn', 'task', 1, 'gpt-6.1-sol', 2, 1,
                          'server', 'pid-start', '0.163.0', 'synthetic-schema')
    return replace(value, **changes)


def usage(footprint=20000, window=475000, cumulative=4000000, cached=19000):
    def counters(total):
        return dict(inputTokens=19000, outputTokens=1000, cachedInputTokens=cached,
                    reasoningOutputTokens=500, totalTokens=total, cacheWriteInputTokens=0)
    return dict(method='thread/tokenUsage/updated', params=dict(threadId='thread', turnId='turn',
        tokenUsage=dict(last=counters(footprint), total=counters(cumulative), modelContextWindow=window)))


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = 1000.
        self.state = ContextState(self.root/'usage.json', binding(), clock=lambda: self.now)

    def tearDown(self):
        self.temp.cleanup()

    def update(self, value=None, order=1):
        return self.state.update(value or usage(), self.state.identity, order, self.now)

    def test_latest_not_cumulative_cached_or_added_reasoning(self):
        reading = self.update()
        d = self.state.decision()
        self.assertEqual(reading['cumulative_billing']['totalTokens'], 4000000)
        self.assertEqual(reading['cached_input'], 19000)
        self.assertEqual(reading['active_occupancy'], 'UNKNOWN')
        self.assertAlmostEqual(d['pressure_estimate'], 36000/475000)
        self.assertAlmostEqual(d['native_ui_used_estimate'], 8000/463000)
        self.assertFalse(d['per_inference_ceiling'])

    def test_bad_denominator_unknown_and_stale_hold(self):
        for window in (None, 0, -1, 1050000, True):
            self.update(usage(window=window), order=self.state.order+1)
            self.assertEqual(self.state.decision()['action'], 'HOLD')
        self.update(order=self.state.order+1)
        self.now += 31
        self.assertEqual(self.state.decision()['reason'], 'STALE_OR_WRONG_IDENTITY')

    def test_wrong_identity_epoch_wire_turn_and_duplicate_order(self):
        self.update()
        for wrong in (binding(thread='other'), binding(model='gpt-6.1-sol', epoch=1), binding(role='reviewer'), binding(server='other')):
            with self.assertRaises(Rejected):
                self.state.update(usage(), wrong, 2, self.now)
        for order in (1, 0):
            with self.assertRaises(Rejected): self.update(usage(30000), order)
        with self.assertRaises(Rejected): self.update(order=2)
        wrong = usage(30000); wrong['params']['turnId'] = 'other'
        with self.assertRaises(Rejected): self.update(wrong, 2)

    def test_threshold_edges_include_pending_and_checkpoint_reserve(self):
        self.state.policy = Policy(reserve=0)
        for footprint, action in ((284999, 'ALLOW'), (285000, 'CHECKPOINT'),
                                  (356250, 'COMPACT'), (403750, 'HOLD')):
            self.update(usage(footprint), order=self.state.order+1)
            self.assertEqual(self.state.decision()['action'], action)
        self.update(usage(280000), order=self.state.order+1)
        self.assertEqual(self.state.decision(pending=4000, checkpoint_payload=1000)['action'], 'CHECKPOINT')

    def test_restart_retains_reading_and_does_not_admit_or_reprobe(self):
        self.update()
        recovered = ContextState(self.root/'usage.json', binding(), clock=lambda: self.now)
        self.assertEqual(recovered.reading['latest_request']['totalTokens'], 20000)
        self.assertEqual(recovered.decision()['reason'], 'RECOVERY_REQUIRED')
        with self.assertRaises(Rejected):
            recovered.startup_probe(phase='read', payload_bytes=1, max_tools=1, max_seconds=1, explicit=True)

    def authority(self):
        a = {key: {} for key in SECTIONS}
        a['inflight_uncertain'] = []
        a['questions_answers'] = dict(pending=[])
        a['lease_generations'] = dict(lease='writer', task_generation=1, role_generation=2)
        return a

    def checkpoint(self, authority=None):
        (self.root/'contract.json').write_text('original request and exact contract')
        c = Checkpoint(self.root/'checkpoint.json', self.root)
        c.save(authority or self.authority(), ['contract.json'])
        return c

    def test_compaction_ack_not_completion_and_decrease_after_epoch(self):
        self.update(usage(300000))
        with self.assertRaises(Rejected):
            self.state.compaction_event('thread/compact/start', 'thread', 'turn', 'c')
        self.state.compaction_event('item/started', 'thread', 'turn', 'c')
        self.assertEqual(self.state.decision()['action'], 'HOLD')
        with self.assertRaises(Rejected):
            self.state.compaction_event('item/completed', 'thread', 'turn', 'wrong')
        self.state.compaction_event('item/completed', 'thread', 'turn', 'c')
        self.assertEqual(self.state.identity.epoch, 1)
        with self.assertRaises(Rejected):
            self.state.update(usage(), binding(), 2, self.now)
        self.update(usage(10000), order=2)
        self.assertEqual(self.state.decision()['reason'], 'RECOVERY_REQUIRED')
        self.state.rehydrate(self.checkpoint(), self.authority())
        self.assertEqual(self.state.decision()['action'], 'ALLOW')

    def test_checkpoint_tamper_missing_latest_question_and_gate(self):
        c = self.checkpoint()
        self.assertTrue(c.validate(self.authority()))
        changed = self.authority(); changed['questions_answers']['pending'] = ['question']
        with self.assertRaises(Rejected): c.validate(changed)
        changed = self.authority(); changed['next_action']['human_gate'] = True
        with self.assertRaises(Rejected): c.validate(changed)
        (self.root/'contract.json').write_text('tampered')
        with self.assertRaises(Rejected): c.validate(self.authority())
        (self.root/'contract.json').unlink()
        with self.assertRaises(Rejected): c.validate(self.authority())

    def test_small_probe_is_explicit_bounded_read_only_and_one_shot(self):
        for kwargs in (dict(explicit=False), dict(phase='write'), dict(payload_bytes=2049), dict(max_tools=2), dict(max_seconds=31)):
            args = dict(phase='read', payload_bytes=10, max_tools=1, max_seconds=10, explicit=True);args.update(kwargs)
            with self.assertRaises(Rejected): self.state.startup_probe(**args)
        self.state.startup_probe(phase='read', payload_bytes=10, max_tools=1, max_seconds=10, explicit=True)
        with self.assertRaises(Rejected):
            self.state.startup_probe(phase='read', payload_bytes=10, max_tools=1, max_seconds=10, explicit=True)


if __name__ == '__main__':
    unittest.main()

class RecoveryControlTests(unittest.TestCase):
    setUp = ContextTests.setUp
    tearDown = ContextTests.tearDown
    update = ContextTests.update
    authority = ContextTests.authority
    checkpoint = ContextTests.checkpoint

    def test_recovery_probe_requires_checkpoint_readonly_and_unique_attempt(self):
        self.update()
        c = self.checkpoint()
        recovered = ContextState(self.root/'usage.json', binding(), clock=lambda: self.now)
        args = dict(phase='read', payload_bytes=100, max_tools=0, max_seconds=30)
        with self.assertRaises(Rejected): recovered.recovery_probe(c, self.authority(), **(args|{'phase':'write'}))
        recovered.recovery_probe(c, self.authority(), **args)
        self.assertEqual(recovered.decision()['reason'], 'RECOVERY_REQUIRED')
        with self.assertRaises(Rejected): recovered.recovery_probe(c, self.authority(), **args)
        restarted = ContextState(self.root/'usage.json', binding(), clock=lambda: self.now)
        with self.assertRaises(Rejected): restarted.recovery_probe(c, self.authority(), **args)

    def test_compaction_restart_keeps_epoch_and_inflight_hold(self):
        self.update()
        self.state.compaction_event('item/started', 'thread', 'turn', 'c')
        recovered = ContextState(self.root/'usage.json', binding(), clock=lambda: self.now)
        self.assertIsNotNone(recovered.compaction)
        with self.assertRaises(Rejected):
            recovered.recovery_probe(self.checkpoint(), self.authority(), phase='read', payload_bytes=100, max_tools=0, max_seconds=30)
        recovered.compaction_event('item/completed', 'thread', 'turn', 'c')
        again = ContextState(self.root/'usage.json', binding(), clock=lambda: self.now)
        self.assertEqual(again.identity.epoch, 1)
        self.assertEqual(again.decision()['reason'], 'RECOVERY_REQUIRED')

    def test_probe_transport_enforces_zero_tools_and_short_deadline(self):
        from loop.native_protocol import Lifecycle
        tick = [0]
        life = Lifecycle('thread', clock=lambda: tick[0], max_seconds=30, max_tools=0)
        life.feed(dict(method='turn/started', params=dict(threadId='thread', turn=dict(id='turn'))))
        with self.assertRaises(Rejected):
            life.feed(dict(method='item/started', params=dict(threadId='thread', turnId='turn', item=dict(id='tool',type='commandExecution'))))
        life = Lifecycle('thread', clock=lambda: tick[0], max_seconds=30, max_tools=0)
        tick[0] = 30
        with self.assertRaises(Rejected): life.budget()

    def test_explicit_compaction_requires_item_and_successful_terminal(self):
        from loop.native_protocol import CompactionLifecycle
        life = CompactionLifecycle('thread')
        def e(method, **kw): return dict(method=method, params=dict(threadId='thread', **kw))
        with self.assertRaises(Rejected): life.finish_compaction()
        life = CompactionLifecycle('thread')
        life.feed(e('turn/started', turn=dict(id='turn')))
        it = dict(id='c', type='contextCompaction')
        life.feed(e('item/started', turnId='turn', item=it))
        life.feed(e('item/completed', turnId='turn', item=it))
        life.feed(e('turn/completed', turn=dict(id='turn', status='completed')))
        self.assertEqual(life.finish_compaction(), 'turn')

    def test_research_snippets_unavailable_and_irrelevant_do_not_ground_claims(self):
        from loop.context import validate_research_claim
        c = dict(url='https://example.invalid/source', title='Synthetic source', retrieved_at='2026-10-22',
            version='synthetic-v1', section='Transport', kind='observation', claim='Synthetic claim', limitations='Synthetic fixture')
        search = dict(tool='hosted_search', status='completed')
        page = dict(tool='original_page', status='completed', url=c['url'], section=c['section'], relevant=True, evidence_hash='synthetic')
        for receipts in ([search], [search,page|{'status':'unavailable'}], [search,page|{'relevant':False}]):
            with self.assertRaises(Rejected): validate_research_claim(c, receipts)
        self.assertEqual(validate_research_claim(c,[search,page]), c)

class LineageRecoveryTests(unittest.TestCase):
    setUp = ContextTests.setUp
    tearDown = ContextTests.tearDown
    authority = ContextTests.authority
    checkpoint = ContextTests.checkpoint

    def original(self):
        a = self.authority()
        a['request_corrections'] = {'original':'preserve behavior','latest_correction':'Use inclusive boundary'}
        a['source_instructions'] = {'candidate':{'module.py':'approved'},'inputs':{'packet.json':'frozen'}}
        a['lease_generations'] = dict(task='task',task_generation=1,role_generation=2,role='doer',
            thread='old',lease='writer',server='server-old',process='process-old',phase='read')
        return a

    def test_exact_lineage_preserves_latest_correction_and_original_manifest(self):
        from loop.context import derive_checkpoint
        a = self.original(); parent = self.checkpoint(a)
        current = copy.deepcopy(a)
        current['lease_generations'].update(role_generation=3,thread='fresh',server='server-new',process='process-new')
        fields = {'role_generation','thread','server','process','phase'}
        transition = dict(kind='replacement',old={k:a['lease_generations'][k] for k in fields},new={k:current['lease_generations'][k] for k in fields})
        derived = Checkpoint(self.root/'derived.json',self.root)
        receipt = derive_checkpoint(parent,derived,current,transition)
        self.assertTrue(derived.validate(current))
        self.assertEqual(current['request_corrections']['latest_correction'],'Use inclusive boundary')
        self.assertEqual(parent.validate(a),receipt['parent_sha256'])
        with self.assertRaises(Rejected):
            derived.validate(current | {'questions_answers':{'pending':['new question']}})
        # A changed original parent breaks the derived chain.
        parent.path.write_text('{}')
        with self.assertRaises(Rejected): derived.validate(current)

    def test_lineage_cannot_authorize_source_task_generation_or_gate_drift(self):
        from loop.context import derive_checkpoint
        a = self.original(); parent = self.checkpoint(a)
        fields = {'role_generation','thread','server','process','phase'}
        for mutation in ('source','task_generation','gate','question','uncertain'):
            current = copy.deepcopy(a)
            current['lease_generations'].update(role_generation=3,thread='fresh',server='new',process='new')
            if mutation=='source':current['source_instructions']['candidate']['module.py']='wrong'
            if mutation=='task_generation':current['lease_generations']['task_generation']=2
            if mutation=='gate':current['next_action']['human_gate']=True
            if mutation=='question':current['questions_answers']['pending']=['question']
            if mutation=='uncertain':current['inflight_uncertain']=['unreconciled']
            transition = dict(kind='replacement',old={k:a['lease_generations'][k] for k in fields},new={k:current['lease_generations'][k] for k in fields})
            with self.assertRaises(Rejected):
                derive_checkpoint(parent,Checkpoint(self.root/(mutation+'.json'),self.root),current,transition)

class NamedRecoveryProfileTests(unittest.TestCase):
    def test_named_profile_preserves_denies_and_write_defaults_to_recovery(self):
        import tomllib
        from loop.settings import Settings
        settings = Settings('codex','/operator/auth','/private/state')
        config = tomllib.loads(settings.config('doer','write'))
        self.assertEqual(config['default_permissions'],'recovery')
        self.assertEqual(config['permissions']['role']['extends'],':workspace')
        self.assertEqual(config['permissions']['recovery']['extends'],':read-only')
        self.assertEqual(config['permissions']['role']['filesystem'],config['permissions']['recovery']['filesystem'])
        for path in ('/codex-home','/bridge'):
            self.assertEqual(config['permissions']['recovery']['filesystem'][path],'deny')

    def test_workspace_change_cannot_resume_old_context(self):
        from loop.native import NativeSlots
        from types import SimpleNamespace
        slots = NativeSlots.__new__(NativeSlots)
        slots.backends = {'doer':SimpleNamespace(workspace=Path('/old'))}
        with self.assertRaises(Rejected):
            slots.remount('doer',Path('/inputs'),workspace=Path('/new'))

    def test_write_profile_is_held_before_same_process_recovery(self):
        from loop.native import Backend,Binding
        b = Backend.__new__(Backend)
        b.phase='write'
        with self.assertRaises(Rejected):
            b.dispatch(Binding('doer','thread',1,'packet','source',1,'lease','write'),[{'type':'text','text':'write'}])

class NativeOwnerIntegrationTests(unittest.TestCase):
    def setUp(self):
        from loop.store import Store
        from loop.service import capability
        from loop.native import NativeAdapter
        from types import SimpleNamespace
        import threading
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Store(self.root)
        self.repo=self.root/'repo';self.repo.mkdir();(self.repo/'module.py').write_text('approved')
        self.inputs=self.root/'inputs';self.inputs.mkdir();(self.inputs/'request.txt').write_text('Synthetic exact request')
        self.token=capability(self.store,'owner',dict(repo=str(self.repo),request={'text':'Synthetic exact request'},key='owner:1'))
        self.backend=SimpleNamespace(thread='actual-native-thread',mcp=self.token,phase='read',runtime=self.root/'runtime',
            workspace=self.repo,inputs=self.inputs,generation=0,proc=SimpleNamespace(pid=12345),start_identity='start',active=None,error=None)
        self.adapter=NativeAdapter.__new__(NativeAdapter)
        self.adapter.store=self.store
        self.adapter.settings=SimpleNamespace(state_dir=str(self.root/'private'),model='gpt-6.1-sol')
        (self.root/'private'/'thinker').mkdir(parents=True)
        self.adapter.slots=SimpleNamespace(backends={'thinker':self.backend})
        self.adapter.context_states={};self.adapter.context_order={}

    def tearDown(self):
        self.store.close();self.temp.cleanup()

    def test_actual_registration_and_hold_reaches_unchanged_service_boundary(self):
        from loop.service import handle
        result=self.adapter.register_thinker('owner',self.token)
        self.assertEqual(result['thread'],'actual-native-thread')
        row=self.store.db.execute('SELECT * FROM sessions').fetchone()
        self.assertEqual(row['owner'],'owner')
        self.adapter.hold_thinker_tools()
        with self.assertRaises(Rejected):
            handle(self.store,{},dict(capability=self.token,operation='submit_task',arguments={'proposal':{}}))
        self.assertEqual(self.store.db.execute('SELECT enabled FROM capabilities').fetchone()['enabled'],0)

    def test_owner_snapshot_scope_and_correction_are_bound(self):
        self.adapter.register_thinker('owner',self.token)
        state,frozen=self.adapter.prepare_owner_context()
        self.assertEqual(state.identity.task,'owner:owner')
        self.assertEqual(frozen['scope']['request']['text'],'Synthetic exact request')
        (self.repo/'module.py').write_text('changed')
        with self.assertRaises(Rejected):self.adapter.prepare_owner_context()

    def test_wrong_native_registration_never_creates_session(self):
        with self.assertRaises(Rejected):self.adapter.register_thinker('someone-else',self.token)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)

    def test_unknown_owner_context_cannot_release_mcp(self):
        self.adapter.register_thinker('owner',self.token)
        self.adapter.hold_thinker_tools()
        with self.assertRaises(Rejected):self.adapter.release_thinker_tools()
        self.assertEqual(self.store.db.execute('SELECT enabled FROM capabilities').fetchone()[0],0)

    def test_report_rejects_unregistered_or_wrong_gate(self):
        self.adapter.thinker_owner='different-owner'
        with self.assertRaises(Rejected):self.adapter.thinker_turn('report',report_task='no-task')


    def test_new_owner_preserves_foreign_legacy_binding_and_budget_ledger(self):
        self.adapter.register_thinker('owner',self.token)
        legacy=self.root/'private'/'thinker'
        binding=b'{"owner":"previous-owner","marker":"preserve-exactly"}'
        ledger=b'{"marker":"preserved-predecessor-budget-history"}'
        (legacy/'owner-binding.json').write_bytes(binding)
        (legacy/'owner-context.json').write_bytes(ledger)
        state,frozen=self.adapter.prepare_owner_context()
        self.assertEqual(state.identity.task,'owner:owner')
        self.assertNotEqual(state.path,legacy/'owner-context.json')
        self.assertIsNone(state.reading)
        self.assertEqual((legacy/'owner-binding.json').read_bytes(),binding)
        self.assertEqual((legacy/'owner-context.json').read_bytes(),ledger)
        (self.repo/'module.py').write_text('different source')
        with self.assertRaises(Rejected):self.adapter.prepare_owner_context()

    def test_same_owner_reuses_legacy_budget_history_without_freshness_reset(self):
        self.adapter.register_thinker('owner',self.token)
        state,frozen=self.adapter.prepare_owner_context()
        state.probe_used=True
        state.persist()
        legacy=self.root/'private'/'thinker'
        (legacy/'owner-binding.json').write_text(json.dumps(frozen,sort_keys=True))
        (legacy/'owner-context.json').write_bytes(state.path.read_bytes())
        preserved=(legacy/'owner-context.json').read_bytes()
        self.adapter.context_states={}
        restored,_=self.adapter.prepare_owner_context()
        self.assertEqual(restored.path,legacy/'owner-context.json')
        self.assertTrue(restored.probe_used)
        self.assertTrue(restored.rehydrating)
        self.assertTrue(restored.restart)
        self.assertEqual((legacy/'owner-context.json').read_bytes(),preserved)

    def test_unknown_legacy_ownership_keeps_new_owner_held(self):
        self.adapter.register_thinker('owner',self.token)
        legacy=self.root/'private'/'thinker'/'owner-binding.json'
        legacy.write_text('{"unattributed":"do not discard"}')
        preserved=legacy.read_bytes()
        with self.assertRaises(Rejected):self.adapter.prepare_owner_context()
        self.assertEqual(legacy.read_bytes(),preserved)

    def owner_ready(self,footprint=285000):
        from dataclasses import replace
        import time
        from unittest.mock import Mock
        for name in ('REFERENCE_LED_DESIGN.md','preserved-requirements.json','successor-request.json'):
            (self.inputs/name).write_text('{}')
        self.adapter.register_thinker('owner',self.token)
        self.adapter.planned_compactions=set();self.adapter.operation_deadline=time.monotonic()+240;self.adapter.operation_tools=6
        self.adapter.slots.save=lambda:None
        state,_=self.adapter.prepare_owner_context();state.clock=lambda:1000
        state.identity=replace(state.identity,turn='turn');reading=usage(footprint);reading['params']['threadId']=self.backend.thread;state.update(reading,state.identity,1,1000)
        return state

    def test_owner_soft_threshold_saves_once_and_preserves_scope_budget(self):
        state=self.owner_ready();deadline=self.adapter.operation_deadline
        self.assertEqual(self.adapter.owner_idle_maintenance([])['action'],'CHECKPOINT')
        saved=state.soft_checkpoint.copy();self.assertTrue(self.adapter.owner_soft_allows(state.decision()))
        self.adapter.owner_idle_maintenance([]);self.assertEqual(saved,state.soft_checkpoint)
        self.assertEqual(deadline,self.adapter.operation_deadline);self.assertEqual(self.adapter.operation_tools,6)

    def test_owner_compaction_withholds_tools_and_rereads_originals(self):
        from unittest.mock import Mock
        state=self.owner_ready(350000);calls=[];deadline=self.adapter.operation_deadline
        def compact(**kwargs):
            self.assertEqual(self.store.db.execute('SELECT enabled FROM capabilities').fetchone()[0],0)
            self.assertLessEqual(kwargs['max_seconds'],60);state.restart=state.rehydrating=True
        self.backend.compact=Mock(side_effect=compact)
        def dispatch(payload,**kwargs):
            calls.append(kwargs)
            if kwargs.get('probe'):
                reading=usage(10000);reading['params']['threadId']=self.backend.thread;state.update(reading,state.identity,2,1000)
        self.adapter.owner_dispatch=dispatch
        self.assertEqual(self.adapter.owner_idle_maintenance([])['action'],'ALLOW')
        self.assertEqual(len(calls),2);self.assertEqual(len(calls[1]['recovery_originals']),3)
        self.assertFalse(state.rehydrating);self.assertEqual(deadline,self.adapter.operation_deadline);self.assertEqual(self.adapter.operation_tools,6)
        self.assertEqual(self.store.db.execute('SELECT enabled FROM capabilities').fetchone()[0],1)

    def test_owner_compaction_timeout_stays_held_and_cannot_repeat(self):
        from unittest.mock import Mock
        self.owner_ready(350000);self.backend.compact=Mock(side_effect=Rejected('SYNTHETIC uncertain timeout'))
        with self.assertRaises(Rejected):self.adapter.owner_idle_maintenance([])
        with self.assertRaises(Rejected):self.adapter.owner_idle_maintenance([])
        self.backend.compact.assert_called_once()
        self.assertEqual(self.store.db.execute('SELECT enabled FROM capabilities').fetchone()[0],0)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM events WHERE kind='NATIVE_OWNER_COMPACTION_UNCERTAIN'").fetchone()[0],1)

    def test_owner_cached_context_rejects_process_identity_drift(self):
        self.owner_ready();self.backend.start_identity='reused-pid'
        with self.assertRaises(Rejected):self.adapter.prepare_owner_context()

    def test_fresh_thread_fence_preserves_counters_probes_and_uncertain_original(self):
        from loop.context import ContextState
        state=self.owner_ready();state.compaction={'thread':self.backend.thread,'item':'synthetic-pending'};state.probe_used=True;state.recovery_probes=['preserved-probe'];state.persist()
        old=state.path.read_bytes();new_identity=replace(state.identity,thread='fresh-thread',role_generation=state.identity.role_generation+1)
        fresh=ContextState(state.path,new_identity,clock=lambda:1000)
        fresh.fence_prior_compaction(dict(kind='DEAD_READ_ONLY_COMPACTION_FENCE',old_thread=self.backend.thread,new_thread='fresh-thread',receipt='synthetic-sealed-proof'))
        self.assertEqual(fresh.order,state.order);self.assertEqual(fresh.seen,state.seen);self.assertTrue(fresh.probe_used);self.assertEqual(fresh.recovery_probes,['preserved-probe'])
        self.assertIsNone(fresh.compaction);self.assertTrue(fresh.restart);self.assertTrue(fresh.rehydrating)
        self.assertEqual(fresh.reconciliations[-1]['prior_compaction']['item'],'synthetic-pending')
        self.assertNotEqual(old,fresh.path.read_bytes())

class NativeStageWiringTests(unittest.TestCase):
    def test_read_grader_requires_actual_paired_command_content_not_echo(self):
        from loop.native import grade_original_reads,original_read_command
        from loop.util import digest
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);contents='Original correction: inclusive boundary'
            originals={'/inputs/packet.json':digest(contents.encode())}
            command=original_read_command(originals)
            item=dict(id='read',type='commandExecution',command=command,exitCode=0,
                aggregatedOutput=json.dumps({'files':{'/inputs/packet.json':{'sha256':originals['/inputs/packet.json'],'content':contents}}}))
            def write(rows):
                (root/'events.jsonl').write_text('\n'.join(json.dumps({'message':dict(method=method,params=dict(threadId='t',turnId='u',item=it))}) for method,it in rows))
            write([('item/completed',item)])
            self.assertFalse(grade_original_reads(root,originals))
            write([('item/started',item),('item/completed',item)])
            self.assertTrue(grade_original_reads(root,originals))
            forged=dict(item,command='echo '+item['aggregatedOutput'])
            write([('item/started',forged),('item/completed',forged)])
            self.assertFalse(grade_original_reads(root,originals))
            modified=dict(item,aggregatedOutput=json.dumps({'files':{'/inputs/packet.json':{'sha256':originals['/inputs/packet.json'],'content':'changed'}}}))
            write([('item/started',item),('item/completed',modified)])
            self.assertFalse(grade_original_reads(root,originals))

    def test_all_roles_restore_from_same_frozen_snapshot(self):
        from loop.native import NativeSlots
        from loop.settings import ROLES
        slots=NativeSlots.__new__(NativeSlots);slots.backends={}
        calls=[]
        def restore(role,workspace,inputs,controller,**kw):
            calls.append((role,kw['frozen_registry']))
            slots.backends[role]='restored'
        slots.restore_saved_role=restore;slots.save=lambda:dict(slots.backends)
        raw=json.dumps({role:{'thread':role} for role in ROLES}).encode()
        result=slots.restore_all(raw,{role:dict(workspace='/source',inputs='/inputs') for role in ROLES},'/controller')
        self.assertEqual(set(result),set(ROLES))
        self.assertEqual([v for _,v in calls],[raw,raw,raw])
        with self.assertRaises(Rejected):slots.restore_all(raw,{},'/controller')

    def test_stage_instruction_drift_stops_before_backend_work(self):
        from loop.native import NativeAdapter
        from loop.util import identity
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);packet={'instructions':[{'sha256':'approved'}]}
            (root/'packet.json').write_text(json.dumps(packet));(root/'instruction-0.md').write_text('modified')
            t=dict(owner='owner',packet=packet,content_hash=identity(packet))
            adapter=NativeAdapter.__new__(NativeAdapter)
            adapter.store=SimpleNamespace(task=lambda _:t,require_current=lambda _:None)
            adapter.engine=SimpleNamespace(verify_inputs=lambda _:None)
            with self.assertRaises(Rejected):adapter.prepare_stage('task','preflight',root,root)

class ObservedNativeWrapperTests(unittest.TestCase):
    def test_observed_shell_wrapper_is_exact_and_output_must_be_complete(self):
        import shlex
        from loop.native import grade_original_reads,original_read_command
        from loop.util import digest
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);content='Synthetic original correction'
            originals={'/inputs/packet.json':digest(content.encode())}
            canonical=original_read_command(originals)
            wrapped=shlex.join(['/usr/bin/bash','-c',canonical])
            output=json.dumps({'files':{'/inputs/packet.json':{'sha256':originals['/inputs/packet.json'],'content':content}}})
            def grade(command=wrapped,stdout=output,turn='turn'):
                items=[]
                for method,tid in [('item/started','turn'),('item/completed',turn)]:
                    items.append({'message':{'method':method,'params':{'threadId':'thread','turnId':tid,'item':dict(id='read',type='commandExecution',command=command,exitCode=0,aggregatedOutput=stdout)}}})
                (root/'events.jsonl').write_text('\n'.join(json.dumps(v) for v in items))
                return grade_original_reads(root,originals)
            self.assertTrue(grade())
            for wrong in (wrapped+' extra',shlex.join(['/bin/bash','-c',canonical]),
                          shlex.join(['/usr/bin/bash','-lc',canonical]),
                          shlex.join(['/usr/bin/bash','-c',canonical+'; echo fake']),
                          shlex.join(['/usr/bin/bash','-c','echo '+shlex.quote(output)])):
                self.assertFalse(grade(command=wrong),wrong)
            self.assertFalse(grade(stdout=output[:-5]))
            self.assertFalse(grade(turn='wrong-turn'))


class OwnedTerminalReconnectTests(unittest.TestCase):
    def setUp(self):
        from loop.native import NativeTerminals
        from loop.settings import Settings,ROLES
        from types import SimpleNamespace
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.calls=[];self.rows={};self.panes={}
        self.records={'_server':dict(pid=100,process_identity='100')}
        for i,role in enumerate(ROLES):
            self.rows[role]=dict(thread=role,generation=0,empty=False,endpoint='unix:///private/'+role+'.sock')
            self.records[role]=dict(pane='%'+str(i),pid=200+i,process_identity=str(200+i),thread=role,generation=0)
            self.panes[role]=['%'+str(i),200+i,'0']
        (self.root/'terminal-registry.json').write_text(json.dumps(self.records))
        slots=SimpleNamespace(root=self.root,settings=Settings(sys.executable,'/operator/auth',str(self.root)))
        def runner(argv,**kwargs):
            self.calls.append(argv)
            output=''
            if 'list-panes' in argv:
                output='\n'.join(r+'\t'+'\t'.join(map(str,self.panes[r])) for r in ROLES)
            elif 'respawn-pane' in argv:
                target=argv[argv.index('-t')+1]
                for role,row in self.panes.items():
                    if row[0]==target:row[1]=777
            elif 'display-message' in argv:output='777\n'
            return SimpleNamespace(returncode=0,stdout=output,stderr='')
        self.terminals=NativeTerminals(slots,runner=runner)

    def tearDown(self):self.temp.cleanup()

    def test_changed_mapping_reconnects_only_owned_role_before_return(self):
        from unittest.mock import patch
        self.rows['doer'].update(thread='fresh-doer',generation=1)
        with patch('loop.native.process_identity',side_effect=lambda pid:str(pid)):
            self.terminals.sync(self.rows)
        calls=[a for a in self.calls if 'respawn-pane' in a]
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][calls[0].index('-t')+1],self.records['doer']['pane'])
        self.assertIn('-S',calls[0]);self.assertIn(str(self.root/'ui.sock'),calls[0])
        self.assertEqual(self.terminals.records['doer']['thread'],'fresh-doer')
        self.assertEqual(self.terminals.records['doer']['pid'],777)
        self.assertIn('gpt-6.1-sol',(self.root/'frontends/doer/config.toml').read_text())

    def test_unknown_pane_refuses_every_respawn(self):
        from unittest.mock import patch
        self.rows['doer'].update(thread='fresh',generation=1)
        self.panes['reviewer'][0]='%999'
        with patch('loop.native.process_identity',side_effect=lambda pid:str(pid)):
            with self.assertRaises(Rejected):self.terminals.sync(self.rows)
        self.assertFalse(any('respawn-pane' in a for a in self.calls))

    def test_reused_server_pid_refuses_pane_signaling(self):
        from unittest.mock import patch
        with patch('loop.native.process_identity',return_value='reused'):
            with self.assertRaises(Rejected):self.terminals.sync(self.rows)
        self.assertFalse(any('respawn-pane' in a for a in self.calls))
