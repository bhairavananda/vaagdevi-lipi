#!/usr/bin/env python3
"""Shape every Ṛgveda word with the built Vaagdevi (HarfBuzz) and check that
its total advance equals the cells iTerm2 will give it (DESIGN.md §3)."""

import sys
from collections import Counter
from pathlib import Path

import uharfbuzz as hb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CELL, OUT, cells_of_char, corpus_words


def main():
    font = hb.Font(hb.Face(OUT.read_bytes()))
    bad, total, worst = 0, 0, Counter()
    for word, n in corpus_words().items():
        buf = hb.Buffer()
        buf.add_str(word)
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        got = sum(p.x_advance for p in buf.glyph_positions)
        want = CELL * sum(cells_of_char(c) for c in word)
        total += n
        if got != want:
            bad += n
            worst[(word, want // CELL, got / CELL)] += n
    print(f"{total - bad}/{total} words fit their cells exactly ({100 * (total - bad) / total:.3f}%)")
    for (w, want, got), n in worst.most_common(15):
        print(f"  {n:5}  {w}  want {want} cells, got {got:g}")


if __name__ == "__main__":
    main()
