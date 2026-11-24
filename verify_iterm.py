#!/usr/bin/env python3
"""Check Vaagdevi the way iTerm2 will draw it: shape every distinct corpus word
with CoreText, re-place the glyphs with iTerm2's grid-alignment rule (taking
each composite's built-in shift into account), and count the words where
every glyph lands within half a pixel of where CoreText meant it to be."""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build import CELL, DIST, OUT, cells_of_char, corpus_words
from ligate import Shaper, iterm_x, TOLERANCE


def main():
    shaper = Shaper(OUT)
    shifts = json.loads((DIST / "composite_shifts.json").read_text())
    words = corpus_words()
    ok = width_ok = 0
    worst, err = Counter(), Counter()
    for w, n in words.items():
        glyphs = shaper.shape(w)
        # Ideal: each glyph's drawing lands at CoreText's position, minus the
        # shift baked into composites (they are meant to be re-anchored).
        got = iterm_x(glyphs, w)
        off = max((abs(a + shifts.get(g["name"], 0) - g["x"]) for a, g in zip(got, glyphs)), default=0)
        good = off <= TOLERANCE
        fits = abs(sum(g["adv"] for g in glyphs) - CELL * sum(cells_of_char(c) for c in w)) < 1
        ok += n * good
        width_ok += n * fits
        err[min(int(off // 100) * 100, 600)] += n
        if not good:
            worst[w] += n
    total = sum(words.values())
    print(f"{len(words)} distinct words, {total} occurrences")
    print(f"  width fits the grid:       {width_ok}/{total} ({100 * width_ok / total:.3f}%)")
    print(f"  drawn correctly in iTerm2: {ok}/{total} ({100 * ok / total:.3f}%)")
    print("  worst glyph offset per word (font units):", dict(sorted(err.items())))
    for w, n in worst.most_common(12):
        print(f"    {n:5}  {w}")


if __name__ == "__main__":
    main()
