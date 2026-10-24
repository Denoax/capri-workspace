"""Compile compact content roles into flow-based, uniformly scaled artboards."""
import re

def block(text,tag,marker):
    match=re.search(r'<'+tag+r'\b[^>]*'+marker+r'[^>]*>',text)
    if not match:raise ValueError('Missing frame content: '+marker)
    depth=1
    for item in re.finditer(r'</?'+tag+r'\b[^>]*>',text[match.end():]):
        depth += -1 if item[0].startswith('</') else 1
        if not depth:return text[match.start():match.end()+item.end()]
    raise ValueError('Unclosed frame content: '+marker)

def frame(markup,name,formats,outer=True):
    controls=''
    if 'class="story-controls"' in markup:
        controls=block(markup,'div','class="story-controls"');markup=markup.replace(controls,'')
    if name=='workflow':
        packets=''
        for detail in re.findall(r'<details\b.*?</details>',markup,re.S):packets+=detail;markup=markup.replace(detail,'')
        controls='<div class="workflow-packets">'+packets+'</div>'+controls
        markup=markup.replace('<p></p>','').replace('Thinker report → your decision.','One writer. You decide.')
        content=markup
    else:
        is_native=name in ['brief','horizon'];stage=block(markup,'div','class="cs-stage' if is_native else 'class="cp-scene')
        caption=block(markup,'div','class="cs-caption"' if is_native else 'class="cp-copy"')
        title=re.search(r'<h3>.*?</h3>',caption,re.S)[0];label=re.search(r'<p>.*?</p>',caption,re.S)[0]
        for detail in re.findall(r'<details\b.*?</details>',caption,re.S):controls+=detail
        stage=stage.replace('<h3></h3>','')
        content='<header class="story-title">'+title+'</header><div class="story-visual">'+stage+'</div><div class="story-label">'+label+'</div>'
    art='<div class="story-frame"><div class="story-artboard">'+content+'</div></div>'
    if not outer:return art+controls
    family='support' if name=='closing' else 'illustration'
    start=markup[:markup.index('>')].replace('<section',f'<section data-lesson="{name}" data-family="{family}"',1)
    return start+'>'+art+controls+'</section>'

def format_css(f):
    css=['/* Geometry comes from format.json. Flow and fixed uniform scale, no per-panel Y slots. */']
    for layout,family in f['layouts'].items():
        d=f['families'][family];stage=d.get('stage_width',d['width']);margin=(d['width']-2*d['inset']-stage)/2
        css.append(f'.story-frame[data-layout="{layout}"]{{--frame-width:{d["width"]};--frame-height:{d["height"]};--inset:{d["inset"]}px;--gap:{d["gap"]}px;--heading:{d["heading"]}px;--body:{d["body"]}px;--stage-width:{stage}px;--small-stage:{d.get("small_stage_width",stage)}px;--stage-margin:{margin}px;--model-width:{d.get("workflow_model_width",220)}px;--model-height:{d.get("workflow_model_height",160)}px;aspect-ratio:{d["width"]}/{d["height"]}}}')
    for name,(w,h) in f['source_aspects'].items():
        lesson={'hands':'handoff','cat':'checking','rain':'requirements','dots':'coordination','stack':'closing'}.get(name)
        if lesson:css.append(f'[data-lesson="{lesson}"] .cp-scene{{aspect-ratio:{w}/{h}!important}}')
    for name,(w,h) in f['native_world'].items():css.append(f'[data-story-scene="{name}"] .cs-stage{{aspect-ratio:{w}/{h}!important}}')
    return '\n'.join(css)
