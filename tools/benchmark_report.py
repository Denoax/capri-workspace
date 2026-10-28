"""Summarize normalized benchmark receipts; never launch models or infer billing.

Usage must be normalized to one row per inference request by the collector.
Repeated cumulative app-server snapshots are not valid request rows.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

MODEL = 'gpt-6.1-sol'
TOKEN_FIELDS = ('uncached_input_tokens', 'cached_input_tokens',
                'cache_write_input_tokens', 'output_tokens')


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid nonnegative number: ' + name)
    return value


def token_cost(request, prices):
    if request.get('usage_kind') != 'per_request' or request.get('model') != MODEL:
        raise ValueError('Exact model and normalized per-request usage required')
    for field in TOKEN_FIELDS:
        value = request.get(field)
        if type(value) is not int or value < 0:
            raise ValueError('Invalid token count: ' + field)
    prompt = sum(request[k] for k in TOKEN_FIELDS[:3])
    long = prompt > prices['long_context_threshold']
    input_factor = prices['long_input_multiplier'] if long else 1
    output_factor = prices['long_output_multiplier'] if long else 1
    ttl = request.get('cache_write_ttl')
    if request['cache_write_input_tokens'] and ttl not in ('30m', '12h'):
        raise ValueError('Cache writes require a known retention tier')
    write_rate = prices['cache_write_12h'] if ttl == '12h' else prices['cache_write_30m']
    cost = input_factor * (request['uncached_input_tokens'] * prices['uncached_input'] +
                           request['cached_input_tokens'] * prices['cached_input'] +
                           request['cache_write_input_tokens'] * write_rate)
    cost += request['output_tokens'] * prices['output'] * output_factor
    return cost / 1_000_000, prompt


def summarize(document, prices):
    if document.get('schema') != 'capri-benchmark-v1' or not document.get('runset'):
        raise ValueError('Versioned benchmark runset required')
    if (prices.get('model') != MODEL or prices.get('service_tier') != 'standard' or
            prices.get('currency') != 'USD' or prices.get('per_tokens') != 1_000_000):
        raise ValueError('Only the supplied exact-model Standard price profile is supported')
    for key in ('uncached_input', 'cached_input', 'cache_write_30m', 'cache_write_12h',
                'output', 'long_context_threshold', 'long_input_multiplier', 'long_output_multiplier'):
        number(prices.get(key), key)
    arms = document['arms']
    if len(arms) != len(set(arms)) or len(arms) < 2:
        raise ValueError('Distinct comparison arms required')
    rows, seen, keys = defaultdict(list), set(), defaultdict(set)
    source, profiles = None, {}
    for trial in document['trials']:
        arm = trial['arm']
        key = (trial['task'], trial['replicate'])
        if arm not in arms or (arm, key) in seen:
            raise ValueError('Unknown arm or duplicate trial')
        seen.add((arm, key)); keys[arm].add(key)
        status = trial['status']
        if status not in ('COMPLETED', 'ABORTED', 'NOT_RUN'):
            raise ValueError('Unknown trial status')
        if not trial.get('source') or not trial.get('profile'):
            raise ValueError('Source and profile identities required')
        source = source or trial['source']
        if trial['source'] != source or profiles.get(arm, trial['profile']) != trial['profile']:
            raise ValueError('Do not pool source revisions or change an arm profile mid-runset')
        profiles[arm] = trial['profile']
        requests = trial.get('requests', [])
        if status == 'NOT_RUN' and requests:
            raise ValueError('An unrun trial cannot contain inference usage')
        request_ids, cost, tokens, peak = set(), 0.0, 0, 0
        for request in requests:
            rid = (request.get('thread_id'), request.get('request_id'))
            if not all(rid) or rid in request_ids or not request.get('evidence'):
                raise ValueError('Unique thread/request identity and evidence required')
            request_ids.add(rid)
            value, prompt = token_cost(request, prices)
            cost += value; tokens += prompt + request['output_tokens']; peak = max(peak, prompt)
        complete = (status != 'NOT_RUN' and trial.get('usage_complete') is True and bool(requests))
        passed = status == 'COMPLETED' and trial.get('grader_pass') is True
        if passed and not trial.get('grader_evidence'):
            raise ValueError('Passing outcome requires parent grader evidence')
        wall = trial.get('wall_seconds')
        if wall is not None: number(wall, 'wall_seconds')
        rows[arm].append(dict(status=status, passed=passed, usage_complete=complete,
                              token_api_usd=cost, recorded_tokens=tokens,
                              peak_request_input=peak, wall=wall,
                              synthetic=trial.get('evidence_kind') != 'NATIVE_MEASUREMENT'))
    if any(keys[a] != keys[arms[0]] for a in arms[1:]):
        raise ValueError('Every arm must retain the same scheduled task/replicate keys')
    report = dict(schema='capri-benchmark-report-v1', runset=document['runset'], arms={},
                  actual_billed_usd=None, exact_active_occupancy='UNKNOWN',
                  price_profile=prices['profile'],
                  cost_basis='STANDARD_API_EQUIVALENT_TOKEN_ESTIMATE_ONLY',
                  tool_and_infrastructure_costs='EXCLUDED',
                  general_superiority_claim='NOT_ESTABLISHED')
    for arm in arms:
        values = rows[arm]; started = [r for r in values if r['status'] != 'NOT_RUN']
        complete = bool(started) and all(r['usage_complete'] for r in started)
        passes = sum(r['passed'] for r in started)
        cost = sum(r['token_api_usd'] for r in started) if complete else None
        report['arms'][arm] = dict(scheduled=len(values), started=len(started), passed=passes,
            aborted=sum(r['status'] == 'ABORTED' for r in values), not_run=len(values)-len(started),
            pass_rate_started=passes/len(started) if started else None,
            recorded_tokens=sum(r['recorded_tokens'] for r in started),
            usage_complete=complete, token_api_equivalent_usd=cost,
            token_api_usd_per_pass=cost/passes if cost is not None and passes else None,
            peak_request_input_tokens=max((r['peak_request_input'] for r in started), default=None),
            wall_seconds=sum(r['wall'] for r in started) if started and all(r['wall'] is not None for r in started) else None,
            synthetic_or_unverified=any(r['synthetic'] for r in started))
    comparisons = {}
    for reference, arm in ((arms[i], arms[j]) for i in range(len(arms)) for j in range(i+1, len(arms))):
        base = report['arms'][reference]
        managed = report['arms'][arm]
        eligible = (base['started'] > 0 and base['not_run'] == managed['not_run'] == 0 and
                    base['usage_complete'] and managed['usage_complete'] and
                    not base['synthetic_or_unverified'] and not managed['synthetic_or_unverified'])
        b, m = base['token_api_usd_per_pass'], managed['token_api_usd_per_pass']
        key = arm if reference == arms[0] else arm+'__vs__'+reference
        comparisons[key] = dict(reference_arm=reference, descriptive_only=True,
            token_api_cost_per_pass_savings_percent=(1-m/b)*100 if eligible and b and m is not None else None,
            all_scheduled_usage_observed=eligible,
            note='Includes failed and aborted run costs; subscription billing and product superiority remain unmeasured.')
    report['comparisons'] = comparisons
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipts', type=Path)
    parser.add_argument('--prices', type=Path, default=Path(__file__).resolve().parents[1]/'evaluation/benchmark-v1/prices.json')
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.receipts.read_text()), json.loads(args.prices.read_text())), indent=2))


if __name__ == '__main__':
    main()
