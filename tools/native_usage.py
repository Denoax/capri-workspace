"""Parent-only conversion of hash-bound public native usage receipts.

Only an observed cumulative delta equal to `last` becomes one inference row.
Ambiguous/missing updates remain gaps. Raw bodies and private reasoning are
never copied. This tool cannot certify capture coverage from a caller flag.
"""
import argparse
import hashlib
import json
from pathlib import Path

COUNTERS = ('inputTokens', 'cachedInputTokens', 'cacheWriteInputTokens',
            'outputTokens', 'reasoningOutputTokens', 'totalTokens')
REQUIRED = set(COUNTERS)-{'cacheWriteInputTokens'}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def bound_file(spec):
    p=Path(spec['path'])
    if not p.is_absolute() or p.is_symlink() or not p.is_file() or p.stat().st_size>32_000_000:
        raise ValueError('Regular bounded absolute receipt required')
    raw=p.read_bytes()
    if sha(raw)!=spec['sha256']:raise ValueError('Receipt identity changed')
    return raw


def counters(value):
    if not isinstance(value,dict) or not REQUIRED<=set(value) or set(value)-set(COUNTERS):
        raise ValueError('Unknown/incomplete native token breakdown')
    result={name:value.get(name,0) for name in COUNTERS}
    if any(type(v) is not int or v<0 for v in result.values()):raise ValueError('Invalid native token count')
    if (result['cachedInputTokens']+result['cacheWriteInputTokens']>result['inputTokens'] or
            result['reasoningOutputTokens']>result['outputTokens'] or
            result['totalTokens']!=result['inputTokens']+result['outputTokens']):
        raise ValueError('Unqualified token-bucket semantics')
    return result


def convert(inventory, schema):
    """Return partial measured rows plus explicit gaps, never a billing claim."""
    if inventory.get('schema')!='capri-native-usage-inventory-v1':raise ValueError('Versioned parent inventory required')
    definitions=json.loads(bound_file(schema))['definitions']
    fields=definitions['TokenUsageBreakdown']
    if (set(fields['properties'])!=set(COUNTERS) or set(fields['required'])!=REQUIRED or
            fields['properties']['cacheWriteInputTokens'].get('default')!=0):
        raise ValueError('Installed usage schema differs; requalify normalization')
    requests=[];gaps=[];previous={};seen=set();sources=[];turns=set();accounted=set()
    for spec in inventory['captures']:
        if spec.get('role') not in ('thinker','doer','reviewer') or type(spec.get('generation')) is not int:
            raise ValueError('Exact role/generation binding required')
        raw=bound_file(spec);sources.append({k:spec[k] for k in ('path','sha256','role','generation')})
        for line_number,line in enumerate(raw.splitlines(),1):
            row=json.loads(line)
            if row.get('role')!=spec['role'] or row.get('generation')!=spec['generation']:
                raise ValueError('Capture producer identity differs')
            message=row.get('message',{});params=message.get('params',{});method=message.get('method')
            thread=params.get('threadId');turn=params.get('turnId')
            if method=='turn/started':
                turns.add((thread,params['turn']['id']))
            if method!='thread/tokenUsage/updated':continue
            if not thread or not turn:raise ValueError('Usage thread/turn identity missing')
            usage=params['tokenUsage'];last=counters(usage['last']);total=counters(usage['total'])
            fingerprint=(thread,tuple(total[n] for n in COUNTERS),tuple(last[n] for n in COUNTERS))
            if fingerprint in seen:continue
            seen.add(fingerprint)
            prior=previous.get(thread,{n:0 for n in COUNTERS})
            delta={n:total[n]-prior[n] for n in COUNTERS}
            previous[thread]=total
            evidence=dict(path=spec['path'],sha256=spec['sha256'],line=line_number,
                          role=spec['role'],generation=spec['generation'],turn=turn)
            if delta!=last or any(v<0 for v in delta.values()):
                gaps.append(dict(code='AMBIGUOUS_OR_MISSING_INFERENCE_BOUNDARY',evidence=evidence));continue
            if not total['totalTokens']:
                continue
            # Reasoning is a subset, not an extra billed output bucket. Equality
            # with totalTokens above is part of this exact normalization contract.
            write=last['cacheWriteInputTokens']
            request=dict(thread_id=thread,request_id='native-total:'+sha(json.dumps(total,sort_keys=True).encode()),
                model='gpt-6.1-sol',usage_kind='per_request',
                uncached_input_tokens=last['inputTokens']-last['cachedInputTokens']-write,
                cached_input_tokens=last['cachedInputTokens'],cache_write_input_tokens=write,
                output_tokens=last['outputTokens'],reasoning_output_tokens_included=last['reasoningOutputTokens'],
                cache_write_ttl=None,evidence=evidence,
                request_identity='DERIVED_CUMULATIVE_BOUNDARY_NOT_PROVIDER_REQUEST_ID')
            if write:gaps.append(dict(code='CACHE_WRITE_RETENTION_TIER_UNREPORTED',evidence=evidence))
            requests.append(request);accounted.add((thread,turn))
    for thread,turn in sorted(turns-accounted):
        gaps.append(dict(code='STARTED_TURN_WITHOUT_NORMALIZED_USAGE',thread=thread,turn=turn))
    # No flag in a JSON inventory establishes that every charged probe/retry,
    # compaction/idle notification and failed process was captured. Reconcile
    # these public rows with the parent dispatch/process ledger before promoting
    # them into a completed benchmark trial. This converter never does so.
    gaps.append(dict(code='PARENT_DISPATCH_AND_CHARGED_RETRY_COVERAGE_NOT_RECONCILED'))
    return dict(schema='capri-native-normalized-usage-v1',requests=requests,gaps=gaps,
        usage_complete=False,sources=sources,schema_evidence=schema,
        exact_active_occupancy='UNKNOWN',actual_billed_usd=None,
        cost_basis='PARTIAL_PUBLIC_TOKEN_COUNTS; RETENTION_AND_FULL_COVERAGE_REQUIRED',
        synthetic=inventory.get('evidence_kind')!='NATIVE_MEASUREMENT')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path);parser.add_argument('--schema',type=Path,required=True)
    parser.add_argument('--schema-sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(convert(json.loads(args.inventory.read_text()),
        dict(path=str(args.schema.resolve()),sha256=args.schema_sha256)),indent=2))


if __name__=='__main__':main()
