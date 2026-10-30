import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from loop.native_owner_material import completed_turn,foreground_line
from loop.native_startup_repair import records
from loop.util import digest,Rejected


class CompletedOwnerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'events.jsonl'
        self.row=dict(thread='thread',generation=9)

    def capture(self,starts=1,ends=1,status='completed',generation=9):
        events=[]
        for _ in range(starts):events.append(dict(role='thinker',generation=generation,message=dict(method='turn/started',params=dict(threadId='thread',turn={'id':'turn'}))))
        for _ in range(ends):events.append(dict(role='thinker',generation=generation,message=dict(method='turn/completed',params=dict(threadId='thread',turn=dict(id='turn',status=status)))))
        self.path.write_text(''.join(json.dumps(e)+'\n' for e in events));return dict(path=str(self.path),sha256=digest(self.path.read_bytes()))

    def test_matching_successful_terminal_is_required(self):
        self.assertEqual(completed_turn(self.capture(),self.row),'turn')

    def test_missing_duplicate_failed_or_wrong_generation_terminal_is_held(self):
        for kw in ({'ends':0},{'ends':2},{'starts':2},{'status':'failed'},{'generation':10}):
            with self.subTest(kw=kw),self.assertRaises(Rejected):completed_turn(self.capture(**kw),self.row)

    def test_capture_bytes_cannot_be_changed_after_binding(self):
        spec=self.capture();self.path.write_text('changed')
        with self.assertRaises(Rejected):completed_turn(spec,self.row)

    def test_foreground_instruction_names_exact_source_and_binding(self):
        b=dict(intent_event=271,target_source='a'*64,other='preserved')
        line=foreground_line(b);self.assertIn('271',line);self.assertIn('a'*64,line)
        self.assertNotEqual(line,foreground_line({**b,'other':'changed'}))


if __name__=='__main__':unittest.main()
