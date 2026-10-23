#!/usr/bin/env python3
"""Build V5 art and reading paths from recorded footage, masks and OFL glyphs.

Media-only tool: no network, controller, runtime state or approved-hero writes.
"""
from io import BytesIO
from pathlib import Path
import base64
import hashlib
import html
import json
import subprocess

from PIL import Image, ImageDraw
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "showcase/capri"
OUT = MEDIA / "afterimage"
INK, PINK, GREEN, PAPER = "#100a19", "#ff1265", "#28fb86", "#f4f1ee"


class Artwork:
    def __init__(self):
        self.font = TTFont(MEDIA / "fonts/BarlowCondensed-ExtraBoldItalic.ttf")
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.units = self.font["head"].unitsPerEm

    def letters(self, text, x, y, size, color):
        offset, paths = 0, []
        for char in text:
            glyph = self.glyphs[self.cmap[ord(char)]]
            pen = SVGPathPen(self.glyphs)
            glyph.draw(pen)
            paths.append(f'<path transform="translate({offset},0)" d="{pen.getCommands()}"/>')
            offset += glyph.width
        return (f'<g fill="{color}" transform="translate({x},{y}) '
                f'scale({size / self.units},-{size / self.units})">' + "".join(paths) + "</g>")

    @staticmethod
    def image(frame, x, y, width, height, transparent=False):
        buffer = BytesIO()
        if transparent:
            frame.save(buffer, "PNG", optimize=True)
            mime = "png"
        else:
            frame.convert("RGB").save(buffer, "JPEG", quality=90, subsampling=0)
            mime = "jpeg"
        data = base64.b64encode(buffer.getvalue()).decode()
        return (f'<image x="{x}" y="{y}" width="{width}" height="{height}" '
                f'preserveAspectRatio="xMidYMid meet" href="data:image/{mime};base64,{data}"/>')

    @staticmethod
    def save(name, width, height, body, title, png=False):
        svg = OUT / f"{name}.svg"
        svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                       f'viewBox="0 0 {width} {height}" role="img"><title>{html.escape(title)}</title>'
                       f'{body}</svg>\n')
        if png:
            subprocess.run(["rsvg-convert", str(svg), "-o", str(OUT / f"{name}.png")], check=True)


def frame_at(source, index):
    with Image.open(MEDIA / "sources" / f"capri-{source}.gif") as image:
        image.seek(index)
        return image.convert("RGBA").copy()


def build_studies(art, recipe):
    s = recipe["stills"]
    expression = frame_at(s["expression"]["source"], s["expression"]["frame"])
    body = f'<rect width="1000" height="960" fill="{INK}"/>'
    body += f'<path d="M280 95H930V765H280Z" fill="none" stroke="{PINK}" stroke-width="3"/>'
    body += art.image(expression, 330, 24, 620, 697)
    body += art.letters("CAPRI", 28, 914, 260, PAPER)
    art.save("expression", 1000, 960, body, "Capri: expression study from source 1, frame 97", png=True)

    original_gesture = frame_at(s["gesture"]["source"], s["gesture"]["frame"])
    gesture = original_gesture.copy()
    mask = Image.new("L", (gesture.width * 4, gesture.height * 4))
    points = [(x * 4, y * 4) for x, y in recipe["gesture_mask"]["outline"]]
    ImageDraw.Draw(mask).polygon(points, fill=255)
    gesture.putalpha(mask.resize(gesture.size, Image.Resampling.LANCZOS))
    gesture.save(OUT / "gesture-hand-layer.png", optimize=True)
    body = f'<rect width="1000" height="660" fill="{PAPER}"/>'
    body += art.letters("HANDS", 42, 108, 115, INK)
    body += art.image(original_gesture, 80, 140, 840, 474)
    body += f'<path d="M45 115H790V640H45Z" fill="none" stroke="{INK}" stroke-width="3"/>'
    body += art.image(gesture, 80, 140, 840, 474, transparent=True)
    art.save("gesture", 1000, 660, body, "Source 14 frame 0, complete source box; her actual hand crosses the authored frame", png=True)

    movement = frame_at(s["movement"]["source"], s["movement"]["frame"])
    body = f'<rect width="1000" height="820" fill="{PAPER}"/>'
    body += art.letters("MOTION", 32, 148, 177, INK)
    body += art.image(movement, 0, 182, 1000, 564)
    art.save("movement", 1000, 820, body, "Capri moving through an industrial scene, source 20 frame 101", png=True)


def build_motion(art, recipe):
    motion = recipe["motion"]
    body = f'<rect width="760" height="500" fill="{INK}"/>'
    body += art.letters("AFTERIMAGE", 32, 477, 72, GREEN)
    art.save("interlude-overlay", 760, 500, body, "Stable Afterimage lettering", png=True)
    overlay = Image.open(OUT / "interlude-overlay.png").convert("RGB")
    frames, durations = [], []
    with Image.open(MEDIA / "sources" / f'capri-{motion["source"]}.gif') as source:
        first, last = motion["source_frames"]
        if not 0 <= first <= last < source.n_frames:
            raise ValueError("Motion source frame range is outside the supplied clip")
        for index in range(first, last + 1):
            source.seek(index)
            frame = overlay.copy()
            frame.paste(source.convert("RGB").resize((696, 393), Image.Resampling.LANCZOS), (32, 18))
            frames.append(frame)
            durations.append(source.info.get("duration", 100))
    source_duration = sum(durations)
    source_count = len(frames)
    durations[0] += motion["opening_hold_ms"]
    durations[-1] += motion["closing_hold_ms"]
    frames += [overlay.copy(), frames[0].copy()]
    durations += [motion["image_bound_ink_cut_ms"], motion["return_hold_ms"]]
    frames = [frame.resize(tuple(motion["delivery_size"]), Image.Resampling.LANCZOS) for frame in frames]
    # One palette for the entire loop avoids frame-dependent color pumping.
    atlas = Image.new("RGB", (190 * len(frames), 125))
    for index, frame in enumerate(frames):
        atlas.paste(frame.resize((190, 125)), (190 * index, 0))
    palette = atlas.quantize(colors=motion["colors"], method=Image.Quantize.MEDIANCUT)
    quantized = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    quantized[0].save(OUT / "interlude.gif", save_all=True, append_images=quantized[1:],
                      duration=durations, loop=0, optimize=True, disposal=1)
    frames[0].save(OUT / "interlude.png", optimize=True)
    body += art.image(frame_at(motion["source"], 0), 32, 18, 696, 393)
    art.save("interlude", 760, 500, body, "Afterimage interlude: still alternative from its actual first frame")
    return {"source_duration_ms": source_duration, "delivery_duration_ms": sum(durations),
            "source_frames": source_count, "authored_image_only_cut_ms": motion["image_bound_ink_cut_ms"]}


def build_reading_paths(art):
    for name, label, bg, fg in [("setup", "SETUP", GREEN, INK),
                               ("architecture", "ARCHITECTURE", INK, PAPER),
                               ("context", "OWNERSHIP", PAPER, INK),
                               ("recovery", "RECOVERY", PINK, PAPER),
                               ("evaluation", "EVALUATION", INK, GREEN),
                               ("index", "READING PATHS", GREEN, INK)]:
        body = f'<path d="M1 1H409L385 99H1Z" fill="{bg}" stroke="{INK}" stroke-width="2"/>'
        body += art.letters(label, 16, 70, 58 if len(label) < 12 else 49, fg)
        art.save(f"path-{name}", 410, 100, body, label)
    # This topology explains ownership gates, rather than duplicating the role map.
    for mobile, width in [(False, 1000), (True, 650)]:
        height = 1040 if mobile else 700
        body = f'<rect width="{width}" height="{height}" fill="{INK}"/>'
        if mobile:
            rows = [(56, "SOURCE + INSTRUCTIONS", 40, PAPER),
                    (172, "CHECK IDENTITY", 48, GREEN), (294, "ONE WRITE OWNER", 48, PAPER),
                    (416, "CANDIDATE + RECEIPTS", 42, PAPER), (558, "UNCERTAIN EFFECTS?", 43, PINK),
                    (686, "HOLD", 82, PINK), (816, "RECONCILE", 59, GREEN),
                    (891, "SOURCE / OWNER / EFFECTS", 32, PAPER)]
            for y, text, size, color in rows:
                body += art.letters(text, 30, y + 28, size, color)
            for top in [104, 223, 345, 469, 611, 744]:
                body += f'<path d="M51 {top}v31m-8 -10 8 10 8-10" fill="none" stroke="{PAPER}" stroke-width="2"/>'
            body += art.letters("NO AUTOMATIC RESTART", 30, 1003, 34, PAPER)
        else:
            body += art.letters("SOURCE + INSTRUCTIONS", 36, 72, 50, PAPER)
            body += art.letters("CHECK IDENTITY", 36, 162, 50, GREEN)
            body += art.letters("ONE WRITE OWNER", 36, 288, 62, PAPER)
            body += art.letters("CANDIDATE + RECEIPTS", 36, 392, 46, PAPER)
            body += f'<path d="M56 184v40m-9 -13 9 13 9-13M590 278H660V385m-9 -13 9 13 9-13" stroke="{PAPER}" stroke-width="3" fill="none"/>'
            body += art.letters("UNCERTAIN?", 650, 275, 47, PINK)
            body += art.letters("HOLD", 650, 447, 105, PINK)
            body += art.letters("RECONCILE", 36, 574, 78, GREEN)
            body += art.letters("SOURCE / OWNER / EFFECTS", 38, 631, 33, PAPER)
            body += f'<path d="M800 480v53H570m13 -9-13 9 13 9" stroke="{PAPER}" stroke-width="3" fill="none"/>'
        art.save("ownership-mobile" if mobile else "ownership", width, height, body,
                 "Source identity gates one write owner; uncertain effects hold for source, owner and effect reconciliation")


def main():
    OUT.mkdir(exist_ok=True)
    recipe = json.loads((OUT / "COMPOSITION.json").read_text())
    selected = json.loads((MEDIA / "SOURCES.json").read_text())["selected"]
    for source in selected:
        actual = hashlib.sha256((MEDIA / source["candidate_path"]).read_bytes()).hexdigest()
        if actual != source["sha256"]:
            raise ValueError("Source hash differs: " + source["candidate_path"])
    art = Artwork()
    build_studies(art, recipe)
    motion = build_motion(art, recipe)
    build_reading_paths(art)
    outputs = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(OUT.iterdir()) if p.suffix in {".svg", ".png", ".gif"}}
    record = {"version": 5, "recipe": "COMPOSITION.json", "motion": motion, "outputs": outputs,
              "scope": "Deterministic media-only composition; not runtime evidence or visual approval",
              "rights": "Private candidate; underlying anime redistribution unverified"}
    (OUT / "BUILD.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"outputs": len(outputs), "motion": motion}, indent=2))


if __name__ == "__main__":
    main()
