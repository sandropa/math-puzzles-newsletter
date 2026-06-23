"""Build puzzles.json: every puzzle's name + crop coordinates, in fixed play order.

Run once locally:  .venv/bin/python build_index.py
The PDF is fetched from Dartmouth's public copy (same file the daily job uses),
so coordinates always match. No images are stored — send_email.py renders the
crops on the fly.

The book has three parallel sections, each keyed by puzzle name:
  - puzzle  : pdf pages 8-69,   bold CMBX12/12pt heading per puzzle
  - hint    : pdf pages 70-83,  bold CMBX10 "Name:" heading per hint
  - solution: pdf pages 84-417, bold CMBX12/12pt heading per solution, inside chapters
Each puzzle gets {name, strips, hint, solution}; hint/solution are crop strips too
(images, to keep math/figures faithful). Matched across sections by normalized name.
"""

import json
import random
import re
import urllib.request

import fitz  # PyMuPDF

URL = "https://math.dartmouth.edu/news-resources/electronic/puzzlebook/book/book.pdf"
PUZ = (8, 69)
HINT = (70, 83)
SOL = (84, 417)
CONT_TOP = 110

doc = fitz.open(stream=urllib.request.urlopen(URL).read(), filetype="pdf")
PAGE_H = doc[PUZ[0]].rect.height
PAGE_W = doc[PUZ[0]].rect.width

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def content_bottom(page):
    """Y just above the centered page-number footer (so it isn't cropped in)."""
    foot = PAGE_H
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            txt = "".join(s["text"] for s in line["spans"]).strip()
            if txt.isdigit() and line["bbox"][1] > PAGE_H * 0.85:
                foot = min(foot, line["bbox"][1])
    return foot - 6


def text_column(page):
    """Left/right margins of the page's body text column (constant width across the
    book, so every crop renders at the same scale and left-aligns). Ignores the
    running header (above CONT_TOP) and page-number footer."""
    bot = content_bottom(page)
    x0, x1 = PAGE_W, 0
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            ly = l["bbox"][1]
            if CONT_TOP < ly < bot:
                x0, x1 = min(x0, l["bbox"][0]), max(x1, l["bbox"][2])
    return (x0, x1) if x1 > x0 else (60, PAGE_W - 60)


def content_x(page, top, bottom):
    """Crop x-range: the full body text column, widened for any figures in the band.
    Full-column width (not flush-to-content) keeps a short one-line hint from being
    blown up to fill the email width; flush-left keeps recto/verso pages aligned."""
    x0, x1 = text_column(page)
    rects = [i["bbox"] for i in page.get_image_info()]
    rects += [d["rect"] for d in page.get_drawings()]
    for rx0, ry0, rx1, ry1 in rects:
        if ry1 > top and ry0 < bottom:  # a figure in the band
            x0, x1 = min(x0, rx0), max(x1, rx1)
    return (x0 - 2, x1 + 2)


def strips(sp, sy, ep, ey, top_pad=6):
    """Crop strips spanning a heading at (sp, sy) to a boundary at (ep, ey).
    top_pad is small for the dense hints list (else it grabs the line above)."""
    out = []
    for p in range(sp, ep + 1):
        top = sy - top_pad if p == sp else CONT_TOP
        bot = ey - 6 if p == ep else content_bottom(doc[p])
        if bot - top > 4:
            x0, x1 = content_x(doc[p], top, bot)
            out.append([p, round(top, 1), round(bot, 1), round(x0, 1), round(x1, 1)])
    return out


def marks_to_strips(marks, last_page, top_pad=6, starts=None):
    """marks: sorted (page, y, name|None). Named marks become strips bounded by the
    next mark of any kind; None marks are boundaries only (chapter titles).
    starts (in named-mark order) overrides where each strip begins — used to start a
    solution at its "Solution:" line, skipping the restated problem above it."""
    out, j = {}, 0
    for i, (sp, sy, name) in enumerate(marks):
        if name is None:
            continue
        if starts is not None:
            sp, sy = starts[j]
            j += 1
        ep, ey = marks[i + 1][:2] if i + 1 < len(marks) else (last_page, content_bottom(doc[last_page]))
        out[norm(name)] = strips(sp, sy, ep, ey, top_pad)
    return out


def heads(lo, hi, want):
    """want(spans, text) -> name|None|False. False=ignore line, None=boundary, str=named."""
    out = []
    for p in range(lo, hi + 1):
        for b in doc[p].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                spans = l["spans"]
                if not spans:
                    continue
                txt = "".join(s["text"] for s in spans).strip()
                name = want(spans, txt)
                if name is not False:
                    out.append((p, round(l["bbox"][1], 1), name))
    return out


def big12(spans, txt):  # puzzle / solution names: bold 12pt
    return txt if spans[0]["font"].startswith("CMBX12") and abs(spans[0]["size"] - 12) < 0.5 else False


def puzzle_heads(spans, txt):
    n = big12(spans, txt)
    return False if n in (False, "The Puzzles") else n


def sol_heads(spans, txt):
    n = big12(spans, txt)
    if n is not False:
        return n  # solution name
    if spans[0]["font"].startswith("CMBX") and spans[0]["size"] > 14:
        return None  # chapter / "Notes & Sources" boundary
    return False


def hint_heads(spans, txt):
    if spans[0]["font"].startswith("CMBX10") and ":" in txt:
        return txt.split(":")[0].strip()
    return False


def sol_label(spans, txt):  # the "Solution:" line; strip starts here, not at the name
    return None if (spans[0]["font"].startswith("CMBX10") and txt == "Solution:") else False


puz = [(p, y, n) for p, y, n in heads(*PUZ, puzzle_heads)]
hint_map = marks_to_strips(heads(*HINT, hint_heads), HINT[1], top_pad=1)
sol_starts = [(p, y) for p, y, _ in heads(*SOL, sol_label)]  # 1:1 with solution names, in order
sol_map = marks_to_strips(heads(*SOL, sol_heads), SOL[1], starts=sol_starts)

puzzles = []
for i, (p, y, name) in enumerate(puz):
    ep, ey = puz[i + 1][:2] if i + 1 < len(puz) else (PUZ[1], content_bottom(doc[PUZ[1]]))
    puzzles.append({
        "name": name,
        "strips": strips(p, y, ep, ey),
        "hint": hint_map.get(norm(name)),       # ponytail: None for the 1 puzzle w/o a hint
        "solution": sol_map.get(norm(name)),
    })

random.Random(20260622).shuffle(puzzles)  # fixed-seed shuffle = the daily play order
with open("puzzles.json", "w") as f:
    json.dump(puzzles, f, indent=0, ensure_ascii=False)

missing = sum(p["hint"] is None for p in puzzles), sum(p["solution"] is None for p in puzzles)
print(f"{len(puzzles)} puzzles -> puzzles.json (missing hints: {missing[0]}, solutions: {missing[1]})")
