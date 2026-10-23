#!/usr/bin/env python3
"""Original SVG charts from explicit illustrative inputs; no model telemetry."""
from pathlib import Path
import importlib.util,json
from build_capri_explainer import Art,INK,PAPER,PINK,GREEN,MUTED

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'showcase/capri/context-budget'


def main():
    spec=importlib.util.spec_from_file_location('worked_budget',OUT/'calculate.py')
    calc=importlib.util.module_from_spec(spec);spec.loader.exec_module(calc)
    inputs=json.loads((OUT/'scenario.json').read_text());results=calc.calculate(inputs)
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    art=Art();art.output=OUT
    totals=results['total_assumed_input_tokens']
    if inputs['calls']!=6:raise ValueError('This lesson requires six calls; edit the assumed budgets within that story')
    maximum=max(totals.values())
    growing_reduction=results['scoped_input_reduction_percent']['growing_history']
    curated_reduction=results['scoped_input_reduction_percent']['curated_single_session']
    growing_label=f"{abs(growing_reduction):.1f}% {'lower' if growing_reduction>=0 else 'higher'}"
    curated_label=f"{abs(curated_reduction):.1f}% {'lower' if curated_reduction>=0 else 'higher'}"
    rows=[('Growing conversation',totals['growing_history'],PAPER),('Curated single session',totals['curated_single_session'],PINK),('Scoped role contexts',totals['scoped_roles'],GREEN)]
    for mobile in [False,True]:
        w,h=(600,1020) if mobile else (1200,820)
        body=art.text('WORKED EXAMPLE',25 if mobile else 35,65,54 if mobile else 64,GREEN,'display')
        body+=art.lines(['Assumed input tokens / six requests','Not a measured CAPRI run.'],25 if mobile else 35,120,29 if mobile else 34)
        if mobile:
            for i,(label,total,color) in enumerate(rows):
                y=245+i*160
                body+=art.text(label,25,y,31)
                body+=f'<rect x="25" y="{y+20}" width="550" height="42" fill="#302a38"/>'
                body+=f'<rect x="25" y="{y+20}" width="{550*total/maximum}" height="42" fill="{color}"/>'
                body+=art.text(f'{total:,} input tokens',25,y+107,32,color)
            body+=art.lines([f'Same zero baseline; largest bar {maximum:,}.','All six calls and assumed handoffs included.'],25,725,27,MUTED)
            body+=art.lines([f'Scoped: {growing_label} vs growing;',f'{curated_label} vs curated, in this example.'],25,825,28,GREEN)
            body+=art.lines(['Input tokens are not bill totals.','Cache reuse can reverse the cost ordering.'],25,945,28,PAPER)
        else:
            for tick in [maximum*n/3 for n in range(4)]:
                x=380+640*tick/maximum
                body+=f'<path d="M{x} 220v360" stroke="#302a38" stroke-width="2"/>'
                body+=art.text('0' if tick==0 else f'{tick/1000:g}k',x-12,618,27,MUTED)
            for i,(label,total,color) in enumerate(rows):
                y=277+i*123
                body+=art.text(label,35,y+22,30)
                body+=f'<rect x="380" y="{y-18}" width="{640*total/maximum}" height="54" fill="{color}"/>'
                body+=art.text(f'{total:,}',1044,y+22,32,color)
            body+=art.text('Assumed input tokens, summed across six requests',380,660,28,MUTED)
            body+=art.lines([f'Scoped inputs: {growing_label} vs growing; {curated_label} vs curated, under these assumptions.','Input tokens are not bill totals. Cache reuse can reverse the cost ordering.'],35,735,29)
        art.save('budget-mobile' if mobile else 'budget',w,h,body,f'Worked example: assumed input tokens, not a measured CAPRI run. {totals["growing_history"]} growing, {totals["curated_single_session"]} curated single, {totals["scoped_roles"]} scoped roles. Input-only assumptions; cache can reverse cost ordering.')
    print(json.dumps({'totals':totals,'evidence_class':results['evidence_class']}))


if __name__=='__main__':main()
