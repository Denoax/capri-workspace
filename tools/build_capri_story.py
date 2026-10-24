#!/usr/bin/env python3
"""Compose V5 compact roles around the existing source renderer; no new media sources."""
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

def chart(model, portrait=True):
    width,height=480,540;left,right,top,bottom=52,450,130,334
    xs=[round(left+(right-left)*i/5,3) for i in range(6)]
    ys=lambda v:round(bottom-(bottom-top)*v/55000,3)
    pieces=['<svg class="story-chart portrait-chart" data-layout="portrait" viewBox="0 0 480 540" fill="#f4f1ee" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Illustrative inputs, not a CAPRI benchmark. Three assumed input policies across six requests, in thousand tokens." style="font-family:Inter,sans-serif">','<rect width="480" height="540" fill="#100a19"/>','<text x="24" y="42" font-size="34" font-family="Manrope,sans-serif" font-weight="500">Illustrative inputs</text>','<text x="24" y="76" font-size="25">Not a CAPRI benchmark</text>','<text x="24" y="110" font-size="24" fill="#c9c3d4">Input / request · thousand tokens</text>']
    for v in range(0,51,10):
        y=ys(v*1000);pieces.extend([f'<path d="M{left},{y}H{right}" stroke="#3d3448"/>',f'<text x="{left-10}" y="{y+8}" text-anchor="end" font-size="25">{v}</text>'])
    for i,x in enumerate(xs):pieces.append(f'<text x="{x}" y="370" text-anchor="middle" font-size="25">{i+1}</text>')
    pieces+=['<text x="250" y="405" text-anchor="middle" font-size="24">Request number</text>',f'<path data-current-rule="" d="M{xs[0]},{top}V{bottom}" stroke="#f4f1ee" stroke-dasharray="4 6" opacity=".65"/>']
    points={};colors={'growing':'#ff438a','curated':'#c9c3d4','scoped':'#3be598'}
    for i,policy in enumerate(model['policies']):
        name=policy['id'];points[name]=[[x,ys(v)] for x,v in zip(xs,policy['values'])];path='M'+'L'.join(f'{x},{y}' for x,y in points[name]);dash=' stroke-dasharray="9 7"' if name=='curated' else ''
        pieces.append(f'<path d="{path}" fill="none" stroke="{colors[name]}" stroke-width="3"{dash}/>')
        for x,y in points[name]:
            if name=='scoped':pieces.append(f'<path d="M{x},{y-5}l5,5 -5,5 -5,-5Z" fill="{colors[name]}"/>')
            elif name=='curated':pieces.append(f'<rect x="{x-5}" y="{y-5}" width="10" height="10" fill="{colors[name]}"/>')
            else:pieces.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{colors[name]}"/>')
        pieces.append(f'<circle data-current-dot="{name}" cx="{points[name][0][0]}" cy="{points[name][0][1]}" r="8" fill="#100a19" stroke="{colors[name]}" stroke-width="3"/>')
        pieces.append(f'<text x="24" y="{446+i*34}" font-size="26" fill="{colors[name]}">{html.escape(policy["label"])} · {policy["total"]//1000}k total</text>')
    pieces.append('</svg>');return ''.join(pieces),{'x':xs,'points':points,'top':top,'bottom':bottom}

def replace_once(text, old, new):
    if text.count(old)!=1:raise ValueError('Unexpected source boundary: '+old[:80])
    return text.replace(old,new,1)

def main():
    config=json.loads((STORY/'story.json').read_text());formats=json.loads((STORY/config['format']).read_text());source=(STORY/config['canonical_inputs']).resolve()
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
    svg,points=chart(model);graphs={'portrait':points};(STORY/'input-portrait.svg').write_text(svg+'\n')
    math='<section data-lesson="graph" data-family="graph" id="story-graph"><div class="story-frame"><div class="story-artboard"><div class="story-math">'+svg+'</div></div></div><div class="story-controls"><label for="story-request">Inspect request</label><select id="story-request">'+''.join(f'<option value="{i}">{i} of 6</option>' for i in range(1,model['calls']+1))+'</select><output id="story-values"></output></div></section>'
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
    from capri_story_format import frame, format_css
    workflow=workflow.replace('From request to a reviewable candidate.','One ordered loop.').replace('A brief crosses ordered stages. One worker writes; you decide.','')
    for title,short in [('Plan / Thinker','Plan'),('Build / Doer','Build'),('Review / Reviewer','Review')]:workflow=workflow.replace('<h3>'+title+'</h3>','<h3>'+short+'</h3>')
    copies=iter(['Scope + checks','Patch + limits','Findings'])
    workflow=re.sub(r'<p class="hcf-copy">.*?</p>',lambda m:'<p class="hcf-copy">'+next(copies)+'</p>',workflow)
    workflow=re.sub(r'<div class="hcf-end">.*?</div>','<div class="hcf-end">Thinker report → your decision.</div>',workflow,flags=re.S)
    sharks=sharks.replace('A focused context.','Keep the brief.').replace('Keep the brief in sight.','').replace('<strong>Request + latest correction</strong><br>Relevant source<br>Allowed files + checks<br>Originals retrievable','Request + correction<br>Relevant source<br>Scope + checks<br>Retrievable originals')
    sharks=re.sub(r'<div class="cs-caption"><h3>.*?</h3><p>.*?</p>', '<div class="cs-caption"><h3>Keep the brief.</h3><p>Originals stay retrievable.</p>',sharks,flags=re.S)
    horizon=horizon.replace("Don't lose the thread.",'Choose the input.').replace('Capri crosses a page that bends around the hole.','Enough context for the next decision.')
    hands=re.sub(r'<div class="cp-copy">.*?</div>','<div class="cp-copy"><h3>Carry the correction.</h3><p>Authored fixture A</p></div>',hands,flags=re.S)
    hands=re.sub(r'<div class="story-packet">.*?</div>','',hands,flags=re.S)
    cat=re.sub(r'<div class="cp-copy">.*?</div>','<div class="cp-copy"><h3>Check the candidate.</h3><p>Request + patch + evidence</p></div>',cat,flags=re.S)
    rain=re.sub(r'<div class="cp-copy">.*?</div>','<div class="cp-copy"><h3>Keep the source.</h3><p>Rules, correction and checks</p></div>',rain,flags=re.S)
    dots=re.sub(r'<div class="cp-copy">.*?</div>','<div class="cp-copy"><h3>Count coordination.</h3><p>Additional input beyond the brief</p></div>',dots,flags=re.S)
    stack=panels['stack'].replace('Bring the brief together.','Keep the evidence.').replace('Scope, correction and evidence arrive as one handoff.','Continue with offline checks.')
    workflow='<div id="handoff-comic-full-sprites" data-lesson="workflow" data-family="illustration">'+frame(workflow,'workflow',formats,outer=False)+'</div>'
    pairs='<div class="story-pair">'+workflow+frame(sharks,'brief',formats)+'</div>'+math+'<div class="story-pair">'+frame(horizon,'horizon',formats)+frame(dots,'coordination',formats)+'</div><div class="story-pair">'+frame(hands,'handoff',formats)+frame(cat,'checking',formats)+'</div><div class="story-pair story-support">'+frame(rain,'requirements',formats)+frame(stack,'closing',formats)+'</div>'
    lessons='<div id="capri-source-scenes"><div id="capri-reference-composites">'+pairs+'</div></div>'
    intro='<header class="story-intro native-text"><h1>CAPRI</h1><p>Planning, coding and review get their own Codex sessions. Explicit handoffs carry current decisions, relevant files, scope and checks. One worker edits; a separate reviewer checks the candidate; you decide what ships.</p><nav><a href="#handoff-comic-full-sprites">Workflow</a><a href="#scene-horizon">Inputs</a><a href="#scene-hands">Correction</a><a href="#scene-dots">Coordination</a><a href="#scene-cat">Checking</a><a href="../../../../docs/QUICKSTART.md">Setup</a></nav><p><a href="../../../../README.md">Repository README</a> · <a href="../../../../docs/README_STATIC.md">Complete static edition</a> · <a href="../../../../docs/VISUAL_STORY.md">Sources and build record</a></p></header>'
    body=intro+lessons+'<footer class="native-text"><p>Illustrative inputs and credited source-reference art; no model result is depicted. <a href="../../../../docs/STATUS.md">Native qualification remains pending.</a> <a href="source-match.html">Preserved source player</a></p></footer>'
    page=re.sub(r'<main>.*?</main>',lambda m:'<main>'+body+'</main>',original,count=1,flags=re.S)
    old_js=(COMP/'scenes.js').read_text();adapted=old_js.replace("nativeRoot.querySelector('.cs-panel')","nativeRoot.querySelector('[data-story-scene=\"sharks\"]')").replace("nativeRoot.querySelectorAll('.cs-panel')[1]","nativeRoot.querySelector('[data-story-scene=\"horizon\"]')")
    adapted=adapted.replace("this.controls.querySelector('input').value =", "window.capriStory?.paint(this, t);\n      this.controls.querySelector('input').value =")
    adapted=replace_once(adapted, "this.status.textContent = 'Playback needs a user Play action: ' + error.message;", "this.status.replaceChildren(document.createTextNode(this.video?.error ? 'Reference media unavailable. ' : 'Playback needs a user Play action. ')); const link=document.createElement('a'); link.href='../../../../docs/README_STATIC.md'; link.textContent='Open complete static edition'; this.status.append(link);")
    adapted=replace_once(adapted, "this.status.textContent = 'WebGL 2 unavailable: source still fallback shown; native execution unverified.';", "this.status.textContent = 'WebGL 2 unavailable: source still fallback shown; native execution unverified.'; this.controls.querySelector('button:last-child').disabled=true;")
    adapted=adapted.replace("actor.draw(ctx, 'plan', time, x, y, .18,", "actor.draw(ctx, 'plan', time, x, y, .26,")
    adapted=adapted.replace("actor.draw(ctx, 'build', time, 70 - 75", "actor.draw(ctx, 'review', time, 70 - 75")
    adapted=adapted.replace('  function tick(now) { for (const scene',"  window.dispatchEvent(new Event('capri:ready'));\n  function tick(now) { for (const scene")
    adapted=adapted.replace('x - packet.offsetWidth / 2', 'x / (this.element.querySelector(\'.story-artboard\').getBoundingClientRect().width / this.element.querySelector(\'.story-artboard\').offsetWidth) - packet.offsetWidth / 2').replace('y - packet.offsetHeight / 2', 'y / (this.element.querySelector(\'.story-artboard\').getBoundingClientRect().height / this.element.querySelector(\'.story-artboard\').offsetHeight) - packet.offsetHeight / 2')
    adapted=adapted.replace("details = card.querySelector('details')", "details = this.element.querySelector('#hcf-' + card.dataset.card + '-brief')")
    adapted=adapted.replace("if (!['sharks', 'horizon'].includes(exportName)) nativeRoot.hidden = true;",'').replace("if (!definitions[exportName].plate) platesRoot.hidden = true;",'')
    adapted=adapted.replace("w = horizon ? 960 : 900, h = horizon ? 600 : 620", "w = horizon ? data.storyFormats.native_world.horizon[0] : data.storyFormats.native_world.sharks[0], h = horizon ? data.storyFormats.native_world.horizon[1] : data.storyFormats.native_world.sharks[1]")
    adapted=adapted.replace("ctx.globalAlpha = exportName ? entry : 1;","ctx.globalAlpha = 1;")
    adapted=adapted.replace("actor.draw(ctx, pose, sample, 120, 64, .135)","actor.draw(ctx, pose, sample, data.storyFormats.actor_placement.workflow.x, data.storyFormats.actor_placement.workflow.y, data.storyFormats.actor_placement.workflow.scale)")
    adapted=adapted.replace("const phase = time / this.duration, entry = smooth(phase / .12) * (1 - smooth((phase - .88) / .12));","const phase = time / this.duration;")
    adapted=adapted.replace("const q = smooth(phase < .5 ? phase * 2 : (1 - phase) * 2), x = 760 - 400 * q, y = 245 + 135 * Math.sin(Math.PI * q);", "const p = data.storyFormats.actor_placement.horizon, q = smooth(phase < .5 ? phase * 2 : (1 - phase) * 2), x = p.x - p.x_travel * q, y = p.y + p.y_travel * Math.sin(Math.PI * q);")
    adapted=adapted.replace("actor.draw(ctx, 'plan', time, x, y, .26,", "actor.draw(ctx, 'plan', time, x, y, data.storyFormats.actor_placement.horizon.scale,")
    adapted=adapted.replace("actor.draw(ctx, 'plan', time * 6400 / this.duration, 725, 390, .19)", "actor.draw(ctx, 'plan', time * 6400 / this.duration, data.storyFormats.actor_placement.sharks.x, data.storyFormats.actor_placement.sharks.y, data.storyFormats.actor_placement.sharks.scale)")
    adapted=adapted.replace("actor.draw(ctx, 'build', time * 6400 / this.duration, 145, 224, .077)", "actor.draw(ctx, 'build', time * 6400 / this.duration, data.storyFormats.actor_placement.hands.x, data.storyFormats.actor_placement.hands.y, data.storyFormats.actor_placement.hands.scale)")
    adapted=adapted.replace("actor.draw(ctx, 'review', time, 70 - 75 * (1 - arrival), 222, .085,", "actor.draw(ctx, 'review', time, data.storyFormats.actor_placement.cat.x - 25 * (1 - arrival), data.storyFormats.actor_placement.cat.y, data.storyFormats.actor_placement.cat.scale,")
    adapted=adapted.replace('z-index:4','z-index:1')
    adapted=adapted.replace("data.rig = window.CAPRI_RIG;", "data.rig = window.CAPRI_RIG; data.storyFormats = JSON.parse(document.getElementById('story-data').textContent).formats;")
    story_data={'model':model,'config':config,'graphs':graphs,'formats':formats}
    ui=(STORY/'story-ui.js').read_text();style='\n'.join(re.findall(r'<style>(.*?)</style>',original,re.S)[1:])+'\n'+(STORY/'story.css').read_text()+'\n'+format_css(formats);(STORY/'scenes.js').write_text('\n'.join(line.rstrip() for line in adapted.splitlines())+'\n')
    page=replace_once(page,'<script>'+old_js+'</script>','<script type="application/json" id="story-data">'+json.dumps(story_data,separators=(',',':'))+'</script><script>'+ui+'</script><script>'+adapted+'</script>')
    page=re.sub(r'<style>(.*?)</style>',lambda m:'<style>'+re.sub(r'\.export[^{}]*\{[^{}]*\}','',m[1])+'</style>',page,count=1,flags=re.S)
    page=page.replace('</style>','\n'+style+'</style>',1);page=page.replace('CAPRI · source-match companion','CAPRI · visual story')
    (COMP/'index.html').write_text('\n'.join(line.rstrip() for line in page.splitlines())+'\n')
    (STORY/'SOURCE_RECORD.json').write_text(json.dumps({'base':'18fecd7b51c8a2a6088a8a2ef2aa7cb4a0ba33ee','handoff_sha256':'fb7eda9ad071ec3df0136320cf01d09a7f02f12a59c0fc70641b2f1dc2a3490b','method':'V5 compact content roles and isolated graph selection around the V3 composition/data overlay around original scenes, native factories, footage and30part rig. No new visual generation. V2 implementation excluded.','lessons':config['lessons'],'root_selection':{name:{'layout':lesson['root_layout'],'role':formats['layouts'][lesson['root_layout']],'display_width':formats['families'][formats['layouts'][lesson['root_layout']]]['display_width']} for name,lesson in config['lessons'].items()},'accent':{'file':'accent.svg','method':'Independent geometric CAPRI rule/interruption; no third-party art copied.'},'format_file':'format.json','format_sha256':hashlib.sha256((STORY/'format.json').read_bytes()).hexdigest(),'format_reference':formats['references'],'canonical_input':str(source.relative_to(ROOT)),'canonical_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'legacy_companion':'../source-match/companion/source-match.html','rights':'Original notices, OFL/MIT and unresolved media/character/shark rights unchanged; private review only.'},indent=2)+'\n')
    print('V5 story composed; original renderer and all source assets preserved')
if __name__=='__main__':main()
