#!/usr/bin/env python3
"""Build Vaagdevi-Regular.ttf: Noto Sans Devanagari fitted to a 600-unit cell
grid, merged with Noto Sans Mono. See DESIGN.md.

    .venv/bin/python build.py      (or: make)

Steps
  1. Instance Noto Sans Devanagari (wght WGHT, wdth WDTH) and keep only the
     Devanagari / Vedic ranges.
  2. Shape every akṣara in the Ṛgveda corpus with HarfBuzz and work out how
     many cells each glyph must take (iTerm2 gives 1 cell to Lo/Mc/Nd/Po
     characters and 0 to Mn), so every akṣara's advance equals its budget.
  3. Redraw each glyph into its cells: scale to 0.9, raise it so the
     headline sits near the cap height, fit it horizontally, and extend
     the headline where a narrow glyph has to fill a whole cell. Apply the
     same mapping to its GPOS anchors so the svara marks follow.
  4. Remove GPOS adjustments that change advances (kern, dist), which
     would break the cell grid.
  5. Merge with Noto Sans Mono, set names and metrics, and save.
"""

import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import uharfbuzz as hb
from fontTools.merge import Merger
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
DEVA_SRC = HERE / "sources/noto-sans-devanagari/NotoSansDevanagari[wdth,wght].ttf"
MONO_SRC = HERE / "sources/noto-sans-mono/NotoSansMono-Regular.ttf"
WORDS = HERE / "data/rigveda_words.tsv"
DIST = HERE / "dist"
OUT = DIST / "Vaagdevi-Regular.ttf"
REPORT = DIST / "build_report.json"

CELL = 600
WDTH = 100
WGHT = 500             # a touch heavier than Regular, to match Monaco's stroke
SCALE = 1.00           # Devanagari at Noto's full design size
RAISE = 136            # lifts the headline to Monaco's cap height (758 units)
HEADLINE = (548, 622)  # y-band of the shirorekha in Noto Devanagari (unscaled)

# U+25CC (dotted circle) is left out on purpose: shapers insert it for
# out-of-order marks (॒ before ः in some sources), and it would cost a cell.
DEVA_RANGES = [(0x0900, 0x097F), (0x1CD0, 0x1CFF), (0xA8E0, 0xA8FF), (0x200C, 0x200D)]


def cells_of_char(c):
    """How many cells iTerm2 gives a character (measured in Phase 0)."""
    cat = unicodedata.category(c)
    if cat in ("Mn", "Me", "Cf"):
        return 0
    return 1


# --- 1. Source Devanagari ---------------------------------------------------------

def load_devanagari(wdth=WDTH):
    f = instantiateVariableFont(TTFont(DEVA_SRC), {"wdth": wdth, "wght": WGHT})
    opts = Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = True
    opts.hinting = False
    opts.layout_scripts = ["dev2", "deva", "DFLT"]
    unicodes = [u for a, b in DEVA_RANGES for u in range(a, b + 1)]
    sub = Subsetter(opts)
    sub.populate(unicodes=unicodes)
    sub.subset(f)
    return f


# --- 2. Cell budgets from the corpus ---------------------------------------------

def corpus_words():
    """Every distinct word of the accented Ṛgveda with its count
    (data/rigveda_words.tsv), plus forms the renderers produce."""
    words = Counter()
    for line in WORDS.open(encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        w, n = line.rstrip("\n").split("\t")
        words[w] += int(n)
    for w in "॥ १ ॥ २ ३ ४ ५ ६ ७ ८ ९ ० । स्व१॒॑ यो॒३॒॑ सी३ दे॒वाँ इति॑ इति॒".split():
        words[w] += 1
    return words


def solve_cells(font_bytes, font):
    """Shape the corpus and decide each glyph's cell count."""
    face = hb.Face(font_bytes)
    hbfont = hb.Font(face)
    order = font.getGlyphOrder()
    gdef = font["GDEF"].table.GlyphClassDef.classDefs if "GDEF" in font else {}
    hmtx = font["hmtx"]

    clusters = Counter()
    for text, weight in corpus_words().items():
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(hbfont, buf, {})
        infos = buf.glyph_infos
        # Group glyphs by HarfBuzz cluster, then map clusters back to text.
        starts = sorted({i.cluster for i in infos})
        bounds = {s: (starts[k + 1] if k + 1 < len(starts) else len(text))
                  for k, s in enumerate(starts)}
        groups = defaultdict(list)
        for i in infos:
            groups[i.cluster].append(order[i.codepoint])
        for s, gl in groups.items():
            chars = text[s:bounds[s]]
            budget = sum(cells_of_char(c) for c in chars)
            clusters[(tuple(gl), budget, chars)] += weight

    def is_mark(g):
        return gdef.get(g) == 3 or hmtx[g][0] == 0

    cells = {}
    for g in order:
        if is_mark(g) and not is_reph(g):
            cells[g] = 0
    votes = defaultdict(Counter)
    changed = True
    while changed:
        changed = False
        for (gl, budget, _), n in clusters.items():
            unknown = [g for g in gl if g not in cells]
            if len(set(unknown)) == 1 and gl.count(unknown[0]) == len(unknown):
                rest = budget - sum(cells[g] for g in gl if g in cells)
                if rest >= 0 and rest % len(unknown) == 0:
                    votes[unknown[0]][rest // len(unknown)] += n
        for g, vs in votes.items():
            if g not in cells:
                cells[g] = vs.most_common(1)[0][0]
                changed = True
        votes.clear()

    # Anything never seen in the corpus: round its own advance.
    for g in order:
        if g not in cells:
            cells[g] = 0 if is_mark(g) else max(1, round(SCALE * hmtx[g][0] / CELL))

    # Check: how many corpus clusters now add up?
    bad = Counter()
    for (gl, budget, chars), n in clusters.items():
        if sum(cells[g] for g in gl) != budget:
            bad[(chars, budget, " ".join(gl), sum(cells[g] for g in gl))] += n
    return cells, clusters, bad


def is_reph(g):
    """Zero-width marks that still owe the र a cell: reph (र्) above, and the
    below-base rakāra (्र) that conjuncts like ष्ट्र leave as a separate mark."""
    base = g.split(".")[0]
    return ("0930094D" in base and not base.startswith("uni093F")) or base == "uni094D0930"


# Noto draws ई as इ + the reph glyph, and र + ृ as ऋ + reph. There the reph
# is part of a 1-cell letter and must not get a filler.
NOT_A_REPH_AFTER = ("uni0907", "uni090B")


# --- 3. Redrawing glyphs into cells -------------------------------------------------

def stem_span(rec, y=300):
    """x-range where the outline crosses height y: the vowel sign's vertical stem.

    Curves are followed through their control points, which is close enough to
    find a straight stem.
    """
    xs, cur, start = [], None, None

    def seg(p0, p1):
        (x0, y0), (x1, y1) = p0, p1
        if (y0 - y) * (y1 - y) < 0:
            xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))

    for op, args in rec.value:
        if op == "moveTo":
            cur = start = args[0]
        elif op in ("lineTo", "qCurveTo", "curveTo"):
            for pt in args:
                if pt is None:
                    continue
                seg(cur, pt)
                cur = pt
        elif op in ("closePath", "endPath") and cur and start:
            seg(cur, start)
            cur = start
    return (min(xs), max(xs)) if xs else None


def make_xmap(kind, bounds, adv, target, stem):
    """A function x → x' that fits a glyph's design box into `target` units."""
    if bounds is None:
        return lambda x: x * target / max(adv, 1)
    _, _, x1, _ = bounds
    if kind == "prebase" and stem:            # ि: stem to the right edge, arc reaches on
        s0, s1 = stem
        shift = target - 70 - s1 * SCALE
        return lambda x: x * SCALE + shift
    if kind == "half":                         # half form: lean on the next consonant
        shift = target - 40 - x1 * SCALE
        return lambda x: x * SCALE + shift
    if kind == "postbase" and stem:           # ा ी ो ौ: stem to the left edge
        s0, s1 = stem
        shift = 70 - s0 * SCALE
        return lambda x: x * SCALE + shift
    # Samānam: natural proportions at one common size; narrow only a glyph
    # that is wider than its cells (see ligate.py).
    k = min(1.0, target / max(adv * SCALE, 1))
    width = adv * SCALE * k
    shift = (target - width) / 2
    return lambda x: x * SCALE * k + shift


def classify(name):
    base = name.split(".")[0]
    if base.startswith("uni093F"):                       # ि and ि+reph: pre-base
        return "prebase"
    if base in ("uni093E", "uni0940", "uni094B", "uni094C"):   # ा ी ो ौ: post-base
        return "postbase"
    if base.endswith("094D") and len(base) == 11:        # half form, e.g. uni0917094D
        return "half"
    return "normal"


def redraw(font, cells):
    glyf, hmtx = font["glyf"], font["hmtx"]
    gs = font.getGlyphSet()
    maps = {}
    for name in font.getGlyphOrder():
        if name == ".notdef":
            continue
        adv, lsb = hmtx[name]
        target = cells[name] * CELL
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(rec)
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        bounds = bp.bounds
        if target == 0:
            # Marks keep their origin. Some attach through anchors; others
            # (ं after ा) rely on Noto drawing them back over the previous
            # letter. Marks that overhang their cell are handled in ligate.py.
            xmap = (lambda k: (lambda x: x * k))(SCALE)
            maps[name] = xmap
            new_adv = 0
            fill = None
        else:
            kind = classify(name)
            stem = stem_span(rec) if kind in ("prebase", "postbase") else None
            xmap = make_xmap(kind, bounds, adv, target, stem)
            maps[name] = xmap
            new_adv = target
            fill = None
            span = headline_span([pt for _, args in rec.value for pt in args])
            if bounds and span and has_headline(rec) and not is_sign(name):
                # Extend only from where the glyph's own headline ends, and only
                # on a side where the headline reaches the ink's edge (अ's
                # headline stops short of its curved left side: no stub there).
                left = xmap(span[0]) if span[0] - bounds[0] < 60 else None
                right = xmap(span[1]) if bounds[2] - span[1] < 60 else None
                fill = (left, right)
        pen = TTGlyphPen(None)
        for op, args in rec.value:
            pts = [(round(xmap(x)), round(y * SCALE + RAISE)) for x, y in args]
            getattr(pen, op)(*pts)
        if fill and target:
            y0 = round(HEADLINE[0] * SCALE + RAISE)
            y1 = round(HEADLINE[1] * SCALE + RAISE)
            # Extend the headline from the cell's left edge and to its right
            # edge wherever the ink stops short, so the shirorekha runs on
            # unbroken between the cells of a word.
            for a, b in ((0, None if fill[0] is None else fill[0] + 8),
                         (None if fill[1] is None else fill[1] - 8, target)):
                if a is None or b is None:
                    continue
                if b - a > 12 and a < target and b > 0:
                    pen.moveTo((round(a), y0)); pen.lineTo((round(a), y1))
                    pen.lineTo((round(b), y1)); pen.lineTo((round(b), y0)); pen.closePath()
        glyf[name] = pen.glyph()
        glyf[name].recalcBounds(glyf)
        hmtx[name] = (new_adv, glyf[name].xMin if hasattr(glyf[name], "xMin") else 0)
    return maps


def is_sign(name):
    """Daṇḍas, digits, avagraha, oṃ, abbreviation sign: no shirorekha to extend."""
    base = name.split(".")[0]
    return base[:7] in ("uni0964", "uni0965", "uni0966", "uni0967", "uni0968", "uni0969",
                        "uni096A", "uni096B", "uni096C", "uni096D", "uni096E", "uni096F",
                        "uni093D", "uni0950", "uni0970", "uni0971")


def headline_span(points):
    """x-range covered by the shirorekha: points inside the headline band."""
    xs = [x for x, y in points if HEADLINE[0] - 10 <= y <= HEADLINE[1] + 10]
    return (min(xs), max(xs)) if xs else None


def has_headline(rec):
    """True if the outline reaches into the headline band at all."""
    ys = [y for op, args in rec.value for x, y in args]
    return bool(ys) and max(ys) >= HEADLINE[0] and min(ys) < HEADLINE[0] - 150


def transform_anchors(font, maps):
    """Apply each glyph's x-map (and the y scale/raise) to its GPOS anchors."""
    def fix(anchor, glyph):
        if anchor is None or glyph not in maps:
            return
        anchor.XCoordinate = round(maps[glyph](anchor.XCoordinate))
        anchor.YCoordinate = round(anchor.YCoordinate * SCALE + RAISE)
        if hasattr(anchor, "XDeviceTable"):
            anchor.XDeviceTable = anchor.YDeviceTable = None
        anchor.Format = 1

    for lookup in font["GPOS"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            st = st.ExtSubTable if lookup.LookupType == 9 else st
            t = st.LookupType if lookup.LookupType == 9 else lookup.LookupType
            if t == 4:
                for g, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
                    fix(rec.MarkAnchor, g)
                for g, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                    for a in rec.BaseAnchor:
                        fix(a, g)
            elif t == 5:
                for g, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
                    fix(rec.MarkAnchor, g)
                for g, lig in zip(st.LigatureCoverage.glyphs, st.LigatureArray.LigatureAttach):
                    for comp in lig.ComponentRecord:
                        for a in comp.LigatureAnchor:
                            fix(a, g)
            elif t == 6:
                for g, rec in zip(st.Mark1Coverage.glyphs, st.Mark1Array.MarkRecord):
                    fix(rec.MarkAnchor, g)
                for g, rec in zip(st.Mark2Coverage.glyphs, st.Mark2Array.Mark2Record):
                    for a in rec.Mark2Anchor:
                        fix(a, g)


def add_reph_fill(font, extra):
    """Give reph its cell without breaking it off its consonant.

    Reph stays a zero-width mark attached above the consonant. A GSUB rule
    then inserts `vaag.fill` glyphs after it: each is one cell of plain
    headline, so र्क takes its 2 cells with the shirorekha running on
    instead of a gap.
    """
    from fontTools.otlLib.builder import buildMultipleSubstSubtable
    from fontTools.ttLib.tables import otTables as ot
    if not extra:
        return
    order = font.getGlyphOrder()
    font.setGlyphOrder(order + ["vaag.fill"])
    y0 = round(HEADLINE[0] * SCALE + RAISE)
    y1 = round(HEADLINE[1] * SCALE + RAISE)
    pen = TTGlyphPen(None)
    pen.moveTo((0, y0)); pen.lineTo((0, y1)); pen.lineTo((CELL, y1)); pen.lineTo((CELL, y0))
    pen.closePath()
    font["glyf"]["vaag.fill"] = pen.glyph()
    font["hmtx"]["vaag.fill"] = (CELL, 0)
    font["GDEF"].table.GlyphClassDef.classDefs["vaag.fill"] = 1
    from fontTools.otlLib.builder import buildCoverage
    glyph_map = font.getReverseGlyphMap()
    gsub = font["GSUB"].table

    def add(lookup):
        gsub.LookupList.Lookup.append(lookup)
        gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
        return len(gsub.LookupList.Lookup) - 1

    multi = ot.Lookup()
    multi.LookupType, multi.LookupFlag = 2, 0
    multi.SubTable = [buildMultipleSubstSubtable({g: [g] + ["vaag.fill"] * n
                                                  for g, n in extra.items()})]
    multi.SubTableCount = 1
    multi_idx = add(multi)

    def chain(backtrack, with_subst):
        st = ot.ChainContextSubst()
        st.Format = 3
        st.BacktrackGlyphCount = len(backtrack)
        st.BacktrackCoverage = [buildCoverage(b, glyph_map) for b in backtrack]
        st.InputGlyphCount = 1
        st.InputCoverage = [buildCoverage(list(extra), glyph_map)]
        st.LookAheadGlyphCount = 0
        st.LookAheadCoverage = []
        recs = []
        if with_subst:
            r = ot.SubstLookupRecord()
            r.SequenceIndex, r.LookupListIndex = 0, multi_idx
            recs = [r]
        st.SubstCount = len(recs)
        st.SubstLookupRecord = recs
        return st

    letters = [g for g in font.getGlyphOrder() if g.split(".")[0] in NOT_A_REPH_AFTER]
    ctx = ot.Lookup()
    ctx.LookupType, ctx.LookupFlag = 6, 0
    # First subtable matches reph after इ/ऋ and does nothing ("ignore");
    # the second adds the filler everywhere else.
    ctx.SubTable = [chain([letters], False), chain([], True)]
    ctx.SubTableCount = 2
    idx = add(ctx)
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "psts":
            fr.Feature.LookupListIndex.append(idx)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)


def drop_advance_changes(font):
    """Make sure no GPOS rule changes an advance after the cell fitting."""
    gpos = font["GPOS"].table
    # Single and pair positioning stay, because Noto uses them to fine-tune
    # mark placement. Only their advance changes go, and placements are scaled
    # like the outlines.
    def fix(vr):
        if vr is None:
            return
        if getattr(vr, "XAdvance", None):
            vr.XAdvance = 0
        if getattr(vr, "XPlacement", None):
            vr.XPlacement = round(vr.XPlacement * SCALE)
        if getattr(vr, "YPlacement", None):
            vr.YPlacement = round(vr.YPlacement * SCALE)

    for lookup in gpos.LookupList.Lookup:
        for st in lookup.SubTable:
            s = st.ExtSubTable if lookup.LookupType == 9 else st
            t = s.LookupType if lookup.LookupType == 9 else lookup.LookupType
            if t == 1:
                if s.Format == 1:
                    fix(s.Value)
                else:
                    for v in s.Value:
                        fix(v)
            elif t == 2:
                if s.Format == 1:
                    for ps in s.PairSet:
                        for pvr in ps.PairValueRecord:
                            fix(pvr.Value1); fix(pvr.Value2)
                else:
                    for c1 in s.Class1Record:
                        for c2 in c1.Class2Record:
                            fix(c2.Value1); fix(c2.Value2)


# --- 4. Merge and finish ------------------------------------------------------------

def finish(deva, tmp_deva):
    deva.save(tmp_deva)
    mono = TTFont(MONO_SRC)
    for t in ("fpgm", "prep", "cvt ", "gasp"):
        if t in mono:
            del mono[t]
    tmp_mono = DIST / ".mono.ttf"
    mono.save(tmp_mono)
    font = Merger().merge([str(tmp_mono), str(tmp_deva)])
    name = font["name"]
    for rec in list(name.names):
        if rec.nameID in (1, 3, 4, 6, 16, 17):
            name.removeNames(nameID=rec.nameID)
    name.setName("Vaagdevi", 1, 3, 1, 0x409)
    name.setName("Regular", 2, 3, 1, 0x409)
    name.setName("Vaagdevi Regular 0.1", 3, 3, 1, 0x409)
    name.setName("Vaagdevi Regular", 4, 3, 1, 0x409)
    name.setName("Version 0.100", 5, 3, 1, 0x409)
    name.setName("Vaagdevi-Regular", 6, 3, 1, 0x409)
    name.setName("Vaagdevi is built from Noto Sans Mono and Noto Sans Devanagari "
                 "(SIL OFL 1.1).", 10, 3, 1, 0x409)
    font["post"].isFixedPitch = 1
    os2 = font["OS/2"]
    os2.panose.bProportion = 9
    os2.xAvgCharWidth = CELL
    # Line metrics close to Monaco's, the ASCII font in the user's iTerm2.
    font["hhea"].ascent, font["hhea"].descent, font["hhea"].lineGap = 1000, -250, 83
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = 1000, -250, 83
    os2.usWinAscent, os2.usWinDescent = 1100, 330
    font.save(OUT)
    tmp_mono.unlink()
    return font


def main():
    deva = load_devanagari()
    DIST.mkdir(exist_ok=True)
    tmp = DIST / ".deva.ttf"
    deva.save(tmp)
    cells, clusters, bad = solve_cells(tmp.read_bytes(), deva)
    extra = {g: n for g, n in cells.items() if is_reph(g) and n > 0}
    for g in extra:
        cells[g] = 0
    maps = redraw(deva, cells)
    transform_anchors(deva, maps)
    add_reph_fill(deva, extra)
    drop_advance_changes(deva)
    finish(deva, tmp)
    tmp.unlink()
    total = sum(clusters.values())
    nbad = sum(bad.values())
    REPORT.write_text(json.dumps({
        "clusters": total, "distinct": len(clusters),
        "budget_mismatch": nbad,
        "worst": [dict(chars=c, budget=b, glyphs=g, got=x, count=n)
                  for (c, b, g, x), n in bad.most_common(40)],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"built {OUT.name}: {total} akṣara clusters ({len(clusters)} distinct), "
          f"{nbad} with a width mismatch ({100 * nbad / total:.2f}%)")


if __name__ == "__main__":
    main()
