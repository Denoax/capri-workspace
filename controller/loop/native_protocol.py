"""Native 0.163 JSON-RPC lifecycle; deliberately independent of exec JSONL."""
import json
import time
from .util import Rejected

TOOL_ITEMS = frozenset(('commandExecution', 'mcpToolCall', 'webSearch', 'dynamicToolCall'))


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Rejected('Duplicate JSON key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(Rejected('Nonfinite JSON')))
    except (ValueError, TypeError) as ex:
        raise Rejected('Malformed native JSON') from ex
    if not isinstance(value, dict):
        raise Rejected('Native message must be an object')
    return value


class Lifecycle:
    """One bounded turn. Terminal errors latch and cannot be repaired by later events."""
    def __init__(self, thread, packet_hash=None, clock=time.monotonic, max_seconds=240, max_tools=12):
        self.thread, self.packet_hash, self.clock = thread, packet_hash, clock
        if not 0 < max_seconds <= 240 or type(max_tools) is not int or not 0 <= max_tools <= 12:
            raise Rejected('Invalid bounded lifecycle limits')
        self.max_seconds, self.max_tools = max_seconds, max_tools
        self.begin = clock()
        self.turn = None
        self.started = False
        self.terminal = None
        self.failure = None
        self.acked = packet_hash is None
        self.tools = set()
        self.items = {}
        self.final = None

    def reject(self, reason):
        self.failure = self.failure or reason
        raise Rejected(self.failure)

    def budget(self):
        if self.clock() - self.begin >= self.max_seconds:
            self.reject('Native turn exceeded wall budget; reconcile effects')
        if self.failure:
            raise Rejected(self.failure)

    def bind_response(self, turn):
        if not isinstance(turn, str) or not turn or (self.turn and self.turn != turn):
            self.reject('Conflicting turn/start response')
        self.turn = turn

    def feed(self, value):
        self.budget()
        method, p = value.get('method'), value.get('params', {})
        if not isinstance(method, str) or not isinstance(p, dict):
            self.reject('Malformed notification')
        if method == 'model/rerouted':
            self.reject('Model substitution is unauthorized')
        relevant = method.startswith(('turn/', 'item/')) or method == 'thread/tokenUsage/updated'
        if not relevant:
            return
        if p.get('threadId') != self.thread:
            self.reject('Wrong native thread')
        turn = p.get('turn', {}) if method in ('turn/started', 'turn/completed') else None
        if turn is not None and not isinstance(turn, dict):
            self.reject('Malformed turn')
        tid = turn.get('id') if turn is not None else p.get('turnId')
        if not isinstance(tid, str) or not tid or (self.turn and tid != self.turn):
            self.reject('Wrong or missing native turn')
        if method == 'turn/started':
            if self.started or self.terminal:
                self.reject('Duplicate/out-of-order turn start')
            self.turn, self.started = tid, True
            return
        if not self.started or self.terminal:
            self.reject('Event outside active turn')
        if method == 'turn/completed':
            status = turn.get('status')
            self.terminal = status
            if status != 'completed' or turn.get('error'):
                self.reject('Turn failed/interrupted or malformed terminal status')
            if not self.acked:
                self.reject('Missing execution ACK')
            return
        if method not in ('item/started', 'item/completed'):
            return
        item = p.get('item')
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not isinstance(item.get('type'), str):
            self.reject('Malformed native item')
        iid, kind = item['id'], item['type']
        if method == 'item/started':
            if iid in self.items:
                self.reject('Duplicate item start')
            self.items[iid] = (kind, False)
            if kind in TOOL_ITEMS:
                if not self.acked:
                    self.reject('Tool before exact packet ACK')
                self.tools.add(iid)
                if len(self.tools) > self.max_tools:
                    self.reject('Native turn exceeded exposed tool budget')
        else:
            if self.items.get(iid) != (kind, False):
                self.reject('Unstarted/duplicate/conflicting item completion')
            self.items[iid] = (kind, True)
            if kind == 'agentMessage':
                text = item.get('text')
                if not isinstance(text, str):
                    self.reject('Malformed agent message')
                if self.packet_hash and text.startswith('ACK:' + self.packet_hash):
                    self.acked = True
                if item.get('phase') == 'final_answer':
                    self.final = text

    def finish(self, validate_output, independent_checks):
        self.budget()
        if self.terminal != 'completed' or any(not done for _, done in self.items.values()):
            self.reject('Missing successful complete lifecycle')
        if self.final is None or not validate_output(self.final) or not independent_checks():
            self.reject('Output/check evidence not validated')
        return self.final


class CompactionLifecycle(Lifecycle):
    """An explicit idle compaction operation, never an unadmitted ordinary turn."""
    def __init__(self, thread, **kwargs):
        super().__init__(thread, max_tools=0, **kwargs)
        self.compaction_item = None
        self.compaction_done = False

    def feed(self, value):
        super().feed(value)
        method, params = value.get('method'), value.get('params', {})
        item = params.get('item', {})
        if item.get('type') == 'contextCompaction':
            if method == 'item/started':
                if self.compaction_item:
                    self.reject('Duplicate compaction item')
                self.compaction_item = item['id']
            elif method == 'item/completed':
                if item['id'] != self.compaction_item:
                    self.reject('Conflicting compaction item')
                self.compaction_done = True

    def finish_compaction(self):
        self.budget()
        if self.terminal != 'completed' or not self.compaction_done or any(not done for _, done in self.items.values()):
            self.reject('Compaction lacks successful matching item and terminal lifecycle')
        return self.turn
