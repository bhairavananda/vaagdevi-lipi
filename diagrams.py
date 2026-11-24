#!/usr/bin/env python3
"""Draw the explanatory diagrams in docs/images/ with the built font.

Every Devanagari line is drawn the way iTerm2 draws it (CoreText plus
iTerm2's glyph placement, see preview.py), so the diagrams stay true to the
font as it changes.

    .venv/bin/python diagrams.py      (after make; or: make diagrams)

Writes docs/images/diagram-{cells,packing,svara-lines,line-spacing}.png.
"""

import sys
import unicodedata
from pathlib import Path

import CoreText as CT
import Quartz as Q
from Foundation import NSURL, NSAttributedString

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build import CELL, LINE_SPACING, RAISE, SCALE, cells_of_char  # noqa: E402
from ligate import ANUDATTA_TOP, SVARITA_BOTTOM, word_aksharas  # noqa: E402
from preview import draw_line, ink, load_font  # noqa: E402

OUT = HERE / "docs/images"
PX = 2                                 # pixels per point: retina-sized images
BG = (0.157, 0.157, 0.157)
FG = (0.92, 0.86, 0.70)
GRID = (0.45, 0.42, 0.38)
MUTED = (0.66, 0.60, 0.52)
LABEL = (0.98, 0.74, 0.18)
BLUE = (0.37, 0.66, 0.96)
SALMON = (0.98, 0.52, 0.41)
RED = (0.98, 0.29, 0.20)


# --- drawing helpers ----------------------------------------------------------------

class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ctx = Q.CGBitmapContextCreate(None, int(w * PX), int(h * PX), 8, 0,
                                           Q.CGColorSpaceCreateDeviceRGB(),
                                           Q.kCGImageAlphaPremultipliedLast)
        Q.CGContextScaleCTM(self.ctx, PX, PX)
        self.fill_rect(0, 0, w, h, BG)
        self.mono = CT.CTFontCreateWithName("Menlo-Regular", 13, None)
        self.mono_small = CT.CTFontCreateWithName("Menlo-Regular", 11, None)
        self.deva = CT.CTFontCreateWithName("KohinoorDevanagari-Regular", 20, None)

    def y(self, top):
        """Convert a distance from the top edge into Quartz's bottom-up y."""
        return self.h - top

    def fill_rect(self, x, y, w, h, color, alpha=1.0):
        Q.CGContextSetRGBFillColor(self.ctx, *color, alpha)
        Q.CGContextFillRect(self.ctx, Q.CGRectMake(x, y, w, h))

    def stroke_rect(self, x, y, w, h, color, alpha=1.0, width=1.0):
        Q.CGContextSetRGBStrokeColor(self.ctx, *color, alpha)
        Q.CGContextSetLineWidth(self.ctx, width)
        Q.CGContextStrokeRect(self.ctx, Q.CGRectMake(x, y, w, h))

    def line(self, x0, y0, x1, y1, color, alpha=1.0, width=1.0, dash=None):
        Q.CGContextSetRGBStrokeColor(self.ctx, *color, alpha)
        Q.CGContextSetLineWidth(self.ctx, width)
        Q.CGContextSetLineDash(self.ctx, 0, dash or [], len(dash or []))
        Q.CGContextMoveToPoint(self.ctx, x0, y0)
        Q.CGContextAddLineToPoint(self.ctx, x1, y1)
        Q.CGContextStrokePath(self.ctx)
        Q.CGContextSetLineDash(self.ctx, 0, [], 0)

    def text(self, s, x, y, color=MUTED, font=None, center=False):
        font = font or self.mono
        attrs = {CT.kCTFontAttributeName: font,
                 CT.kCTForegroundColorAttributeName: Q.CGColorCreateGenericRGB(*color, 1)}
        line = CT.CTLineCreateWithAttributedString(
            NSAttributedString.alloc().initWithString_attributes_(s, attrs))
        if center:
            x -= CT.CTLineGetTypographicBounds(line, None, None, None)[0] / 2
        Q.CGContextSetTextPosition(self.ctx, x, y)
        CT.CTLineDraw(line, self.ctx)

    def deva_line(self, font, s, x, y, color=FG):
        Q.CGContextSetRGBFillColor(self.ctx, *color, 1)
        # Glyphs are drawn relative to the text position, which labels move.
        Q.CGContextSetTextPosition(self.ctx, 0, 0)
        Q.CGContextSetTextMatrix(self.ctx, Q.CGAffineTransformIdentity)
        draw_line(self.ctx, font, s, x, y)

    def save(self, name):
        path = OUT / name
        img = Q.CGBitmapContextCreateImage(self.ctx)
        dst = Q.CGImageDestinationCreateWithURL(NSURL.fileURLWithPath_(str(path)), "public.png", 1, None)
        Q.CGImageDestinationAddImage(dst, img, None)
        Q.CGImageDestinationFinalize(dst)
        print(f"wrote {path.relative_to(HERE)}")


def cell_groups(word):
    """The characters that own each of the word's cells (marks join the cell before)."""
    cells = []
    for c in word:
        if cells_of_char(c) == 0 and cells:
            cells[-1] += c
        else:
            cells.append(c)
    return cells


def show(chars):
    """A cell's characters as a label: a lone sign gets a dotted circle."""
    if unicodedata.category(chars[0]) in ("Mc", "Mn"):
        return "◌" + chars
    return chars


# --- 1. cells -----------------------------------------------------------------------

def diagram_cells():
    word = "अ॒ग्निमी॑ळे"
    size = 64
    cell = CELL / 1000 * size
    groups = cell_groups(word)
    x0, W = 40, 40 + cell * len(groups) + 300
    c = Canvas(W, 360)
    c.text("iTerm2 gives every letter and spacing vowel sign one cell; marks get none.",
           20, c.y(26), LABEL)
    # the word, as Vaagdevi draws it, on its cells
    top = 60
    for k in range(len(groups)):
        c.stroke_rect(x0 + k * cell, c.y(top + 130), cell, 130, GRID)
    c.deva_line(load_font(size), word, x0, c.y(top + 98))
    c.text("as Vaagdevi draws it", x0 + cell * len(groups) + 20, c.y(top + 70))
    # who owns each cell
    for k, g in enumerate(groups):
        c.text(show(g), x0 + k * cell + cell / 2, c.y(top + 170), FG, c.deva, center=True)
    c.text("characters owning each cell", x0 + cell * len(groups) + 20, c.y(top + 165))
    # akṣaras and their budgets
    start = 0
    for ak in word_aksharas(word):
        n = sum(cells_of_char(ch) for ch in ak)
        a, b = x0 + start * cell + 4, x0 + (start + n) * cell - 4
        yy = c.y(top + 205)
        c.line(a, yy, b, yy, LABEL, width=1.5)
        c.line(a, yy, a, yy + 6, LABEL, width=1.5)
        c.line(b, yy, b, yy + 6, LABEL, width=1.5)
        c.text(ak, (a + b) / 2, c.y(top + 235), FG, c.deva, center=True)
        c.text(f"{n} cell{'s' * (n != 1)}", (a + b) / 2, c.y(top + 260), LABEL, c.mono_small, center=True)
        start += n
    c.text("akṣaras and the cells they own", x0 + cell * len(groups) + 20, c.y(top + 235))
    c.save("diagram-cells.png")


# --- 2. packing ---------------------------------------------------------------------

def diagram_packing():
    text = "अ॒ग्निमी॑ळे पु॒रोहि॑तं य॒ज्ञस्य॑"
    size = 44
    cell = CELL / 1000 * size
    ncells = sum(cells_of_char(ch) for ch in text)
    x0 = 40
    W = x0 + ncells * cell + 40
    c = Canvas(W, 330)
    font = load_font(size)
    natural = CT.CTFontCreateWithName("KohinoorDevanagari-Regular", size * 0.9, None)

    def grid(top, h):
        for k in range(ncells):
            c.stroke_rect(x0 + k * cell, c.y(top + h), cell, h, GRID, 0.6)

    # (a) each akṣara centred in its own cells
    top = 40
    c.text("Centred in its cells: gaps wherever an akṣara owns spare cells", 20, c.y(top - 12), MUTED)
    grid(top, 80)
    col = 0
    for word in text.split(" "):
        for ak in word_aksharas(word):
            n = sum(cells_of_char(ch) for ch in ak)
            cx = x0 + (col + n / 2) * cell
            c.text(ak, cx, c.y(top + 52), FG, natural, center=True)
            col += n
        col += 1
    # (b) Vaagdevi: packed
    top = 190
    c.text("Vaagdevi: each word set as in print, its spare cells after it", 20, c.y(top - 12), LABEL)
    grid(top, 80)
    base = c.y(top + 52)
    c.deva_line(font, text, x0, base)
    col = 0
    for word in text.split(" "):
        n = sum(cells_of_char(ch) for ch in word)
        rects = ink(font, word, x0 + col * cell, base)
        right = max(r[2] for r in rects)
        end = x0 + (col + n) * cell
        if end > right + 2:
            c.fill_rect(right + 2, c.y(top + 80), end - right - 2, 80, LABEL, 0.14)
            c.text("spare", (right + end) / 2, c.y(top + 96), LABEL, c.mono_small, center=True)
        col += n + 1
    c.save("diagram-packing.png")


# --- 3. svara lines -----------------------------------------------------------------

def diagram_svara_lines():
    text = "ई॒ळे॒ र॒त्न॒धात॑मम् ज॑ जं"
    size = 72
    cell = CELL / 1000 * size
    ncells = sum(cells_of_char(ch) for ch in text)
    x0 = 40
    W = x0 + ncells * cell * 1.25 + 200
    c = Canvas(W, 210)
    c.text("Anudātta hangs from one low line, svarita stands on one line above the headline.",
           20, c.y(26), LABEL)
    base = c.y(130)
    font = load_font(size)
    c.deva_line(font, text, x0, base)
    k = size / 1000
    low = base + (ANUDATTA_TOP * SCALE + RAISE) * k        # top edge of every anudātta
    high = base + (SVARITA_BOTTOM * SCALE + RAISE) * k     # foot of every svarita
    right = max(r[2] for r in ink(font, text, x0, base)) + 16
    c.line(x0 - 10, low, right, low, BLUE, 0.9, 1.2, [6, 4])
    c.line(x0 - 10, high, right, high, SALMON, 0.9, 1.2, [6, 4])
    c.text("svarita line", right + 10, high - 4, SALMON)
    c.text("anudātta line", right + 10, low - 4, BLUE)
    c.text("last two: svarita vs anusvāra", right - 230, c.y(190), MUTED, c.mono_small)
    c.save("diagram-svara-lines.png")


# --- 4. line spacing ----------------------------------------------------------------

def diagram_line_spacing():
    # The deepest anudātta (under ु) above the tallest svarita (on ो): real
    # Ṛgveda words. In RV 1.1 the closest marks nearly touch but don't overlap.
    lines = ["दु॒हि॒ता दि॒वः", "सो॑म॒ रथो॑"]
    size = 40
    cell = CELL / 1000 * size
    ncells = max(sum(cells_of_char(ch) for ch in l) for l in lines)
    panel = max(ncells * cell, 300) + 60
    c = Canvas(2 * panel + 40, 260)
    font = load_font(size)
    for p, (spacing, title, color) in enumerate(((1.0, "vertical spacing 100%", RED),
                                                 (LINE_SPACING, f"vertical spacing {LINE_SPACING:.0%}", LABEL))):
        x0 = 40 + p * panel
        row = size * 1.333 * spacing
        c.text(title, x0, c.y(26), color)
        top = 50
        bases = []
        for r in range(2):
            y_top = top + r * row
            c.stroke_rect(x0 - 6, c.y(y_top + row), panel - 60, row, GRID, 0.5)
            base = c.y(y_top) - (row - 1.333 * size) / 2 - size * 1.0 - size * 0.083 / 2
            bases.append(base)
            c.deva_line(font, lines[r], x0, base)
        # where the first line's lowest ink meets the second line's highest
        upper = ink(font, lines[0], x0, bases[0])
        lower = ink(font, lines[1], x0, bases[1])
        overlap = []
        for a in upper:
            for b in lower:
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3]:
                    overlap.append((max(a[0], b[0]), min(a[2], b[2]), a[1], b[3]))
        for x_a, x_b, y_lo, y_hi in overlap:
            c.stroke_rect(x_a - 2, y_lo - 2, x_b - x_a + 4, y_hi - y_lo + 4, RED, 1.0, 1.5)
        note = "svara marks of the two lines collide" if overlap else "svara marks clear each other"
        c.text(note, x0, c.y(top + 2 * row + 24), color, c.mono_small)
    c.save("diagram-line-spacing.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    diagram_cells()
    diagram_packing()
    diagram_svara_lines()
    diagram_line_spacing()


if __name__ == "__main__":
    main()
