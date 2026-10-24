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
