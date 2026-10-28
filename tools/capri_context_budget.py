#!/usr/bin/env python3
"""Illustrative arithmetic only; never a model/tokenizer/usage measurement."""
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import json
ROOT=Path(__file__).resolve().parents[1]
def calculate(data):
    totals={s['id']:sum(s['values']) for s in data['series']}
    percent=lambda a,b:str((Decimal(a-b)*100/Decimal(a)).quantize(Decimal('.1'),rounding=ROUND_HALF_UP))
    return {'evidence_class':'ILLUSTRATIVE_ASSUMPTIONS_NOT_MODEL_RUN','calls':data['calls'],'total_assumed_input_tokens':totals,'scoped_vs_growing_percent_lower':percent(totals['growing'],totals['scoped']),'scoped_vs_curated_percent_lower':percent(totals['curated'],totals['scoped']),'cache_counterexample':{'relative_cached_rate':'0.05','growing_weighted_units':str(Decimal(50000)+Decimal(130000)*Decimal('.05')),'scoped_weighted_units':'60000','prices_or_usage':False},'quality_equivalence':'untested','cost_savings':None,'measured_capri_savings':None}
if __name__=='__main__':
    data=json.loads((ROOT/'showcase/capri/source-match/source/assets/data/context-budget.json').read_text());print(json.dumps(calculate(data),indent=2))


def story_model(data, configuration):
    """One arithmetic path for authored Markdown, graphics and local controls.

    Controls select precomputed rows, so they cannot grow a second cost model.
    Existing calculate() output remains compatible with archived source-match data.
    """
    result = calculate(data)
    policies = []
    for series in data['series']:
        values = series['values']
        if len(values) != data['calls'] or any(type(v) is not int or v < 0 for v in values):
            raise ValueError('Expected nonnegative integer inputs for every request')
        label = 'Curated single session' if series['id'] == 'curated' else series['label']
        policies.append({**series, 'label': label, 'total': result['total_assumed_input_tokens'][series['id']], 'peak_request': max(values)})
    totals = result['total_assumed_input_tokens']
    rows = []
    for request in range(data['calls']):
        rows.append({'request': request + 1, 'values': {s['id']: s['values'][request] for s in policies}})
    overhead = configuration['overhead']
    sensitivity = []
    for extra in range(overhead['minimum'], overhead['maximum'] + 1, overhead['step']):
        total = totals['scoped'] + extra
        margin = totals['curated'] - total
        percent = str((abs(Decimal(margin)) * 100 / Decimal(totals['curated'])).quantize(Decimal('.1'), rounding=ROUND_HALF_UP))
        relation = 'equal' if margin == 0 else 'lower' if margin > 0 else 'higher'
        sensitivity.append({'additional_input': extra, 'scoped_total': total, 'margin_vs_curated': margin, 'relation': relation, 'percent': percent})
    n = data['calls']
    triangular = n * (n - 1) // 2
    derivations = {}
    for policy in policies[:2]:
        initial = policy['values'][0]
        increment = policy['values'][1] - initial
        if policy['values'] != [initial + increment * i for i in range(n)]:
            raise ValueError('Append illustration requires an arithmetic sequence')
        derivations[policy['id']] = {'requests': n, 'initial': initial, 'increment': increment, 'retained_steps': triangular, 'total': n * initial + increment * triangular}
    return {**result, 'policies': policies, 'requests': rows, 'derivations': derivations,
            'sensitivity': sensitivity, 'break_even_additional_input': totals['curated'] - totals['scoped'],
            'overhead_samples': [row for row in sensitivity if row['additional_input'] in overhead['samples']],
            'exact_active_occupancy': 'UNKNOWN', 'information_sufficiency': 'untested'}
