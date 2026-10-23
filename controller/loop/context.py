"""Version-bound context telemetry and conservative recovery policy.

Last-request footprint is NOT exact active occupancy. Estimates cannot enforce
an absolute ceiling on internal model/tool inferences between notifications.
"""
from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import threading
import time
from .util import Rejected, atomic, digest, identity, safe_path


@dataclass(frozen=True)
class UsageIdentity:
    role: str
    thread: str
    turn: str
    task: str
    revision: int
    model: str
    role_generation: int
    task_generation: int
    server: str
    process: str
    producer: str
    schema: str
    epoch: int = 0

    def __post_init__(self):
        if self.model != 'gpt-6.1-sol' or any(not isinstance(v, str) or not v for v in
            (self.role, self.thread, self.turn, self.task, self.model, self.server, self.process, self.producer, self.schema)):
            raise Rejected('Incomplete usage provenance or unsupported model')
        if any(type(v) is not int or v < 0 for v in
               (self.revision, self.role_generation, self.task_generation, self.epoch)):
            raise Rejected('Invalid usage generation/revision/epoch')


@dataclass(frozen=True)
class Policy:
    checkpoint: float = .60
    compact: float = .75
    hold: float = .85
    reserve: int = 16000
    max_age: float = 30
    expected_window: int = 475000

    def __post_init__(self):
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (self.checkpoint,self.compact,self.hold)) or not 0 < self.checkpoint < self.compact < self.hold <= 1:
            raise Rejected('Invalid provisional pressure thresholds')
        if type(self.reserve) is not int or self.reserve < 0 or type(self.max_age) not in (int,float) or not math.isfinite(self.max_age) or self.max_age <= 0:
            raise Rejected('Invalid context reserve/freshness')
        if type(self.expected_window) is not int or self.expected_window <= 12000:
            raise Rejected('Invalid effective runtime window')


def natural(value):
    return type(value) is int and value >= 0


class ContextState:
    """One role/server identity; caller serializes ordering at the observer boundary."""
    def __init__(self, path, identity_binding, policy=None, clock=time.time):
        self.path, self.identity, self.policy, self.clock = Path(path), identity_binding, policy or Policy(), clock
        self.lock = threading.RLock()
        self.reading = None
        self.order = -1
        self.last_observed = -1
        self.seen = []
        self.rehydrating = False
        self.compaction = None
        self.restart = False
        self.probe_used = False
        self.recovery_probes = []
        self.soft_checkpoint = None
        self.reconciliations = []
        if self.path.exists():
            saved = json.loads(self.path.read_text())
            if saved.get('sha256') != identity(saved.get('state')):
                raise Rejected('Context ledger tampered; reconcile without resetting budgets')
            state = saved['state']
            saved_binding = UsageIdentity(**state['identity'])
            if state.get('policy') is not None and state['policy'] != asdict(self.policy):
                raise Rejected('Persisted context policy changed; new source-bound scope required')
            for key in ('task','revision','model','producer','schema'):
                if getattr(saved_binding,key) != getattr(self.identity,key):
                    raise Rejected('Persisted context task/revision/profile identity differs')
            self.soft_checkpoint=state.get('soft_checkpoint')
            self.reconciliations=state.get('reconciliations',[])
            if saved_binding.thread == self.identity.thread and saved_binding.task == self.identity.task:
                self.identity = replace(self.identity, epoch=max(self.identity.epoch, saved_binding.epoch))
            self.reading, self.order = state['reading'], state['order']
            self.last_observed, self.seen = state['last_observed'], state['seen']
            self.probe_used, self.compaction = state['probe_used'], state['compaction']
            self.recovery_probes = state.get('recovery_probes', [])
            self.rehydrating, self.restart = True, True
            # Saved readings are retained for audit, never made fresh by restart.

    def persist(self):
        state = dict(identity=asdict(self.identity), reading=self.reading, order=self.order,
            last_observed=self.last_observed, seen=self.seen, rehydrating=self.rehydrating,
            compaction=self.compaction, restart=self.restart, probe_used=self.probe_used, recovery_probes=self.recovery_probes,
            policy=asdict(self.policy),soft_checkpoint=self.soft_checkpoint,reconciliations=self.reconciliations)
        atomic(self.path, json.dumps({'state': state, 'sha256': identity(state)}, sort_keys=True) + '\n')

    def fence_prior_compaction(self,proof):
        if proof.get('kind')!='DEAD_READ_ONLY_COMPACTION_FENCE' or proof.get('new_thread')!=self.identity.thread or proof.get('old_thread')==self.identity.thread:
            raise Rejected('Exact fresh-thread compaction fence required')
        if self.compaction and self.compaction.get('thread') not in (None,proof['old_thread']):
            raise Rejected('Compaction belongs to another unreconciled thread')
        self.reconciliations.append(dict(proof=proof,prior_compaction=self.compaction))
        self.compaction=None;self.restart=self.rehydrating=True
        self.persist()

    def bind_turn(self, binding):
        with self.lock:
            old, new = asdict(self.identity), asdict(binding)
            old.pop('turn'); new.pop('turn')
            if old != new:
                raise Rejected('Usage producer/role/task identity changed; explicit recovery required')
            self.identity = binding

    def update(self, value, binding, order, observed_at):
        with self.lock:
            if binding != self.identity or not natural(order) or order <= self.order:
                raise Rejected('Wrong identity/epoch or duplicate/out-of-order usage')
            if type(observed_at) not in (int, float) or not math.isfinite(observed_at) or observed_at < self.last_observed or observed_at > self.clock():
                raise Rejected('Invalid or out-of-order usage timestamp')
            params = value.get('params', {})
            if value.get('method') != 'thread/tokenUsage/updated' or params.get('threadId') != binding.thread or params.get('turnId') != binding.turn:
                raise Rejected('Wrong wire usage identity')
            raw = params.get('tokenUsage')
            if not isinstance(raw, dict):
                raise Rejected('Malformed usage object')
            fingerprint = identity({'identity': asdict(binding), 'usage': raw})
            if fingerprint in self.seen:
                raise Rejected('Duplicate usage reading')
            latest, total = raw.get('last'), raw.get('total')
            valid = all(isinstance(x, dict) and all(natural(x.get(k)) for k in
                ('inputTokens', 'outputTokens', 'cachedInputTokens', 'reasoningOutputTokens', 'totalTokens'))
                for x in (latest, total))
            window = raw.get('modelContextWindow')
            qualified = valid and type(window) is int and window == self.policy.expected_window
            # Counters are preserved, not recomputed: reasoning may be inclusive.
            self.reading = dict(identity=asdict(binding), observed_at=observed_at, order=order,
                raw=json.loads(json.dumps(raw)), cumulative_billing=total,
                latest_request=latest, cached_input=latest.get('cachedInputTokens') if isinstance(latest, dict) else None,
                active_occupancy='UNKNOWN', effective_window=window,
                quality='REPORTED_FOOTPRINT' if qualified else 'UNKNOWN')
            self.order, self.last_observed = order, observed_at
            self.seen = (self.seen + [fingerprint])[-64:]
            self.restart = False
            self.persist()
            return self.reading

    def decision(self, pending=0, checkpoint_payload=0):
        with self.lock:
            if not natural(pending) or not natural(checkpoint_payload):
                raise Rejected('Pending/checkpoint tokens must be nonnegative policy estimates')
            r = self.reading
            result = dict(action='HOLD', reason='UNKNOWN', active_occupancy='UNKNOWN',
                          pressure_estimate=None, headroom_estimate=None,
                          pending_estimate=pending, checkpoint_payload_estimate=checkpoint_payload,
                          reserve=self.policy.reserve, policy='PROVISIONAL', per_inference_ceiling=False)
            if self.rehydrating or self.compaction or self.restart:
                return {**result, 'reason': 'RECOVERY_REQUIRED'}
            if not r or r['quality'] != 'REPORTED_FOOTPRINT':
                return result
            scope = asdict(self.identity); scope.pop('turn')
            prior = dict(r['identity']); prior.pop('turn')
            age = self.clock() - r['observed_at']
            if scope != prior or age < 0 or age > self.policy.max_age:
                return {**result, 'reason': 'STALE_OR_WRONG_IDENTITY'}
            window, footprint = r['effective_window'], r['latest_request']['totalTokens']
            pressure = (footprint + pending + checkpoint_payload + self.policy.reserve) / window
            ui = max(0, footprint - 12000) / (window - 12000)
            action = 'HOLD' if pressure >= self.policy.hold else 'COMPACT' if pressure >= self.policy.compact else 'CHECKPOINT' if pressure >= self.policy.checkpoint else 'ALLOW'
            return {**result, 'action': action, 'reason': 'LATEST_FOOTPRINT_ESTIMATE',
                'pressure_estimate': pressure, 'native_ui_used_estimate': min(1, ui),
                'headroom_estimate': max(0, window-footprint-pending-checkpoint_payload-self.policy.reserve),
                'native_ui_baseline':12000,'estimator':'UTF8_BYTES_POLICY_ESTIMATE_FOR_PENDING_AND_CHECKPOINT',
                'policy_values':asdict(self.policy)}

    def startup_probe(self, *, phase, payload_bytes, max_tools, max_seconds, explicit=False):
        with self.lock:
            # This reserves a probe only; transport must enforce the same tool/time bounds.
            # Ordinary NativeAdapter.run never consumes it to admit an unknown-context job.
            if not explicit or phase != 'read' or self.reading or self.restart or self.rehydrating or self.compaction or self.probe_used:
                raise Rejected('Unknown context does not authorize ordinary work')
            if not natural(payload_bytes) or payload_bytes > 2048 or not 0 <= max_tools <= 1 or not 0 < max_seconds <= 30:
                raise Rejected('Startup probe exceeds explicit small bounds')
            self.probe_used = True
            self.persist()

    def refresh_probe(self, scope_seal, *, phase, payload_bytes):
        """One same-process read-only refresh per observed reading, no recovery bypass."""
        with self.lock:
            if phase != 'read' or self.restart or self.rehydrating or self.compaction or not self.reading:
                raise Rejected('Refresh cannot replace checkpoint recovery')
            if not natural(payload_bytes) or payload_bytes > 2048 or not scope_seal:
                raise Rejected('Invalid bounded refresh scope')
            key=identity(dict(scope=scope_seal,identity=asdict(self.identity),order=self.order,kind='refresh'))
            if key in self.recovery_probes: raise Rejected('Refresh already attempted; reconcile')
            self.recovery_probes.append(key)
            self.persist()

    def recovery_probe(self, checkpoint, authority, *, phase, payload_bytes, max_tools, max_seconds):
        with self.lock:
            seal = checkpoint.validate(authority)
            if phase != 'read' or self.compaction or not (self.rehydrating or self.restart):
                raise Rejected('Recovery probe requires read-only reconciled recovery hold')
            if not natural(payload_bytes) or payload_bytes > 2048 or not 0 <= max_tools <= 1 or not 0 < max_seconds <= 30:
                raise Rejected('Recovery probe exceeds bounded caps')
            key = identity({'checkpoint': seal, 'identity': asdict(self.identity) | {'turn': 'recovery'}})
            if key in self.recovery_probes:
                raise Rejected('Recovery probe already attempted; reconcile before retry')
            self.recovery_probes.append(key)
            self.persist()

    def status(self):
        with self.lock:
            r = self.reading
            return dict(identity=asdict(self.identity),
                latest_footprint=r['latest_request'] if r else None,
                effective_window=r['effective_window'] if r else None,
                observed_at=r['observed_at'] if r else None,
                freshness_seconds=self.clock()-r['observed_at'] if r else None,
                exact_active_occupancy='UNKNOWN', action=self.decision(),
                rehydrating=self.rehydrating, compaction=self.compaction,
                cumulative_billing=r.get('cumulative_billing') if r else None,
                cached_input=r.get('cached_input') if r else None,raw=r.get('raw') if r else None,
                policy=asdict(self.policy),policy_hash=identity(asdict(self.policy)),
                soft_checkpoint=self.soft_checkpoint,native_ui_baseline=12000)

    def compaction_event(self, method, thread, turn, item_id):
        with self.lock:
            if thread != self.identity.thread or turn != self.identity.turn or not item_id:
                raise Rejected('Compaction identity mismatch')
            if method == 'item/started':
                if self.compaction:
                    raise Rejected('Duplicate compaction start')
                self.compaction = dict(thread=thread, turn=turn, item=item_id)
                self.rehydrating = True
            elif method == 'item/completed':
                if self.compaction != dict(thread=thread, turn=turn, item=item_id):
                    raise Rejected('Compaction completion without matching start')
                self.compaction = None
                self.identity = replace(self.identity, epoch=self.identity.epoch + 1)
                self.restart = True  # Fresh post-compaction usage remains mandatory.
            else:
                raise Rejected('RPC acknowledgement is not compaction completion')
            self.persist()

    def rehydrate(self, checkpoint, current_authority):
        with self.lock:
            checkpoint.validate(current_authority)
            if self.compaction or self.restart or not self.reading:
                raise Rejected('Recovery lacks lifecycle completion/fresh usage')
            r = self.reading
            if r['identity'] != asdict(self.identity) or r['quality'] != 'REPORTED_FOOTPRINT' or not 0 <= self.clock()-r['observed_at'] <= self.policy.max_age:
                raise Rejected('Recovery usage is stale or mismatched')
            self.rehydrating = False
            self.persist()


SECTIONS = frozenset(('request_corrections', 'contract_requirements', 'source_instructions',
    'scope_decisions', 'questions_answers', 'checks_steps_evidence', 'inflight_uncertain',
    'lease_generations', 'references', 'next_action'))


class Checkpoint:
    """Hash-bound originals and authority; a model summary is never sufficient."""
    def __init__(self, path, artifact_root):
        self.path, self.root = Path(path), Path(artifact_root).resolve()

    def save(self, authority, artifacts):
        if set(authority) != SECTIONS:
            raise Rejected('Checkpoint missing authoritative sections')
        records = {name: digest(safe_path(self.root, name).read_bytes()) for name in artifacts}
        if not records:
            raise Rejected('Checkpoint must reference authoritative original artifacts')
        state = dict(authority=authority, artifacts=records)
        atomic(self.path, json.dumps({'state': state, 'sha256': identity(state)}, sort_keys=True), exclusive=True)
        return identity(state)

    def validate(self, current_authority):
        saved = json.loads(self.path.read_text())
        state = saved.get('state')
        if saved.get('sha256') != identity(state) or not isinstance(state, dict):
            raise Rejected('Checkpoint manifest tampered')
        if set(current_authority) != SECTIONS or state['authority'] != current_authority:
            raise Rejected('Checkpoint authority/questions/checks/lease changed')
        if current_authority['questions_answers'].get('pending') or current_authority['inflight_uncertain'] or current_authority['next_action'].get('human_gate'):
            raise Rejected('Recovery cannot bypass questions/uncertain effects/human gate')
        for name, expected in state['artifacts'].items():
            try:
                actual = digest(safe_path(self.root, name).read_bytes())
            except OSError as ex:
                raise Rejected('Checkpoint artifact missing') from ex
            if actual != expected:
                raise Rejected('Checkpoint original artifact modified')
        return saved['sha256']


def validate_research_claim(claim, receipts):
    """Require actual original-page evidence; URLs/snippets alone cannot ground claims."""
    required = {'url', 'title', 'retrieved_at', 'version', 'section', 'kind', 'claim', 'limitations'}
    if not isinstance(claim, dict) or set(claim) != required or claim['kind'] not in ('observation', 'inference', 'proposal'):
        raise Rejected('Incomplete source-backed claim record')
    if not all(isinstance(claim[k], str) and claim[k].strip() for k in required - {'limitations'}):
        raise Rejected('Missing inspected original metadata')
    searched = any(r.get('tool') == 'hosted_search' and r.get('status') == 'completed' for r in receipts)
    inspected = any(r.get('tool') == 'original_page' and r.get('status') == 'completed'
        and r.get('url') == claim['url'] and r.get('section') == claim['section']
        and r.get('relevant') is True and r.get('evidence_hash') for r in receipts)
    if not searched or not inspected:
        raise Rejected('Original-page inspection absent, unavailable or irrelevant')
    return claim


def derive_checkpoint(parent, target, current_authority, transition):
    """Only exact observed role-process lineage may change; originals remain bound."""
    original = json.loads(parent.path.read_text())
    prior = original.get('state', {}).get('authority')
    parent_seal = parent.validate(prior)
    if transition.get('kind') not in ('replacement', 'restart', 'remount', 'write-recovery') or set(transition) != {'kind', 'old', 'new'}:
        raise Rejected('Explicit observed role transition required')
    old, new = prior['lease_generations'], current_authority['lease_generations']
    mutable = {'role_generation', 'thread', 'server', 'process', 'phase'}
    if transition['old'] != {k: old.get(k) for k in mutable} or transition['new'] != {k: new.get(k) for k in mutable}:
        raise Rejected('Observed role transition does not match checkpoint identities')
    if new['role_generation'] != old['role_generation'] + 1 or (new.get('phase') != 'read' and not (transition['kind'] == 'write-recovery' and new.get('phase') == 'write' and new.get('role') == 'doer')):
        raise Rejected('Recovery transition must advance one role generation in read-only mode')
    if transition['kind'] != 'replacement' and old['thread'] != new['thread']:
        raise Rejected('Resume/remount cannot change thread')
    if transition['kind'] == 'replacement' and old['thread'] == new['thread']:
        raise Rejected('Replacement must create a fresh thread')
    stable = json.loads(json.dumps(prior))
    stable['lease_generations'].update({k: new.get(k) for k in mutable if k in new})
    if stable != current_authority:
        raise Rejected('Lineage cannot change source/instructions/inputs/task/questions/checks/lease')
    records = list(original['state']['artifacts']) + [str(parent.path.resolve().relative_to(parent.root))]
    target.save(current_authority, records)
    receipt = {'parent_sha256': parent_seal, 'derived_sha256': target.validate(current_authority), 'transition': transition}
    atomic(target.path.with_suffix('.lineage.json'), json.dumps(receipt, sort_keys=True), exclusive=True)
    return receipt


def configured_policy(settings):
    return settings.policy() if callable(getattr(settings,'policy',None)) else Policy()


def persisted_status(path, *, clock=time.time):
    """Observe a durable ledger without initialization, writes or freshening it."""
    path=Path(path);saved=json.loads(path.read_text());data=saved.get('state')
    if path.is_symlink() or saved.get('sha256')!=identity(data):raise Rejected('Invalid durable context ledger')
    state=ContextState.__new__(ContextState)
    state.path=path;state.identity=UsageIdentity(**data['identity']);state.policy=Policy(**data.get('policy',{}));state.clock=clock;state.lock=threading.RLock()
    for name,default in [('reading',None),('order',-1),('last_observed',-1),('seen',[]),('rehydrating',False),('compaction',None),('restart',False),('probe_used',False),('recovery_probes',[]),('soft_checkpoint',None)]:setattr(state,name,data.get(name,default))
    return state.status()
