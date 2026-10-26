"""Shared static SVG plate geometry for the raster compositor and exported masters."""
from pathlib import Path
import json,subprocess

def build(media):
    scene=Path(media)/'hero-scene';cfg=json.loads((scene/'scene.json').read_text());frame=cfg['frame'];seam=cfg['seam'];x1,y1,x2,y2=frame['gradient']
    stops=''.join(f'<stop offset="{i/(len(frame["colors"])-1)}" stop-color="{color}"/>' for i,color in enumerate(frame['colors']))
    defs=f'<defs><linearGradient id="plate-gradient" gradientUnits="userSpaceOnUse" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{stops}</linearGradient></defs>'
    top=frame['y'];bottom=top+frame['height'];start=seam['centerline_x0']+seam['slope']*top;end=seam['centerline_x0']+seam['slope']*bottom
    line=f'M{start} {top}L{end} {bottom}'
    def rail(shape,width,support):return f'<{shape} fill="none" stroke="#100a19" stroke-width="{support}" opacity="{frame["support_opacity"]}"/>' + f'<{shape} fill="none" stroke="url(#plate-gradient)" stroke-width="{width}"/>'
    path=f'path d="{line}" stroke-linecap="butt"';rect=f'rect x="{frame["x"]}" y="{top}" width="{frame["width"]}" height="{frame["height"]}" stroke-linejoin="miter"'
    body=defs+'<g id="internal-rail">'+rail(path,seam['rail_width'],seam['support_width'])+'</g><g id="outer-frame">'+rail(rect,frame['stroke_width'],frame['support_width'])+'</g>'
    (scene/'frame.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="480" viewBox="0 0 1400 480" role="img" aria-label="Steady outer frame and diagonal rail">'+body+'</svg>\n')
    subprocess.run(['rsvg-convert',str(scene/'frame.svg'),'-o',str(scene/'frame.png')],check=True)
if __name__=='__main__':build(Path(__file__).resolve().parents[1]/'showcase/capri')
