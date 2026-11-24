#!/usr/bin/env python3
"""Make Vaagdevi safe for iTerm2's grid alignment.

iTerm2 3.5 (CoreTextLineRenderingHelper.swift) re-places every glyph CoreText
produces: glyphs are sorted by the terminal cell of the character they came
from, and each new cell is re-anchored to that cell's left edge. That is
harmless when glyphs come out in character order. Devanagari reorders on
purpose (ि is drawn before its consonant, reph after it), so iTerm2 moves
those glyphs by whole cells and stacks half forms under the next consonant.

A single glyph can't be split up that way. So for every akṣara this script
bakes Noto's own layout of the akṣara, marks included, into one composite
glyph, and adds a GSUB ligature that swaps the shaped glyph sequence for it.
It then packs words as in print: each akṣara gets copies pre-shifted by the
slack of the akṣaras before it, and a chained lookup in 'calt' picks the copy
from the previous glyph (see docs/how-it-works.md).

    .venv/bin/python ligate.py      (after build.py; or: make)
"""

import json
import os
import re
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

_C = "\u0915-\u0939\u0958-\u095F\u0978-\u097F"                 # consonants
_V = "\u0904-\u0914\u0960\u0961\u0972-\u0977"                  # independent vowels
_M = "\u093A\u093B\u093E-\u094C\u094E\u094F\u0955-\u0957\u0962\u0963"  # vowel signs
_MARKS = "\u0900-\u0903\u0951-\u0954\u1CD0-\u1CFF\uA8E0-\uA8F1\u200C\u200D"
AKSHARA = re.compile(
    f"(?:(?:[{_C}]\u093C?\u094D[\u200C\u200D]?)*[{_C}]\u093C?(?:[{_M}]+|\u094D)?"
    f"|[{_V}]|.)[{_MARKS}]*", re.S)


def word_aksharas(word, font_path=None):
    """A word's akṣaras (orthographic syllables): any number of consonant +
    virāma, a consonant, then its vowel signs or a final virāma, then marks.
    A virāma before an independent vowel (र्ऋ) ends the syllable."""
    return AKSHARA.findall(word)


def syllables(words, font_path):
    """Distinct akṣaras with their counts."""
    seen = Counter()
    for word, n in words.items():
        for ak in word_aksharas(word, font_path):
            seen[ak] += n
    return seen


def synthetic():
    """Common akṣaras beyond the corpus: every consonant with ि or reph, with marks."""
    out = []
    for c in CONSONANTS:
        for tail in MARK_TAILS:
            out += [c + "ि" + tail, "र्" + c + tail, "र्" + c + "ि" + tail]
    return out


# --- Composites -------------------------------------------------------------------

# Packing. iTerm2 gives an akṣara one cell per letter or spacing vowel sign,
# so रो or हि get 2 cells for about 1.2 cells of letter. Rather than stretch
# letters or leave gaps inside words, every akṣara is drawn at its natural
# width and pulled left by the slack of the akṣaras before it in the word, so
# a word is set as in print and its spare cells collect after it. A composite
# can't see its neighbours, so each akṣara gets pre-shifted variants and a
# chained GSUB lookup picks the variant from the previous akṣara's glyph.
PACK_Q = 50          # font units per shift step (0.3 pt at 12 pt)
PACK_MAX = 1800      # largest shift; slack beyond it stays inside the word
XSCALE = float(os.environ.get("XSCALE", 1.2))      # every akṣara a little wider, so words fill more of their cells
OVERHANG = int(os.environ.get("OVERHANG", 300))    # how far a word may run past its cells, into the space after it (½ cell)
# A word with a lot of slack (स॒त्यश्चि॒त्रश्र॑वस्तमः: 15 cells, 8 akṣaras) would
# leave a hole after it. Once the carried slack passes TRACK_FROM, each later
# akṣara keeps a small gap before it, bridged by the shirorekha.
TRACK_FROM = int(os.environ.get("TRACK_FROM", 450))      # carried slack (font units) before gaps start
TRACK_RATE = float(os.environ.get("TRACK_RATE", 0.5))    # share of the carried slack above TRACK_FROM given back per akṣara
TRACK_MAX = int(os.environ.get("TRACK_MAX", 240))        # largest gap (0.4 cell)
VISARGA = "uni0903"
CONDENSE_BELOW = 0.9   # akṣaras that would be squeezed more than this use the condensed design
ANUDATTA = ("uni0952",)
SVARITA = ("uni0951", "uni1CDA")
CLEARANCE = 90          # font units between a svara mark and the letter's ink
ANUDATTA_TOP = -300     # fixed top edge of every anudātta, just below ु and ृ (-268)
SVARITA_BOTTOM = 680    # fixed foot of every svarita, just above the headline (622)
SVARITA_STRETCH = 1.3   # Noto's svarita tick is short enough to read as a dot


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


def family(name):
    return name.split(".")[0]


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


def add_bars(g, a, b, shift):
    while b - a > 4:
        seg = min(b - a, 2 * CELL - 2)
        g.components.append(component("vaag.bar", a - shift, 0, seg / CELL))
        a += seg


def add_calt(gsub, lookup_index):
    """Put a lookup in a new 'calt' feature for the Devanagari scripts.
    Shapers apply Devanagari's own features (psts, haln, ...) one syllable at
    a time, so a rule there can't see the previous akṣara; calt runs after
    them across the whole run, and is on by default in CoreText and HarfBuzz."""
    fr = ot.FeatureRecord()
    fr.FeatureTag = "calt"
    fr.Feature = ot.Feature()
    fr.Feature.FeatureParams = None
    fr.Feature.LookupListIndex = [lookup_index]
    fr.Feature.LookupCount = 1
    gsub.FeatureList.FeatureRecord.append(fr)
    gsub.FeatureList.FeatureCount = len(gsub.FeatureList.FeatureRecord)
    fi = len(gsub.FeatureList.FeatureRecord) - 1
    for sr in gsub.ScriptList.ScriptRecord:
        if sr.ScriptTag not in ("dev2", "deva", "DFLT"):
            continue
        systems = [sr.Script.DefaultLangSys] + [r.LangSys for r in sr.Script.LangSysRecord]
        for ls in systems:
            if ls is not None:
                ls.FeatureIndex.append(fi)
                ls.FeatureCount = len(ls.FeatureIndex)


def add_ligatures(font, plans, variants):
    """plans: {CoreText glyph sequence: base plan}; variants: {(sequence, step):
    (plan, outgoing step)}, step 0 being the base. A plan is (parts, budget,
    shift, headline stubs). Adds the composites, a GSUB ligature lookup that
    swaps each shaped sequence for its base composite, and the packing lookup
    that swaps a base for the variant the previous akṣara asks for."""
    from fontTools.otlLib.builder import buildCoverage, buildSingleSubstSubtable
    glyf, hmtx = font["glyf"], font["hmtx"]
    order = font.getGlyphOrder()
    index = {seq: n for n, seq in enumerate(sorted(plans))}
    names, new_names, shifts, outgoing = {}, [], {}, {}
    for (seq, step), ((parts, budget, shift, stubs), out) in sorted(
            variants.items(), key=lambda kv: (index[kv[0][0]], kv[0][1])):
        name = f"vaag.ak{index[seq]:05d}" + ("" if not step else f".p{step}" if step > 0 else f".m{-step}")
        g = Glyph()
        g.numberOfContours = -1
        g.components = [component(c, x, y, k) for c, x, y, k in parts]
        for a, b in stubs:
            add_bars(g, a, b, shift)
        glyf.glyphs[name] = g
        hmtx.metrics[name] = (round(budget), 0)
        names[seq, step] = name
        new_names.append(name)
        shifts[name] = -shift
        outgoing.setdefault(out, []).append(name)
    font.setGlyphOrder(order + new_names)
    for name in new_names:
        glyf[name].recalcBounds(glyf)
        hmtx.metrics[name] = (hmtx.metrics[name][0], getattr(glyf[name], "xMin", 0))
    gdef = font["GDEF"].table.GlyphClassDef.classDefs
    for name in new_names:
        gdef[name] = 1

    gsub = font["GSUB"].table
    rev = font.getReverseGlyphMap(rebuild=True)

    def add_lookup(ltype, subtables):
        lookup = ot.Lookup()
        lookup.LookupType, lookup.LookupFlag = ltype, 0
        lookup.SubTable = subtables
        lookup.SubTableCount = len(subtables)
        gsub.LookupList.Lookup.append(lookup)
        return len(gsub.LookupList.Lookup) - 1

    lookups = []
    base = {seq: names[seq, 0] for seq in plans}
    multi = {k: v for k, v in base.items() if len(k) > 1}
    single = {k[0]: v for k, v in base.items() if len(k) == 1}
    if multi:
        lookups.append(add_lookup(4, [buildLigatureSubstSubtable(multi)]))
    if single:
        lookups.append(add_lookup(1, [buildSingleSubstSubtable(single)]))
    # Packing: for each shift step, a single substitution base → variant, and a
    # chained rule "previous glyph hands over this step → apply it".
    rules = []
    for step in sorted({s for _, s in variants if s}):
        swap = {base[seq]: names[seq, s] for seq, s in variants if s == step}
        if not swap or not outgoing.get(step):
            continue
        sub = add_lookup(1, [buildSingleSubstSubtable(swap)])
        st = ot.ChainContextSubst()
        st.Format = 3
        st.BacktrackGlyphCount, st.BacktrackCoverage = 1, [buildCoverage(outgoing[step], rev)]
        st.InputGlyphCount, st.InputCoverage = 1, [buildCoverage(list(swap), rev)]
        st.LookAheadGlyphCount, st.LookAheadCoverage = 0, []
        rec = ot.SubstLookupRecord()
        rec.SequenceIndex, rec.LookupListIndex = 0, sub
        st.SubstCount, st.SubstLookupRecord = 1, [rec]
        rules.append(st)
    pack = add_lookup(6, rules) if rules else None
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
    # Run the composites as late as possible, after every other Devanagari
    # substitution.
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag in ("psts", "haln"):
            fr.Feature.LookupListIndex.extend(lookups)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    if pack is not None:
        add_calt(gsub, pack)
    (DIST / "composite_shifts.json").write_text(json.dumps(shifts))
    return len(plans), len(new_names) - len(plans)




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
                if family(name)[:7] == VISARGA:   # its top dot reaches the headline band
                    continue
                rec = DecomposingRecordingPen(self.gs)
                self.gs[name].draw(rec)
                pts += [(px + x, py + y) for _, args in rec.value for px, py in args]
            return headline_span(pts)

    natural = Design(100, ".nat")
    # Noto's own condensed design, for akṣaras too wide for their cells
    # (आ owns one cell but is nearly two consonants wide). Same height and
    # stroke weight, unlike squeezing the natural design.
    condensed = Design(62.5, ".cnd")

    plans, by_text, bad_weight = {}, {}, 0
    for text in candidates:
        glyphs = shaper.shape(text)
        if not glyphs:
            continue
        bad = misplaced(glyphs, text)
        bad_weight += corpus.get(text, 0) * bad
        seq = tuple(g["name"] for g in glyphs)
        by_text[text] = seq
        if seq in plans:
            continue
        # CoreText gives the composite the string index of its first glyph and
        # iTerm2 anchors it to that character's cell, so pre-shift the drawing
        # back by the same amount (see iterm_cells).
        shift = iterm_cells(text)[glyphs[0]["idx"]][1]
        budget = CELL * sum(cells_of_char(c) for c in text)
        plans[seq] = dict(text=text, budget=budget, shift=shift)

    def drawing(seq, step):
        """The akṣara drawn `step` shift steps left of its cells: natural
        width, left-aligned, narrowed only if it would run more than
        OVERHANG past its cells. Returns (plan, outgoing step)."""
        p = plans[seq]
        carried = step * PACK_Q
        gap = min(TRACK_MAX, TRACK_RATE * (carried - TRACK_FROM)) if carried > TRACK_FROM else 0
        budget, shift = p["budget"], p["shift"]
        room = budget + carried - gap + OVERHANG
        design = natural
        parts, adv = design.layout(p["text"])
        if room / max(adv * SCALE * XSCALE, 1) < CONDENSE_BELOW:
            design = condensed
            parts, adv = design.layout(p["text"])
        k = XSCALE * min(1.0, room / max(adv * SCALE * XSCALE, 1))
        width = adv * SCALE * k
        x0 = gap - carried
        comp = [(n + design.suffix, x0 + x * SCALE * k - shift, y * SCALE, k) for n, x, y in parts]
        design.used |= {n for n, _, _ in parts}
        # Short shirorekha stubs where the headline reaches the ink's edge, so
        # neighbours overlap a little instead of leaving a hairline.
        stubs = []
        span = design.head(parts)
        if span is not None and any(not is_sign(n) for n, _, _ in parts):
            ink_lo, ink_hi = design.ink(parts)
            to_x = lambda v: x0 + v * SCALE * k
            if gap:   # bridge back into the previous akṣara's headline (its ink
                # ends a little before its advance, and steps round by ±25)
                stubs.append((to_x(span[0]) - 120 - gap, to_x(span[0]) + 30))
            elif span[0] - ink_lo < 60:
                stubs.append((to_x(span[0]) - 40, to_x(span[0]) + 30))
            if ink_hi - span[1] < 60:
                stubs.append((to_x(span[1]) - 30, to_x(span[1]) + 40))
        out = round((carried - gap + budget - width) / PACK_Q)
        return (comp, budget, shift, stubs), max(-OVERHANG // PACK_Q, min(PACK_MAX // PACK_Q, out))

    # Walk the corpus the way the packing lookup will, collecting every
    # (akṣara, step) that occurs.
    variants = {}
    def variant(seq, step):
        if (seq, step) not in variants:
            variants[seq, step] = drawing(seq, step)
        return variants[seq, step][1]
    for seq in plans:
        variant(seq, 0)
    for word in corpus_words():
        step = 0
        for text in word_aksharas(word, stage1):
            seq = by_text.get(text)
            step = variant(seq, step) if seq else 0

    font = TTFont(stage1)
    order = font.getGlyphOrder()
    added = add_natural_glyphs(font, natural.font, natural.used, ".nat")
    added += add_natural_glyphs(font, condensed.font, condensed.used, ".cnd", bar=False)
    font.setGlyphOrder(order + added)
    n, nv = add_ligatures(font, plans, variants)
    font.save(OUT)
    total = sum(corpus.values())
    report = dict(distinct_aksharas=len(corpus), corpus_aksharas=total,
                  misplaced_by_iterm_without_composites=bad_weight, composites_added=n,
                  packing_variants=nv)
    (DIST / "ligate_report.json").write_text(json.dumps(report, indent=1))
    print(f"{len(corpus)} distinct akṣaras; {bad_weight}/{total} occurrences "
          f"({100 * bad_weight / total:.1f}%) would be misplaced by iTerm2 → "
          f"{n} natural composites added, {nv} packing variants")


if __name__ == "__main__":
    main()
