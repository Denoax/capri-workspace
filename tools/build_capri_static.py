#!/usr/bin/env python3
"""Keep the static README's semantic text and relative links tied to the root."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def main():
 text=(ROOT/'README.md').read_text().replace('showcase/capri/hero.gif','showcase/capri/hero.png').replace('scene/portrait.gif','scene/portrait-static.svg').replace('scene/wide.gif','scene/wide-static.svg')
 text=re.sub(r'((?:src|srcset|href)="|\]\()((?!https?:|#)[^"\s)]+)',lambda m:m[1]+'../'+m[2],text)
 (ROOT/'docs/README_STATIC.md').write_text('<!-- Generated from README.md by tools/build_capri_static.py. -->\n'+text)
if __name__=='__main__':main()
