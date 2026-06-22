"""Build puzzles.json: every puzzle's name + crop coordinates, in fixed play order.

Run once locally:  .venv/bin/python build_index.py
The PDF is fetched from Dartmouth's public copy (same file the daily job uses),
so coordinates always match. No images are stored — send_email.py renders the
one puzzle of the day on the fly. Puzzle titles are the only CMBX (bold) headings
in the front "Puzzles" section (pdf pages 8-69); a puzzle spans from its heading
to the next, stitching across a page break.
"""

import json
import random
import urllib.request

import fitz  # PyMuPDF

URL = "https://math.dartmouth.edu/news-resources/electronic/puzzlebook/book/book.pdf"
FIRST, LAST = 8, 69
CONT_TOP = 110
SKIP = {"The Puzzles"}

doc = fitz.open(stream=urllib.request.urlopen(URL).read(), filetype="pdf")
PAGE_H = doc[FIRST].rect.height


def headings(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = line["spans"]
            if spans and spans[0]["font"].startswith("CMBX"):
                name = "".join(s["text"] for s in spans).strip()
                if name not in SKIP:
                    out.append((line["bbox"][1], name))
    return sorted(out)


def content_bottom(page):
    """Y just above the centered page-number footer (so it isn't cropped in)."""
    foot = PAGE_H
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            txt = "".join(s["text"] for s in line["spans"]).strip()
            if txt.isdigit() and line["bbox"][1] > PAGE_H * 0.85:
                foot = min(foot, line["bbox"][1])
    return foot - 6


heads = [(p, y, name) for p in range(FIRST, LAST + 1) for y, name in headings(doc[p])]


def strips(i):
    sp, sy, _ = heads[i]
    ep, ey = heads[i + 1][:2] if i + 1 < len(heads) else (LAST, content_bottom(doc[LAST]))
    out = []
    for p in range(sp, ep + 1):
        top = sy - 6 if p == sp else CONT_TOP
        bot = ey - 6 if p == ep else content_bottom(doc[p])
        if bot - top > 4:
            out.append([p, round(top, 1), round(bot, 1)])
    return out


puzzles = [{"name": heads[i][2], "strips": strips(i)} for i in range(len(heads))]
random.Random(20260622).shuffle(puzzles)  # fixed-seed shuffle = the daily play order
with open("puzzles.json", "w") as f:
    json.dump(puzzles, f, indent=0, ensure_ascii=False)
print(f"{len(puzzles)} puzzles -> puzzles.json")
