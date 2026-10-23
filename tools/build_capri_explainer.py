#!/usr/bin/env python3
"""Build the source-derived CAPRI lesson. Offline, media-only, no runtime writes."""
from pathlib import Path
from io import BytesIO
import base64
import hashlib
import html
import json
import subprocess
from PIL import Image
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "showcase/capri"
OUT = MEDIA / "explainer"
INK, PAPER, PINK, GREEN, MUTED = "#100a19", "#f4f1ee", "#ff1265", "#28fb86", "#bcb7c6"
POSES = [(1, 97), (14, 0), (12, 5)]
BUBBLES = [
    ["Plan here.", "Name the task, sources", "and acceptance checks."],
    ["Build here.", "Carry the correction", "with the handoff."],
    ["Review with fresh eyes.", "Check the request, patch", "and evidence together."],
    ["You decide what ships.", "The report brings findings,", "checks and limits back."],
]


class Art:
    def __init__(self):
        self.fonts = {}
        for name, filename in [("body", "Barlow-Regular.ttf"), ("display", "BarlowCondensed-ExtraBoldItalic.ttf")]:
            font = TTFont(MEDIA / "fonts" / filename)
            self.fonts[name] = (font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm)
        self.poses = []
        for source, frame in POSES:
            with Image.open(MEDIA / "sources" / f"capri-{source}.gif") as im:
                im.seek(frame)
                stream = BytesIO()
                im.convert("RGB").save(stream, "PNG", optimize=True)
                self.poses.append(base64.b64encode(stream.getvalue()).decode())

    def text(self, text, x, y, size=30, color=PAPER, face="body"):
        glyphs, cmap, units = self.fonts[face]
        offset, paths = 0, []
        for char in text:
            glyph = glyphs[cmap[ord(char)]]
            pen = SVGPathPen(glyphs)
            glyph.draw(pen)
            paths.append(f'<path transform="translate({offset},0)" d="{pen.getCommands()}"/>')
            offset += glyph.width
        return f'<g fill="{color}" transform="translate({x},{y}) scale({size / units},-{size / units})">' + "".join(paths) + "</g>"

    def lines(self, lines, x, y, size=30, color=PAPER, face="body", leading=1.24):
        return "".join(self.text(line, x, y + n * size * leading, size, color, face) for n, line in enumerate(lines))

    def pose(self, index, x, y, w, h):
        # Whole source box, no mirrored marks, inferred anatomy or synthetic frames.
        return f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{self.poses[index]}"/>'

    def bubble(self, lines, x, y, w, h, size=30, tail="top"):
        tip = f'M{x+35} {y}l-16 -22 55 22' if tail == "top" else f'M{x} {y+50}l-22 18 22 18'
        return (f'<path d="{tip}" fill="{PAPER}"/>'
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{PAPER}"/>'
                + self.lines(lines, x+22, y+39, size, INK))

    @staticmethod
    def rule(x, y, w, color=PAPER):
        return f'<path d="M{x} {y}h{w}" stroke="{color}" stroke-width="2"/>'

    def save(self, name, w, h, body, title):
        svg = OUT / f"{name}.svg"
        svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{html.escape(title)}</title><rect width="{w}" height="{h}" fill="{INK}"/>{body}</svg>\n')
        subprocess.run(["rsvg-convert", str(svg), "-o", str(OUT / f"{name}.png")], check=True)


def context(art, mobile):
    if mobile:
        w, h = 600, 1100
        body = art.pose(0, 20, 12, 210, 240)
        body += art.bubble(["One task.", "Three focused", "conversations."], 238, 38, 342, 173, 32, "left")
        body += art.text("WHAT EACH ROLE CAN WORK WITH", 25, 299, 40, GREEN, "display")
        body += art.text("One growing conversation", 25, 354, 32)
        body += art.rule(25, 374, 550, PINK)
        body += art.lines(["Request + corrections + sources", "+ exploration + logs + failed attempts"], 25, 416, 29)
        body += art.text("Select by purpose", 25, 530, 52, GREEN, "display")
        for y, role, content in [(600,"THINKER",["Task, sources, scope, checks"]), (733,"DOER",["Scoped change + latest correction"]), (866,"REVIEWER",["Request, candidate, evidence"])]:
            body += art.rule(25, y-38, 550, MUTED)
            body += art.text(role, 25, y+6, 45, PAPER, "display")
            body += art.lines(content, 25, y+49, 29)
        body += art.lines(["Originals stay retrievable.", "Exploration need not fill every handoff."], 25, 1010, 29, GREEN)
    else:
        w, h = 1200, 760
        body = art.pose(0, 22, 12, 205, 230)
        body += art.bubble(["One task. Three focused conversations.", "I'll show you what moves between them."], 260, 46, 904, 151, 38, "left")
        body += art.text("CONTEXT = WHAT A ROLE CAN WORK WITH", 32, 298, 56, GREEN, "display")
        body += art.text("One growing conversation", 32, 370, 34)
        body += art.rule(32, 389, 470, PINK)
        body += art.lines(["Original request", "Corrections + relevant source", "Exploration + failed approaches", "Tool output + logs"], 32, 435, 31)
        body += art.text("Select by purpose", 602, 370, 34, GREEN)
        for y, role, line in [(435,"THINKER","Task, sources, scope, checks"), (527,"DOER","Scoped change + latest correction"), (619,"REVIEWER","Request, candidate, evidence")]:
            body += art.rule(602, y-30, 564, MUTED)
            body += art.text(role, 602, y+3, 39, PAPER, "display")
            body += art.text(line, 602, y+39, 29)
        body += art.lines(["Originals stay retrievable. Exploration need not fill every handoff."], 32, 718, 30, GREEN)
    art.save("context-mobile" if mobile else "context", w, h, body, "Capri explains context selection; native text equivalent in CAPRI_EXPLAINS.md")


def geometry(art, mobile):
    if mobile:
        w, h = 600, 1220
        body = art.text("PLAN  /  BUILD  /  REVIEW", 24, 61, 51, GREEN, "display")
        for i, (role, lines) in enumerate([( "THINKER", ["Research + scope", "Task / source / checks"]), ("DOER", ["Scoped candidate", "Patch / checks / limits"]), ("REVIEWER", ["Fresh review context", "Request + patch", "Evidence + limits"]) ]):
            y = 106 + i*276
            body += art.rule(24, y, 552, MUTED)
            body += art.text(role, 24, y+55, 49, PAPER, "display")
            body += art.lines(lines, 24, y+96, 26)
        body += art.rule(24, 1000, 552, GREEN)
        body += art.text("THINKER REPORT  >  HUMAN DECISION", 24, 1053, 38, GREEN, "display")
        body += art.lines(["One write owner. Ordered stages.", "Uncertain effects? Hold and reconcile."], 24, 1104, 28)
        positions = [(316,126,260,148),(316,402,260,148),(316,678,260,148),(316,678,260,148)]
        bubbles = [(24,292,552,115),(24,568,552,115),(24,844,552,115),(24,844,552,115)]
    else:
        w, h = 1200, 850
        body = art.text("PLAN  /  BUILD  /  REVIEW", 30, 70, 66, GREEN, "display")
        roles = [("THINKER",["Research + scope","Task / source / checks"]), ("DOER",["Scoped candidate","Patch / checks / limits"]), ("REVIEWER",["Fresh review context","Request / patch / evidence"])]
        for i, (role, lines) in enumerate(roles):
            x = 30+i*395
            body += art.rule(x, 104, 350, MUTED)
            body += art.text(role, x, 167, 64, PAPER, "display")
            body += art.lines(lines, x, 216, 29)
        body += f'<path d="M355 350h70m-14 -9 14 9-14 9M750 350h70m-14 -9 14 9-14 9" stroke="{GREEN}" stroke-width="3" fill="none"/>'
        body += art.rule(30, 644, 1140, GREEN)
        body += art.text("THINKER REPORT  >  HUMAN DECISION", 30, 713, 58, GREEN, "display")
        body += art.lines(["One write owner. Ordered stages.", "Uncertain effects? Hold and reconcile."], 30, 766, 30)
        positions = [(40,280,330,185),(435,280,330,185),(830,280,330,185),(830,280,330,185)]
        bubbles = [(30,492,350,133),(425,492,350,133),(820,492,350,133),(425,492,745,133)]
    return w, h, body, positions, bubbles


def guide(art, mobile):
    w, h, base, positions, bubbles = geometry(art, mobile)
    prefix = "guide-mobile" if mobile else "guide"
    holds = []
    for i in range(4):
        x,y,pw,ph = positions[i]
        bx,by,bw,bh = bubbles[i]
        body = base + art.pose(min(i,2), x,y,pw,ph)
        if i == 1:
            if mobile:
                body += art.text("PACKET: blank -> Untitled", 24, 551, 27, GREEN)
            else:
                body += f'<path d="M800 304h365v125H800Z" fill="none" stroke="{GREEN}" stroke-width="2"/>'
                body += art.lines(["HANDOFF PACKET", "label.py only", "blank -> Untitled"], 820, 338, 28, GREEN)
        # The pointer touches the active handoff lane; source pose is never altered.
        body += f'<path d="M{x+pw-14} {y+ph-7}L{bx+bw-27} {by-13}" stroke="{PINK}" stroke-width="3"/>'
        body += art.bubble(BUBBLES[i],bx,by,bw,bh,27 if mobile else 29)
        art.save(f"{prefix}-beat-{i+1}",w,h,body,"Capri guide, beat " + str(i+1) + "; illustrative workflow, not live execution")
        holds.append(Image.open(OUT / f"{prefix}-beat-{i+1}.png").convert("RGB"))
    # 16-second overview. Stable labels and long holds; only the source inset moves.
    frames, durations = [], []
    for i in range(4):
        frames.append(holds[i]);durations.append(3600)
        nxt = (i+1)%4
        for n in range(1,5):
            t = n/4
            x,y,pw,ph = positions[i]
            nx,ny,_,_ = positions[nxt]
            body = base + art.pose(min(nxt,2),x+(nx-x)*t,y+(ny-y)*t,pw,ph)
            art.save(f"{prefix}-transit",w,h,body,"Capri follows the handoff path")
            frames.append(Image.open(OUT/f"{prefix}-transit.png").convert("RGB"));durations.append(100)
    atlas = Image.new("RGB", (240*len(frames), round(h*240/w)))
    for i,frame in enumerate(frames):atlas.paste(frame.resize((240,atlas.height)),(240*i,0))
    palette = atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
    indexed = [im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
    indexed[0].save(OUT/f"{prefix}.gif",save_all=True,append_images=indexed[1:],duration=durations,loop=0,optimize=True,disposal=1)
    # Poster is a complete four-beat comic, not the animation's first frame.
    if mobile:
        body = art.text("THE WHOLE HANDOFF",24,62,52,GREEN,"display")
        for i in range(4):
            top=100+i*330
            body += art.rule(24,top,552,MUTED)
            body += art.pose(min(i,2),24,top+20,190,175)
            body += art.text(["THINKER","DOER","REVIEWER","REPORT / HUMAN"][i],235,top+53,40,GREEN,"display")
            body += art.lines(BUBBLES[i],235,top+103,27)
            body += art.text(["Task + source + checks","Candidate + checks + limits","Findings + evidence","Human decision; no automatic next task"][i],24,top+247,28)
        body += art.lines(["Uncertain effects? Hold and reconcile.","Teaching diagram. No live run is shown."],24,1467,28)
        art.save("comic-mobile",600,1540,body,"Complete static guide: all four beats and uncertainty branch")
    else:
        body = art.text("THE WHOLE HANDOFF",30,65,62,GREEN,"display")
        for i in range(4):
            x=30+(i%2)*590;y=105+(i//2)*370
            body += art.rule(x,y,550,MUTED)
            body += art.pose(min(i,2),x,y+25,220,180)
            body += art.text(["THINKER","DOER","REVIEWER","REPORT / HUMAN"][i],x+240,y+60,43,GREEN,"display")
            body += art.lines(BUBBLES[i],x+240,y+111,27)
            body += art.text(["Task + source + checks","Candidate + checks + limits","Findings + evidence","Human decision; no automatic next task"][i],x,y+271,29)
        body += art.lines(["Uncertain effects? Hold and reconcile. This teaching diagram is not a live run."],30,886,30)
        art.save("comic",1200,930,body,"Complete static guide: all four beats and uncertainty branch")
    for suffix in ["svg","png"]:(OUT/f"{prefix}-transit.{suffix}").unlink()
    # A .png sibling is the complete lesson for local pause/reduced-motion fallback.
    Image.open(OUT/("comic-mobile.png" if mobile else "comic.png")).save(OUT/f"{prefix}.png",optimize=True)


def main():
    OUT.mkdir(exist_ok=True)
    source_record=json.loads((MEDIA/"SOURCES.json").read_text())
    for record in source_record["selected"]:
        if hashlib.sha256((MEDIA/record["candidate_path"]).read_bytes()).hexdigest()!=record["sha256"]:
            raise ValueError("Source hash mismatch: " + record["candidate_path"])
    art=Art()
    for mobile in [False,True]:
        context(art,mobile)
        guide(art,mobile)
    outputs={p.name:{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.iterdir()) if p.suffix in {"svg",".svg",".png",".gif"}}
    record={"version":6,"poses":[{"source":s,"frame":f,"treatment":"whole source-frame inset; no mirroring, invented anatomy or generative fill"} for s,f in POSES],"overview_duration_ms":16000,"reading_hold_ms":3600,"transition_ms":400,"outputs":outputs,"scope":"Deterministic source-derived illustration; no live run, speed/cost measurement or visual approval","font":"Barlow Regular and Barlow Condensed ExtraBold Italic; bundled SIL OFL notice"}
    (OUT/"BUILD.json").write_text(json.dumps(record,indent=2)+"\n")
    print(json.dumps({"files":len(outputs),"motion_ms":16000,"motion_bytes":{p.name:p.stat().st_size for p in OUT.glob("*.gif")}},indent=2))


if __name__ == "__main__":
    main()
