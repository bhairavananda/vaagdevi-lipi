#!/usr/bin/env python3
"""Make Vaagdevi safe for iTerm2's grid alignment.

iTerm2 3.5 (CoreTextLineRenderingHelper.swift) re-places every glyph CoreText
produces: glyphs are sorted by the terminal cell of the character they came
from, and each new cell is re-anchored to that cell's left edge. That is
harmless when glyphs come out in character order. Devanagari reorders on
purpose (ि is drawn before its consonant, reph after it), so iTerm2 moves
those glyphs by whole cells and stacks half forms under the next consonant.

A single glyph can't be split up that way. So for every akṣara whose glyphs
iTerm2 would misplace, this script bakes CoreText's own layout of the akṣara,
marks included, into one composite glyph, and adds a GSUB ligature that swaps
the shaped glyph sequence for it. Akṣaras that iTerm2 already draws correctly
are left alone.

    .venv/bin/python ligate.py      (after build.py; or: make)
"""

import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import CoreText as CT
import uharfbuzz as hb
from Foundation import NSURL
from fontTools.otlLib.builder import buildLigatureSubstSubtable
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build import CELL, DIST, OUT, corpus_words  # noqa: E402

UPM = 1000.0
CONSONANTS = [chr(c) for c in range(0x0915, 0x093A)] + ["ळ"]
MARK_TAILS = ["", "॑", "॒", "ं", "ः", "ँ", "ं॑", "ं॒", "ः॑", "ः॒"]


# --- CoreText -----------------------------------------------------------------------

class Shaper:
    def __init__(self, path):
        descs = CT.CTFontManagerCreateFontDescriptorsFromURL(NSURL.fileURLWithPath_(str(path)))
        self.font = CT.CTFontCreateWithFontDescriptor(descs[0], UPM, None)

    def shape(self, text):
        """Glyph names, positions (font units), advances and string indices."""
        attrs = {CT.kCTFontAttributeName: self.font}
        line = CT.CTLineCreateWithAttributedString(CT.CFAttributedStringCreate(None, text, attrs))
        out = []
        for run in CT.CTLineGetGlyphRuns(line):
            n = CT.CTRunGetGlyphCount(run)
            rf = CT.CTRunGetAttributes(run)[CT.kCTFontAttributeName]
            g = CT.CTRunGetGlyphs(run, (0, n), None)
            p = CT.CTRunGetPositions(run, (0, n), None)
            a = CT.CTRunGetAdvances(run, (0, n), None)
            i = CT.CTRunGetStringIndices(run, (0, n), None)
            for k in range(n):
                out.append(dict(name=CT.CTFontCopyNameForGlyph(rf, g[k]), x=p[k].x, y=p[k].y,
                                adv=a[k].width, idx=i[k]))
        return out


def iterm_cells(text):
    """For each character: (cell it is drawn with, that cell's x origin), as
    iTerm2 3.5 builds them (ScreenChar.m StringToScreenChars and
    iTermAttributedStringBuilder.m).

    - Each letter or spacing vowel sign starts a new cell; zero-width marks
      (Mn) join the cell before them.
    - A cell holding nothing but a spacing vowel sign (ि ा ी ो ौ ः, Mc) keeps
      its own cell on the grid but is drawn together with the previous cell,
      at that cell's x, so it combines with its consonant. If a mark follows
      the sign in the same cell (कि॑), the cell is drawn on its own instead.
    """
    cells = []
    for c in text:
        if unicodedata.category(c) in ("Mn", "Me") and cells:
            cells[-1] += c
        else:
            cells.append(c)
    out, last_x = [], None
    for i, cell in enumerate(cells):
        merged = (i > 0 and len(cell) == 1 and unicodedata.category(cell) == "Mc"
                  and not (len(cells[i - 1]) == 1 and ord(cells[i - 1]) < 128))
        draw, x = (i - 1, last_x) if merged else (i, i * CELL)
        for _ in cell:
            out.append((draw, x))
        last_x = x
    return out


def iterm_x(glyphs, text):
    """Where iTerm2 3.5 draws each glyph (port of CoreTextLineRenderingHelper.swift)."""
    cells = iterm_cells(text)
    order = sorted(range(len(glyphs)),
                   key=lambda j: (cells[glyphs[j]["idx"]][0], glyphs[j]["x"] + glyphs[j]["adv"], j))
    new = [g["x"] for g in glyphs]
    last_col, last_col_ext, last_glyph_ext = None, 0.0, 0.0
    for j in order:
        col, x0 = cells[glyphs[j]["idx"]]
        if col != last_col:
            last_col_ext = last_glyph_ext
        new[j] = glyphs[j]["x"] + x0 - last_col_ext
        last_col = col
        last_glyph_ext = glyphs[j]["x"] + glyphs[j]["adv"]
    return new


TOLERANCE = 40   # font units: 0.5 px at 12 pt


def misplaced(glyphs, text):
    """True if iTerm2 would draw any glyph of this akṣara away from CoreText's
    position, or if a glyph's origin reaches past the akṣara's last cell.
    iTerm2 treats the rightmost origin as the cell's end, so an overhanging
    mark would push the next akṣara."""
    end = sum(g["adv"] for g in glyphs)
    if any(g["x"] + g["adv"] > end + TOLERANCE for g in glyphs):
        return True
    return any(abs(a - g["x"]) > TOLERANCE for a, g in zip(iterm_x(glyphs, text), glyphs))


# --- Syllables --------------------------------------------------------------------

def syllables(words, font_path):
    """Distinct akṣaras with their counts, using HarfBuzz's syllable clusters."""
    hbf = hb.Font(hb.Face(Path(font_path).read_bytes()))
    seen = Counter()
    for word, n in words.items():
        buf = hb.Buffer()
        buf.add_str(word)
        buf.guess_segment_properties()
        hb.shape(hbf, buf, {"liga": False})
        starts = sorted({i.cluster for i in buf.glyph_infos})
        for k, s in enumerate(starts):
            e = starts[k + 1] if k + 1 < len(starts) else len(word)
            seen[word[s:e]] += n
    return seen


def synthetic():
    """Common akṣaras beyond the corpus: every consonant with ि or reph, with marks."""
    out = []
    for c in CONSONANTS:
        for tail in MARK_TAILS:
            out += [c + "ि" + tail, "र्" + c + tail, "र्" + c + "ि" + tail]
    return out


# --- Composites -------------------------------------------------------------------

CONDENSE_BELOW = 0.9   # akṣaras that would be squeezed more than this use the condensed design
ANUDATTA = ("uni0952",)
SVARITA = ("uni0951", "uni1CDA")
CLEARANCE = 120         # font units between a svara mark and the letter's ink
ANUDATTA_TOP = -300     # fixed top edge of every anudātta, just below ु and ृ (-268)
SVARITA_BOTTOM = 680    # fixed foot of every svarita, just above the headline (622)
SVARITA_STRETCH = 1.4   # Noto's svarita tick is short enough to read as a dot


def is_svara(name, kinds):
    return name.split(".")[0] in kinds


def clear_svaras(parts, gs):
    """Put svara marks on fixed lines, clear of the akṣara's ink.

    Every anudātta hangs from one low line and every svarita stands on one
    line above the headline, so runs of them read level. Ink that reaches past
    a line (ॄ below, ं above) pushes the mark just clear of it. The ि/ी arc
    and the reph's hook may meet a svarita, as in traditional typesetting.
    """
    from fontTools.pens.boundsPen import BoundsPen

    def box(name, x, y):
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        if not bp.bounds:
            return None
        x0, y0, x1, y1 = bp.bounds
        if is_svara(name, SVARITA):                      # account for the taller tick
            y1 = y0 + (y1 - y0) * SVARITA_STRETCH
        return (x + x0, y + y0, x + x1, y + y1)

    out = []
    for i, (name, x, y) in enumerate(parts):
        if is_svara(name, ANUDATTA) or is_svara(name, SVARITA):
            mb = box(name, x, y)
            others = [box(n, ox, oy) for j, (n, ox, oy) in enumerate(parts)
                      if j != i and not is_svara(n, ANUDATTA) and not is_svara(n, SVARITA)]
            over = [o for o in others if o and o[0] < mb[2] and o[2] > mb[0]]
            if mb and (over or is_svara(name, SVARITA)):
                if is_svara(name, ANUDATTA) and over:
                    # Every anudātta sits at one fixed low line, so a run of
                    # them (ई॒ळे॒) reads level. Only ink hanging below that line
                    # (ॄ) pushes it lower.
                    low = min(o[1] for o in over)
                    top = min(ANUDATTA_TOP, low - CLEARANCE)
                    y += top - mb[3]
                elif is_svara(name, SVARITA):
                    arcs = [box(n, ox, oy) for n, ox, oy in parts
                            if n.split(".")[0][:7] in ("uni093F", "uni0940")
                            or "0930094D" in n]
                    # Every svarita stands on one fixed line above the headline,
                    # like the anudātta below. It may meet the ि/ी arc (as in
                    # traditional typesetting); any other ink at that height (ं)
                    # lifts it just clear.
                    y += SVARITA_BOTTOM - mb[1]
                    mb = (mb[0], SVARITA_BOTTOM, mb[2], SVARITA_BOTTOM + mb[3] - mb[1])
                    touching = [o for o in over if o[1] < mb[3] and o[3] > mb[1]
                                and o not in arcs]
                    if touching:
                        high = max(o[3] for o in touching)
                        y += (high + 30) - mb[1]
        out.append((name, x, y))
    return out


def natural_layout(nat_font, nat_order, text):
    """Noto's own shaping of an akṣara: [(glyph, x, y)], total advance."""
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(nat_font, buf, {})
    parts, pen = [], 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        parts.append((nat_order[info.codepoint], pen + pos.x_offset, pos.y_offset))
        pen += pos.x_advance
    return parts, pen


def add_natural_glyphs(font, nat, names, suffix=".nat", bar=True):
    """Copy Noto's unfitted outlines in as `<name>.nat`, scaled and raised
    like the rest of the Devanagari but not squeezed into cells."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from build import SCALE, RAISE, HEADLINE
    gs = nat.getGlyphSet()
    glyf, hmtx = font["glyf"], font["hmtx"]
    added = []
    for n in sorted(names):
        rec = DecomposingRecordingPen(gs)
        gs[n].draw(rec)
        pen = TTGlyphPen(None)
        ys = [y for _, args in rec.value for _, y in args]
        base_y = min(ys) if ys else 0
        stretch = SVARITA_STRETCH if is_svara(n, SVARITA) else 1.0
        for op, args in rec.value:
            getattr(pen, op)(*[(round(x * SCALE),
                                round((base_y + (y - base_y) * stretch) * SCALE + RAISE))
                               for x, y in args])
        g = pen.glyph()
        glyf.glyphs[n + suffix] = g
        g.recalcBounds(glyf)
        # The left side bearing must equal xMin: Apple's renderer places a
        # TrueType outline from it, so a wrong value shifts the glyph.
        hmtx.metrics[n + suffix] = (0, getattr(g, "xMin", 0))
        added.append(n + suffix)
    if not bar:
        return added
    # One cell of plain shirorekha, stretched by composites to fill their cells.
    y0, y1 = round(HEADLINE[0] * SCALE + RAISE), round(HEADLINE[1] * SCALE + RAISE)
    pen = TTGlyphPen(None)
    pen.moveTo((0, y0)); pen.lineTo((0, y1)); pen.lineTo((CELL, y1)); pen.lineTo((CELL, y0))
    pen.closePath()
    glyf.glyphs["vaag.bar"] = pen.glyph()
    hmtx.metrics["vaag.bar"] = (CELL, 0)
    added.append("vaag.bar")
    return added


def component(name, x, y=0, xscale=1.0):
    c = GlyphComponent()
    c.glyphName = name
    c.x, c.y = round(x), round(y)
    c.flags = 0x1000                     # UNSCALED_COMPONENT_OFFSET: offsets are not scaled
    if abs(xscale - 1.0) > 1e-3:
        c.transform = [[xscale, 0.0], [0.0, 1.0]]
    return c


def add_ligatures(font, plans):
    """plans: {CoreText glyph sequence: (parts, budget, shift, headline)} →
    composites + one GSUB ligature lookup."""
    glyf, hmtx = font["glyf"], font["hmtx"]
    order = font.getGlyphOrder()
    mapping, new_names, shifts = {}, [], {}
    for n, (seq, (parts, budget, shift, headline)) in enumerate(sorted(plans.items())):
        name = f"vaag.ak{n:05d}"
        g = Glyph()
        g.numberOfContours = -1
        g.components = [component(c, x, y, k) for c, x, y, k in parts]
        if headline:
            # Shirorekha from the cell edges to the akṣara, so words join up.
            left, right = headline
            for a, b in ((0, None if left is None else left + 30),
                         (None if right is None else right - 30, budget)):
                if a is None or b is None:
                    continue
                while b - a > 4:
                    seg = min(b - a, 2 * CELL - 2)
                    g.components.append(component("vaag.bar", a - shift, 0, seg / CELL))
                    a += seg
        glyf.glyphs[name] = g
        hmtx.metrics[name] = (round(budget), 0)
        mapping[tuple(seq)] = name
        new_names.append(name)
        shifts[name] = -shift
    font.setGlyphOrder(order + new_names)
    for name in new_names:
        glyf[name].recalcBounds(glyf)
        hmtx.metrics[name] = (hmtx.metrics[name][0], getattr(glyf[name], "xMin", 0))
    gdef = font["GDEF"].table.GlyphClassDef.classDefs
    for name in new_names:
        gdef[name] = 1

    from fontTools.otlLib.builder import buildSingleSubstSubtable
    gsub = font["GSUB"].table
    lookups = []
    multi = {k: v for k, v in mapping.items() if len(k) > 1}
    single = {k[0]: v for k, v in mapping.items() if len(k) == 1}
    for ltype, table in ((4, buildLigatureSubstSubtable(multi) if multi else None),
                         (1, buildSingleSubstSubtable(single) if single else None)):
        if table is None:
            continue
        lookup = ot.Lookup()
        lookup.LookupType, lookup.LookupFlag = ltype, 0
        lookup.SubTable = [table]
        lookup.SubTableCount = 1
        gsub.LookupList.Lookup.append(lookup)
        lookups.append(len(gsub.LookupList.Lookup) - 1)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
    # Run them as late as possible, after every other substitution.
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag in ("psts", "haln"):
            fr.Feature.LookupListIndex.extend(lookups)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    (DIST / "composite_shifts.json").write_text(json.dumps(shifts))
    return len(new_names)




def main():
    from build import load_devanagari, cells_of_char, is_sign
    from fontTools.pens.boundsPen import BoundsPen
    stage1 = OUT
    shaper = Shaper(stage1)
    corpus = syllables(corpus_words(), stage1)
    candidates = list(corpus) + [s for s in synthetic() if s not in corpus]

    from build import SCALE, headline_span
    from fontTools.pens.recordingPen import DecomposingRecordingPen

    class Design:
        """One instance of Noto Sans Devanagari to draw composites from."""
        def __init__(self, wdth, suffix):
            self.font = load_devanagari(wdth)
            path = DIST / f".design{suffix}.ttf"
            self.font.save(path)
            self.hb = hb.Font(hb.Face(path.read_bytes()))
            path.unlink()
            self.order = self.font.getGlyphOrder()
            self.gs = self.font.getGlyphSet()
            self.suffix = suffix
            self.used = set()

        def layout(self, text):
            parts, adv = natural_layout(self.hb, self.order, text)
            return clear_svaras(parts, self.gs), adv

        def ink(self, parts):
            xs = []
            for name, x, y in parts:
                bp = BoundsPen(self.gs)
                self.gs[name].draw(bp)
                if bp.bounds:
                    xs += [x + bp.bounds[0], x + bp.bounds[2]]
            return (min(xs), max(xs)) if xs else (0, 0)

        def head(self, parts):
            pts = []
            for name, x, y in parts:
                rec = DecomposingRecordingPen(self.gs)
                self.gs[name].draw(rec)
                pts += [(px + x, py + y) for _, args in rec.value for px, py in args]
            return headline_span(pts)

    natural = Design(100, ".nat")
    # Noto's own condensed design, for akṣaras too wide for their cells
    # (आ owns one cell but is nearly two consonants wide). Same height and
    # stroke weight, unlike squeezing the natural design.
    condensed = Design(62.5, ".cnd")

    plans, bad_weight = {}, 0
    for text in candidates:
        glyphs = shaper.shape(text)
        if not glyphs:
            continue
        bad = misplaced(glyphs, text)
        bad_weight += corpus.get(text, 0) * bad
        budget = CELL * sum(cells_of_char(c) for c in text)
        design = natural
        parts, adv = design.layout(text)
        if budget / max(adv * SCALE, 1) < CONDENSE_BELOW:
            design = condensed
            parts, adv = design.layout(text)
        # Every multi-glyph akṣara becomes one composite drawn from Noto's
        # natural layout: iTerm2 can't pull it apart, and it reads naturally.
        # A single glyph needs one only if it had to switch to the condensed design.
        if len(glyphs) < 2 and not bad and design is natural:
            continue
        seq = tuple(g["name"] for g in glyphs)
        if seq in plans:
            continue
        # Samānam: every akṣara keeps its design's proportions at one common
        # size. Only an akṣara still wider than its cells is narrowed. Measure
        # by advance, not ink, so a hanging virāma (म्) doesn't shrink it.
        k = min(1.0, budget / max(adv * SCALE, 1))
        width = adv * SCALE * k
        pad = (budget - width) / 2
        # CoreText gives the composite the string index of its first glyph and
        # iTerm2 anchors it to that character's cell, so pre-shift the drawing
        # back by the same amount (see iterm_cells).
        shift = iterm_cells(text)[glyphs[0]["idx"]][1]
        comp = [(n + design.suffix, pad + x * SCALE * k - shift, y * SCALE, k)
                for n, x, y in parts]
        design.used |= {n for n, _, _ in parts}
        span = design.head(parts)
        edges = None
        if span is not None and any(not is_sign(n) for n, _, _ in parts):
            to_x = lambda v: pad + v * SCALE * k
            # Extend the shirorekha from the akṣara's own headline, on sides
            # where that headline reaches the ink's edge.
            ink_lo, ink_hi = design.ink(parts)
            edges = (to_x(span[0]) if span[0] - ink_lo < 60 else None,
                     to_x(span[1]) if ink_hi - span[1] < 60 else None)
        plans[seq] = (comp, budget, shift, edges)

    font = TTFont(stage1)
    order = font.getGlyphOrder()
    added = add_natural_glyphs(font, natural.font, natural.used, ".nat")
    added += add_natural_glyphs(font, condensed.font, condensed.used, ".cnd", bar=False)
    font.setGlyphOrder(order + added)
    n = add_ligatures(font, plans)
    font.save(OUT)
    total = sum(corpus.values())
    report = dict(distinct_aksharas=len(corpus), corpus_aksharas=total,
                  misplaced_by_iterm_without_composites=bad_weight, composites_added=n)
    (DIST / "ligate_report.json").write_text(json.dumps(report, indent=1))
    print(f"{len(corpus)} distinct akṣaras; {bad_weight}/{total} occurrences "
          f"({100 * bad_weight / total:.1f}%) would be misplaced by iTerm2 → "
          f"{n} natural composites added")


if __name__ == "__main__":
    main()
