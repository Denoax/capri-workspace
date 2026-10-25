"""Shared script-free lockup using the supplied OFL font files."""
from pathlib import Path
import base64
ROOT=Path(__file__).resolve().parents[1];STORY=ROOT/'showcase/capri/story'
def identity_markup(formats,prefix='showcase/capri/story/'):
 f=formats['identity'];return f'<picture><source media="(max-width:{formats["responsive"]["breakpoint_px"]}px)" srcset="{prefix}identity-mobile.svg" width="{f["mobile_cap"]}"><img src="{prefix}identity.svg" alt="{f["display_name"]}" width="{f["wide_cap"]}"></picture>'
def build_identity(formats):
 f=formats['identity'];fonts=[]
 for family in ['Manrope','Inter']:
  path=ROOT/'showcase/capri/source-match/source/assets/fonts'/family/(family+'-Variable.ttf');encoded=base64.b64encode(path.read_bytes()).decode();fonts.append("@font-face{font-family:'"+family+"';src:url(data:font/ttf;base64,"+encoded+") format('truetype');font-weight:100 900}")
 for mobile,filename in [(False,'identity.svg'),(True,'identity-mobile.svg')]:
  w,h=f['mobile' if mobile else 'wide'];pieces=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{f["display_name"]}"><style>'+''.join(fonts)+'</style>',f'<rect width="{w}" height="{h}" fill="{f["ink"]}"/>']
  if mobile:pieces += [f'<text x="{w/2}" y="30" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="500" font-size="28" fill="{f["pink"]}">CAPRI</text>',f'<text x="{w/2}" y="63" text-anchor="middle" font-family="Inter,sans-serif" font-size="22" fill="{f["green"]}">Agentic Loop Prompting</text>']
  else:pieces += [f'<text x="219" y="35" font-family="Manrope,sans-serif" font-weight="500" font-size="32" fill="{f["pink"]}">CAPRI</text>',f'<text x="335" y="34" font-family="Inter,sans-serif" font-size="26" fill="{f["green"]}">Agentic Loop Prompting</text>']
  (STORY/filename).write_text(''.join(pieces)+'</svg>\n')
