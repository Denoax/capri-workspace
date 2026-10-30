import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.native_usage import convert, COUNTERS


class NativeUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        def bound(name,data):
            p=self.root/name;p.write_bytes(data)
            return dict(path=str(p),sha256=hashlib.sha256(data).hexdigest())
        self.bound=bound
        definition=dict(definitions={'TokenUsageBreakdown':dict(properties={k:({'default':0} if k=='cacheWriteInputTokens' else {}) for k in COUNTERS},required=[k for k in COUNTERS if k!='cacheWriteInputTokens'])})
        self.schema=bound('schema.json',json.dumps(definition).encode())

    def usage(self,input=100,output=20,cache=40,write=0,reason=5):
        return dict(inputTokens=input,outputTokens=output,cachedInputTokens=cache,
            cacheWriteInputTokens=write,reasoningOutputTokens=reason,totalTokens=input+output)

    def run_rows(self,values):
        rows=[dict(role='thinker',generation=7,message=dict(method='thread/tokenUsage/updated',
            params=dict(threadId='thread',turnId='turn',tokenUsage=dict(last=last,total=total)))) for last,total in values]
        cap=self.bound('events.jsonl',b''.join(json.dumps(v).encode()+b'\n' for v in rows));cap.update(role='thinker',generation=7)
        return convert(dict(schema='capri-native-usage-inventory-v1',captures=[cap],evidence_kind='SYNTHETIC_CONTROL'),self.schema)

    def test_duplicate_snapshots_are_not_added_twice(self):
        a=self.usage();r=self.run_rows([(a,a),(a,a)])
        self.assertEqual(len(r['requests']),1);self.assertEqual(r['requests'][0]['output_tokens'],20)
        self.assertEqual(r['requests'][0]['uncached_input_tokens'],60)
        self.assertFalse(r['usage_complete']);self.assertTrue(r['synthetic'])

    def test_reasoning_is_inclusive_and_never_added_twice(self):
        a=self.usage(reason=15);r=self.run_rows([(a,a)])
        self.assertEqual(r['requests'][0]['output_tokens'],20)
        self.assertEqual(r['requests'][0]['reasoning_output_tokens_included'],15)

    def test_two_exact_cumulative_boundaries_make_two_rows(self):
        a=self.usage();total={k:v*2 for k,v in a.items()};r=self.run_rows([(a,a),(a,total)])
        self.assertEqual(len(r['requests']),2);self.assertNotEqual(r['requests'][0]['request_id'],r['requests'][1]['request_id'])

    def test_missing_updates_and_counter_resets_stay_gaps(self):
        a=self.usage();total={k:v*3 for k,v in a.items()};r=self.run_rows([(a,total),(a,a)])
        self.assertEqual(r['requests'],[])
        self.assertEqual(sum(x['code']=='AMBIGUOUS_OR_MISSING_INFERENCE_BOUNDARY' for x in r['gaps']),2)

    def test_schema_default_zero_write_is_allowed_but_positive_write_ttl_is_unknown(self):
        a=self.usage(write=10);r=self.run_rows([(a,a)])
        self.assertEqual(r['requests'][0]['uncached_input_tokens'],50)
        self.assertIn('CACHE_WRITE_RETENTION_TIER_UNREPORTED',[x['code'] for x in r['gaps']])
        a.pop('cacheWriteInputTokens');r=self.run_rows([(a,a)])
        self.assertEqual(r['requests'][0]['cache_write_input_tokens'],0)

    def test_invalid_counts_and_changed_raw_evidence_are_rejected(self):
        for a in (self.usage(cache=101),self.usage(reason=21),{**self.usage(),'inputTokens':True}):
            with self.subTest(a=a),self.assertRaises(ValueError):self.run_rows([(a,a)])
        Path(self.schema['path']).write_text('{}')
        with self.assertRaises(ValueError):self.run_rows([])


if __name__=='__main__':unittest.main()
