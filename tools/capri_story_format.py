"""Compile the one frame contract into actual artboards and proportional layout CSS."""
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
    # Keep mathematical and scene controls outside the scaled source artboard.
    controls=''
    if 'class="story-controls"' in markup:
        controls=block(markup,'div','class="story-controls"');markup=markup.replace(controls,'')
    packets=''
    if name=='workflow':
        for detail in re.findall(r'<details\b.*?</details>',markup,re.S):packets+=detail;markup=markup.replace(detail,'')
        controls='<div class="workflow-packets">'+packets+'</div>'+controls
    inner='<div class="story-frame"><div class="story-artboard">'+(markup[markup.index('>')+1:markup.rfind('</section>')] if outer else markup)+'</div></div>'
    if outer:return markup[:markup.index('>')].replace('<section','<section data-lesson="'+name+'" data-family="'+('landscape' if name in formats['positions'] or name=='workflow' else 'portrait')+'"',1)+'>'+inner+controls+'</section>'
    return inner+controls

def format_css(f):
    css=['/* Generated from format.json. Artboard coordinates, never anisotropic scaling. */']
    for layout,d in f['families'].items():
        prefix='html.export.portrait ' if layout=='portrait' else 'html.export:not(.portrait) '
        # Runtime data-layout is selected from the same single breakpoint.
        css.append(f'.story-frame[data-layout="{layout}"]{{--frame-width:{d["width"]};--frame-height:{d["height"]};--inset:{d["inset"]}px;--heading:{d["heading"]}px;--body:{d["body"]}px;aspect-ratio:{d["width"]}/{d["height"]}}}')
    for name,layouts in f['positions'].items():
        for layout,items in layouts.items():
            for selector,(x,y,w,h) in items.items():
                css.append(f'[data-lesson="{name}"] .story-frame[data-layout="{layout}"] {selector}{{position:absolute!important;left:{x}px!important;top:{y}px!important;width:{w}px!important;height:{h}px!important;margin:0!important}}')
    p=f['portrait_plate']
    css.append(f'[data-family="portrait"] .cp-scene{{position:absolute!important;left:{p["stage_x"]}px;top:{p["stage_y"]}px;width:{p["stage_width"]}px;height:auto}}')
    for scene,(w,h) in f['source_aspects'].items():
        lesson={'hands':'handoff','cat':'checking','rain':'requirements','dots':'coordination'}.get(scene)
        if lesson:css.append(f'[data-lesson="{lesson}"] .cp-scene{{height:{p["stage_width"]*h/w}px!important}}')
    css.append(f'[data-family="portrait"] .cp-copy h3{{position:absolute;left:{p["stage_x"]}px;top:{p["heading_y"]}px;width:{p["stage_width"]}px;margin:0!important}}[data-family="portrait"] .cp-copy p{{position:absolute;left:{p["stage_x"]}px;top:{p["copy_y"]}px;width:{p["stage_width"]}px;margin:0!important}}')
    for layout,d in f['workflow'].items():
        sel=f'#handoff-comic-full-sprites .story-frame[data-layout="{layout}"]'
        dim=f['families'][layout];inset=dim['inset'];width=dim['width']-2*inset
        css.append(f'{sel} .hcf-intro{{position:absolute;left:{inset}px;top:{d["intro_y"]}px;width:{width}px;padding:0}}{sel} .hcf-grid{{position:absolute;left:{inset}px;top:{d["row_y"]}px;width:{width}px;height:{d["row_height"]}px;margin:0;gap:{dim["gutter"]}px}}{sel} .hcf-end{{position:absolute;left:{inset}px;top:{d["end_y"]}px;width:{width}px;margin:0;padding:0;font-size:24px}}{sel} .hcf-model{{height:{d["model_height"]}px}}')
        if layout=='portrait':css.append(f'{sel} .hcf-grid{{display:flex;flex-direction:column;gap:0}}{sel} .hcf-card{{display:grid;grid-template-columns:{d["model_width"]}px 1fr;grid-template-rows:auto 1fr;height:{d["row_height"]/3}px;gap:0 12px;padding:0}}{sel} .hcf-model{{grid-column:1;grid-row:1/3}}{sel} .hcf-card h3{{grid-column:2;font-size:28px!important;margin:8px 0 5px!important}}{sel} .hcf-copy{{grid-column:2;font-size:26px!important;line-height:1.4!important}}{sel} .hcf-intro h2{{font-size:34px!important}}{sel} .hcf-intro p{{font-size:26px!important;line-height:1.4!important}}')
    css.append('#handoff-comic-full-sprites .story-frame[data-layout="portrait"] .hcf-end{display:flex;flex-direction:column;align-items:flex-start;gap:2px;font-size:22px!important;line-height:1.3}#handoff-comic-full-sprites .story-frame[data-layout="portrait"] .hcf-end strong{margin:0;font-size:22px}#handoff-comic-full-sprites .story-frame[data-layout="portrait"] .hcf-end span{font-size:22px}')
    css.append(f'@media(max-width:{f["mobile_breakpoint_px"]}px){{main{{padding:16px}}.story-pair{{grid-template-columns:1fr!important}}.story-frame{{max-width:{f["families"]["portrait"]["width"]}px;margin-inline:auto}}}}')
    return '\n'.join(css)
