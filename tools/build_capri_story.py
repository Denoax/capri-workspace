#!/usr/bin/env python3
"""Compose V3 lessons around the existing source renderer; no new media sources."""
from pathlib import Path
import hashlib,html,json,re
from capri_context_budget import story_model
from build_capri_source_match import main as build_original
ROOT=Path(__file__).resolve().parents[1]
STORY=ROOT/'showcase/capri/story';BASE=ROOT/'showcase/capri/source-match';COMP=BASE/'companion'

def section(text, marker):
    match=re.search(r'<section\b[^>]*'+marker+r'[^>]*>',text)
    if not match:raise ValueError('Missing original section: '+marker)
    depth=1
    for tag in re.finditer(r'</?section\b[^>]*>',text[match.end():]):
        depth += -1 if tag[0].startswith('</') else 1
        if depth==0:return text[match.start():match.end()+tag.end()]
    raise ValueError('Unclosed source section')

def chart(model, portrait):
    width,height=(600,630) if portrait else (720,560)
    left,right,top,bottom=62,width-26,142,414 if portrait else 346
    xs=[round(left+(right-left)*i/5,3) for i in range(6)]
    ys=lambda value:round(bottom-(bottom-top)*value/55000,3)
    font=32 if portrait else 23;small=32 if portrait else 21
    pieces=[f'<svg class="story-chart {"portrait-chart" if portrait else "wide-chart"}" data-layout="{"portrait" if portrait else "wide"}" viewBox="0 0 {width} {height}" role="img" aria-label="Illustrative input tokens per request, with all three policies and totals. Not a CAPRI benchmark." xmlns="http://www.w3.org/2000/svg">',f'<text x="24" y="38" class="chart-title" font-size="{font+2}">Illustrative inputs</text>',f'<text x="24" y="73" font-size="{font}">— not a CAPRI benchmark</text>',f'<text x="24" y="112" font-size="{small}" class="chart-muted">Input / request · thousand tokens</text>']
    pieces.insert(1,'<style>.chart-grid{stroke:#3d3448;stroke-width:1}.chart-current{stroke:#f4f1ee;stroke-width:1;stroke-dasharray:4 6;opacity:.65}.chart-muted{fill:#c9c3d4}.chart-title{font-family:Manrope,sans-serif;font-weight:500}</style><rect width="100%" height="100%" fill="#100a19"/>')
    pieces[0]=pieces[0].replace(' viewBox=', ' fill="#f4f1ee" color="#f4f1ee" style="font-family:Inter,Arial,sans-serif" viewBox=')
    for value in range(0,51,10):
        y=ys(value*1000);pieces += [f'<path d="M{left},{y}H{right}" class="chart-grid"/>',f'<text x="{left-12}" y="{y+8}" text-anchor="end" font-size="{small}">{value}</text>']
    for i,x in enumerate(xs):pieces.append(f'<text x="{x}" y="{bottom+34}" text-anchor="middle" font-size="{small}">{i+1}</text>')
    pieces.append(f'<text x="{(left+right)/2}" y="{bottom+70}" text-anchor="middle" font-size="{small}">Request number</text>')
    points={};colors={'growing':'#ff438a','curated':'#c9c3d4','scoped':'#3be598'}
    pieces.append(f'<path data-current-rule="" d="M{xs[2]},{top}V{bottom}" class="chart-current"/>')
    for policy in model['policies']:
        name=policy['id'];points[name]=[[x,ys(v)] for x,v in zip(xs,policy['values'])]
        path='M'+'L'.join(f'{x},{y}' for x,y in points[name]);dash=' stroke-dasharray="9 7"' if name=='curated' else ''
        pieces.append(f'<path d="{path}" fill="none" stroke="{colors[name]}" stroke-width="3"{dash}/>')
        for x,y in points[name]:
            if name=='scoped':pieces.append(f'<path d="M{x},{y-6}l6,6 -6,6 -6,-6Z" fill="{colors[name]}"/>')
            elif name=='curated':pieces.append(f'<rect x="{x-5}" y="{y-5}" width="10" height="10" fill="{colors[name]}"/>')
            else:pieces.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{colors[name]}"/>')
        pieces.append(f'<circle data-current-dot="{name}" cx="{points[name][2][0]}" cy="{points[name][2][1]}" r="8" fill="#100a19" stroke="{colors[name]}" stroke-width="3"/>')
    start=bottom+110
    for i,policy in enumerate(model['policies']):
        y=start+i*36;pieces.append(f'<text x="24" y="{y}" font-size="{font}" fill="{colors[policy["id"]]}">{html.escape(policy["label"])} · {policy["total"]//1000}k total</text>')
    pieces.append('</svg>')
    return ''.join(pieces),{'x':xs,'points':points,'top':top,'bottom':bottom}

def replace_once(text, old, new):
    if text.count(old)!=1:raise ValueError('Unexpected source boundary: '+old[:80])
    return text.replace(old,new,1)

def main():
    config=json.loads((STORY/'story.json').read_text());source=(STORY/config['canonical_inputs']).resolve()
    model=story_model(json.loads(source.read_text()),config);STORY.mkdir(exist_ok=True)
    (STORY/'model-results.json').write_text(json.dumps(model,indent=2)+'\n')
    previous=(COMP/'index.html').read_bytes() if (COMP/'index.html').exists() else None
    try:
        build_original();original=(COMP/'index.html').read_text()
    finally:
        if previous is not None:(COMP/'index.html').write_bytes(previous)
    (COMP/'source-match.html').write_text(original)
    data_match=re.search(r'<script type="application/json" id="scene-data">(.*?)</script>',original,re.S);scene_data=json.loads(data_match[1])
    workflow=section(original,r'class="hcf-comic"')
    workflow=workflow.replace('Keep the decision moving.','From request to a reviewable candidate.').replace('Three focused contexts. A clear handoff between them.','A brief crosses ordered stages. One worker writes; you decide.')
    workflow=workflow.replace('<h3>Plan</h3>','<h3>Plan / Thinker</h3>').replace('<h3>Build</h3>','<h3>Build / Doer</h3>').replace('<h3>Review</h3>','<h3>Review / Reviewer</h3>')
    copies=iter(['Request + correction + source → scope and checks.','Brief + allowed files → patch, results and limits.','Request + candidate + evidence → findings.'])
    workflow=re.sub(r'<p class="hcf-copy">.*?</p>',lambda m:'<p class="hcf-copy">'+next(copies)+'</p>',workflow)
    workflow=workflow.replace('Findings, checks and limits return to you.','Findings → Thinker report → your decision.').replace('You decide.','One writer. Human decision.')
    native=re.findall(r'<section class="cs-panel".*?</section>',original,re.S);assert len(native)==2
    sharks=native[0].replace('<section class="cs-panel"','<section data-story-scene="sharks" class="cs-panel"',1)
    sharks=sharks.replace('Relevant source. Current correction.<br><code>blank → Untitled</code>','<strong>Request + latest correction</strong><br>Relevant source<br>Allowed files + checks<br>Originals retrievable')
    sharks=sharks.replace('The task stays legible while everything around it moves.','Select what the next decision needs. Keep the request and compatible rules together.')
    horizon=native[1].replace('<section class="cs-panel"','<section data-story-scene="horizon" class="cs-panel"',1)
    graphs={};svgs=[]
    for portrait in [False,True]:
        svg,points=chart(model,portrait);svgs.append(svg);graphs['portrait' if portrait else 'wide']=points
        (STORY/('input-'+('portrait' if portrait else 'wide')+'.svg')).write_text(svg+'\n')
    growing=model['derivations']['growing'];steps='+'.join(str(i) for i in range(model['calls']))
    derivation=f"{growing['requests']} × {growing['initial']//1000}k + {growing['increment']//1000}k × ({steps})"
    math='<div class="story-math">'+''.join(svgs)+'<p class="story-derivation">'+derivation+'<br><strong>= '+str(model['total_assumed_input_tokens']['growing']//1000)+'k assumed input</strong></p><p class="story-assumption">Equal work and quality untested.</p><div class="story-controls"><label for="story-request">Inspect request</label><select id="story-request">'+''.join(f'<option value="{i}">{i} of 6</option>' for i in range(1,model['calls']+1))+'</select><output id="story-values"></output></div></div>'
    horizon=horizon.replace('<div class="cs-caption"><h3>Don\'t lose the thread.</h3><p>Capri crosses a page that bends around the hole.</p></div>', '<div class="cs-caption"><h3>What each request carries.</h3><p>Focused input can avoid replaying discarded exploration. The coordination still has to earn its cost.</p></div>'+math)
    panels={}
    for name in ['hands','rain','dots','cat','stack']:
        canvas_at=original.index('data-scene="'+name+'"');start=original.rfind('<section',0,canvas_at);panels[name]=section(original[start:],r'class="cp-panel[^\"]*"')
    hands=panels['hands'].replace('The current correction reaches the next context.','Carry the correction with the compatible rules and checks.')
    hands=hands.replace('</section>','<div class="story-packet"><strong>label.py only · blank → Untitled</strong><p>Trim outer whitespace. Preserve case and internal spaces. Non-strings raise TypeError.</p><p><code>"   " → "Untitled"</code><br><code>"  MiX  Case  " → "MiX  Case"</code><br><code>None → TypeError</code></p><p>Authored fixture, not an observed model result.</p></div></section>')
    rain=panels['rain'].replace('Current correction.<br>Source and checks.','label.py only<br>Original rules + source<br>Expected checks')
    rain=rain.replace('Keep the requirement.','Keep requirements retrievable.').replace('Choose the relevant working input. Keep originals retrievable.','A shorter brief can omit a rule. Review rereads the authoritative request and correction.')
    dots=panels['dots'];dots=re.sub(r'<div class="cp-card-copy">.*?</div>','<div class="cp-card-copy"><strong>60k + H</strong><br><span data-budget-total>90k input</span><br><span data-budget-relation>H = 30k</span></div>',dots,flags=re.S)
    dots=dots.replace('Keep the work connected.','Coordination has an input budget.').replace('A compact interlude between explanations.','H is additional input beyond the instructions and handoffs already budgeted. At H = 30k, the raw-input advantage disappears.')
    dots=dots.replace('</section>','<div class="story-controls"><label for="story-overhead">Additional input H</label><input id="story-overhead" type="range" min="0" max="60000" step="1000" value="30000"><output id="story-budget"></output></div></section>')
    cat=panels['cat'].replace('Capri takes over.','Check the candidate against the request.').replace('Monochrome, contact, then colour.','A fresh checking context compares request, correction, patch and evidence. Shared model blind spots remain; the human decides.')
    stack=panels['stack'].replace('Scope, correction and evidence arrive as one handoff.','Scope, current correction and evidence stay together. Continue with the real offline setup.')
    native_root='<div id="capri-source-scenes"><div class="cs-grid story-contexts" data-lesson="contexts">'+horizon+sharks+'</div></div>'
    plates='<div id="capri-reference-composites"><div data-lesson="handoff">'+hands+'</div><div class="story-retained" data-lesson="retained">'+rain+dots+'</div><div data-lesson="checking">'+cat+'</div><div data-lesson="closing">'+stack+'</div></div>'
    intro='<header class="story-intro native-text"><h1>CAPRI</h1><p>Planning, coding and review get their own Codex sessions. Explicit handoffs carry current decisions, relevant files, scope and checks. One worker edits; a separate reviewer checks the candidate; you decide what ships.</p><nav><a href="#handoff-comic-full-sprites">Workflow</a><a href="#scene-horizon">Inputs</a><a href="#scene-hands">Correction</a><a href="#scene-dots">Coordination</a><a href="#scene-cat">Checking</a><a href="../../../../docs/QUICKSTART.md">Setup</a></nav><p><a href="../../../../README.md">Repository README</a> · <a href="../../../../docs/README_STATIC.md">Complete static edition</a> · <a href="../../../../docs/VISUAL_STORY.md">Sources and build record</a></p></header>'
    workflow='<div id="handoff-comic-full-sprites" data-lesson="workflow">'+workflow+'</div>'
    body=intro+workflow+native_root+plates+'<footer class="native-text"><p>Illustrative inputs, authored character acting and credited source-reference scenes. Native qualification remains experimental/BLOCKED; no model result is depicted.</p><p><a href="../../../../docs/BENCHMARK_PROTOCOL.md">Benchmark protocol</a> · <a href="../../../../docs/SOURCE_MATCH.md">Original sources and rights</a> · <a href="source-match.html">Preserved source-match companion</a></p></footer>'
    page=re.sub(r'<main>.*?</main>',lambda m:'<main>'+body+'</main>',original,count=1,flags=re.S)
    old_js=(COMP/'scenes.js').read_text();adapted=old_js.replace("nativeRoot.querySelector('.cs-panel')","nativeRoot.querySelector('[data-story-scene=\"sharks\"]')").replace("nativeRoot.querySelectorAll('.cs-panel')[1]","nativeRoot.querySelector('[data-story-scene=\"horizon\"]')")
    adapted=adapted.replace("this.controls.querySelector('input').value =", "window.capriStory?.paint(this, t);\n      this.controls.querySelector('input').value =")
    adapted=replace_once(adapted, "this.status.textContent = 'Playback needs a user Play action: ' + error.message;", "this.status.replaceChildren(document.createTextNode(this.video?.error ? 'Reference media unavailable. ' : 'Playback needs a user Play action. ')); const link=document.createElement('a'); link.href='../../../../docs/README_STATIC.md'; link.textContent='Open complete static edition'; this.status.append(link);")
    adapted=replace_once(adapted, "this.status.textContent = 'WebGL 2 unavailable: source still fallback shown; native execution unverified.';", "this.status.textContent = 'WebGL 2 unavailable: source still fallback shown; native execution unverified.'; this.controls.querySelector('button:last-child').disabled=true;")
    adapted=adapted.replace("actor.draw(ctx, 'plan', time, x, y, .18,", "actor.draw(ctx, 'plan', time, x, y, .26,")
    adapted=adapted.replace("actor.draw(ctx, 'build', time, 70 - 75", "actor.draw(ctx, 'review', time, 70 - 75")
    adapted=adapted.replace('  function tick(now) { for (const scene',"  window.dispatchEvent(new Event('capri:ready'));\n  function tick(now) { for (const scene")
    story_data={'model':model,'config':config,'graphs':graphs}
    ui=(STORY/'story-ui.js').read_text();style='\n'.join(re.findall(r'<style>(.*?)</style>',original,re.S)[1:])+'\n'+(STORY/'story.css').read_text();(STORY/'scenes.js').write_text(adapted)
    page=replace_once(page,'<script>'+old_js+'</script>','<script type="application/json" id="story-data">'+json.dumps(story_data,separators=(',',':'))+'</script><script>'+ui+'</script><script>'+adapted+'</script>')
    page=page.replace('</style>','\n'+style+'</style>',1);page=page.replace('CAPRI · source-match companion','CAPRI · visual story')
    (COMP/'index.html').write_text(page)
    (STORY/'SOURCE_RECORD.json').write_text(json.dumps({'base':'f502e6448223812edcceedaa48ee9d89e7127343','handoff_sha256':'74b7cafdc862e3316bda5549003416333d48005c28c85ac8889acf8e72c0190a','method':'V3 authored composition/data overlay around original scenes, native factories, footage and30part rig. No new visual generation. V2 implementation excluded.','lessons':config['lessons'],'canonical_input':str(source.relative_to(ROOT)),'canonical_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'legacy_companion':'../source-match/companion/source-match.html','rights':'Original notices, OFL/MIT and unresolved media/character/shark rights unchanged; private review only.'},indent=2)+'\n')
    print('V3 story composed; original renderer and all source assets preserved')
if __name__=='__main__':main()
