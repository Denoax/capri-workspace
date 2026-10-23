import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from loop.native import Backend
from loop.native_protocol import Lifecycle
from loop.native_receipts import ReceivedReceipts
from loop.util import Rejected


def event(method, **params):
    return dict(method=method, params=dict(threadId='thread', **params))


def frames(count):
    result = [event('turn/started', turn=dict(id='turn', status='inProgress'))]
    for n in range(count):
        item = dict(id='tool-'+str(n+1), type='webSearch')
        result += [event('item/started', turnId='turn', item=item),
                   event('item/completed', turnId='turn', item=item)]
    return result


class ReceivedFrameTests(unittest.TestCase):
    def reader(self, root, values, observer=None):
        backend = Backend.__new__(Backend)
        backend.root, backend.role, backend.generation = root, 'thinker', 1
        backend.thread, backend.prior = 'thread', None
        backend.lock = threading.RLock()
        backend.pending, backend.clients = {}, set()
        backend.active = Lifecycle('thread')
        backend.turn_bytes, backend.error, backend.empty = 0, None, True
        backend.observed_terminal = None
        backend.observer = observer
        backend.proc = SimpleNamespace(stdout=io.BytesIO(b''.join(
            json.dumps(v).encode()+b'\n' if isinstance(v, dict) else v for v in values)))
        with patch('loop.native.subprocess.Popen', side_effect=AssertionError('No model processes')):
            backend._reader()
        receipts = [json.loads(line) for line in (root/'received-frames.jsonl').read_text().splitlines()]
        return backend, receipts

    def test_thirteenth_start_is_durable_but_not_trusted(self):
        with tempfile.TemporaryDirectory() as temp:
            observed = []
            b, receipts = self.reader(Path(temp), frames(13), lambda *args: observed.append(args[-1]))
            starts = [r for r in receipts if r['phase']=='RECEIVED' and r['envelope'].get('method')=='item/started']
            self.assertEqual(len(starts), 13)
            self.assertEqual(starts[-1]['envelope']['item']['id'], 'tool-13')
            self.assertEqual(receipts[-1]['sequence'], starts[-1]['sequence'])
            self.assertEqual(receipts[-1]['reason'], 'EXPOSED_TOOL_BUDGET')
            self.assertEqual(receipts[-1]['phase'], 'REJECTED')
            self.assertEqual(sum(v['method']=='item/started' for v in observed), 12)
            self.assertEqual(b.error, 'Native turn exceeded exposed tool budget')
            with self.assertRaisesRegex(Rejected, 'tool budget'):
                b.active.feed(event('turn/completed', turn=dict(id='turn', status='completed')))

    def test_twelve_tools_complete_and_validate(self):
        values = frames(12)
        item = dict(id='answer', type='agentMessage', text='ok', phase='final_answer')
        values += [event('item/started', turnId='turn', item=item),
                   event('item/completed', turnId='turn', item=item),
                   event('turn/completed', turn=dict(id='turn', status='completed'))]
        with tempfile.TemporaryDirectory() as temp:
            b, receipts = self.reader(Path(temp), values)
            self.assertEqual(b.active.finish(lambda x:x=='ok', lambda:True), 'ok')
            self.assertEqual(sum(r['phase']=='VALIDATED' for r in receipts), len(values))

    def test_invalid_identity_does_not_reach_state_observer(self):
        for invalid in [dict(method='turn/started', params=dict(threadId='other', turn=dict(id='turn'))),
                        b'{bad json}\n', b'x'*1_000_001]:
            with self.subTest(invalid_type=type(invalid).__name__), tempfile.TemporaryDirectory() as temp:
                observed=[]
                b, receipts=self.reader(Path(temp), [invalid], lambda *args:observed.append(args))
                self.assertEqual(observed, [])
                self.assertEqual(receipts[-1]['phase'], 'REJECTED')
                self.assertFalse(b.active.started)

    def test_duplicate_and_unstarted_completion_still_reject(self):
        for extra in [frames(1)[1], event('item/completed', turnId='turn', item=dict(id='unknown', type='webSearch'))]:
            with tempfile.TemporaryDirectory() as temp:
                b, receipts=self.reader(Path(temp), frames(1)[:2]+[extra])
                self.assertEqual(len(b.active.tools), 1)
                self.assertEqual(receipts[-1]['phase'], 'REJECTED')

    def test_reasoning_and_credentials_never_enter_metadata(self):
        secret='sk-'+('x'*60)
        values=[event('turn/started', turn=dict(id='turn')),
                event('item/started', turnId='turn', item=dict(id=secret,type='reasoning',text='PRIVATE REASONING',password=secret))]
        with tempfile.TemporaryDirectory() as temp:
            self.reader(Path(temp), values)
            text=(Path(temp)/'received-frames.jsonl').read_text()
            self.assertNotIn(secret,text)
            self.assertNotIn('PRIVATE REASONING',text)
            self.assertNotIn('password',text)

    def test_unrecognized_identifier_is_hashed_instead_of_exposing_a_secret(self):
        credential='ArbitraryCredentialWithoutARecognizablePrefix'
        with tempfile.TemporaryDirectory() as temp:
            sink=ReceivedReceipts(Path(temp),'thinker',1)
            sink.received(json.dumps(dict(method=credential,params=dict(item=dict(id=credential,type=credential)))).encode(),'thread')
            self.assertNotIn(credential,sink.path.read_text())

    def test_capture_failure_and_overflow_hold_reader(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(ReceivedReceipts,'received',side_effect=OSError('disk unavailable')):
                b,_=self.reader(Path(temp),frames(1))
            self.assertIn('disk unavailable',b.error)
            self.assertFalse(b.active.started)
        with tempfile.TemporaryDirectory() as temp:
            sink=ReceivedReceipts(Path(temp),'thinker',1,max_bytes=1)
            with self.assertRaisesRegex(Rejected,'byte budget'):
                sink.received(b'{}\n','thread')


if __name__=='__main__':
    unittest.main()
