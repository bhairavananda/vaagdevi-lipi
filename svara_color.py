#!/usr/bin/env python3
"""Build Vaagdevi Svara: Vaagdevi with every akṣara coloured by its svara.

Colour can't come from the terminal: iTerm2 starts a new shaping run whenever
the text colour changes, which would cut the packing chain between akṣaras.
So the colour is in the font (COLR/CPAL): each composite that carries an
anudātta or svarita mark is drawn in that svara's colour, and every other
glyph keeps the terminal's text colour. Shaping is untouched.

    .venv/bin/python svara_color.py      (after build.py and ligate.py; or: make svara)

Writes dist/VaagdeviSvara-Regular.ttf.
"""

import sys
from pathlib import Path

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build import DIST, OUT  # noqa: E402

SVARA_OUT = DIST / "VaagdeviSvara-Regular.ttf"
FAMILY, PS = "Vaagdevi Svara", "VaagdeviSvara-Regular"

# (red, green, blue) in 0–1, matching the pāṭha renderer's legend.
COLORS = {
    "anudatta": (0.37, 0.66, 0.96),   # low: blue
    "svarita": (0.98, 0.52, 0.41),    # raised: salmon
    "both": (0.83, 0.53, 0.78),       # an akṣara carrying both marks: violet
}
ANUDATTA = ("uni0952",)
SVARITA = ("uni0951", "uni1CDA")       # svarita, and the double svarita (kampa)


def svara_of(font, name):
    """'anudatta', 'svarita', 'both' or None, from a composite's components."""
    glyph = font["glyf"][name]
    if not glyph.isComposite():
        return None
    comps = [c.glyphName.split(".")[0] for c in glyph.components]
    low = any(c in ANUDATTA for c in comps)
    high = any(c in SVARITA for c in comps)
    return "both" if low and high else "anudatta" if low else "svarita" if high else None


def main():
    font = TTFont(OUT)
    keys = list(COLORS)
    layers = {}
    for name in font.getGlyphOrder():
        if not name.startswith("vaag.ak"):
            continue
        kind = svara_of(font, name)
        if kind:
            # COLR v0: the glyph is drawn as one layer of itself in the svara's colour.
            layers[name] = [(name, keys.index(kind))]
    font["COLR"] = buildCOLR(layers, version=0)
    font["CPAL"] = buildCPAL([[(*COLORS[k], 1.0) for k in keys]])
    name = font["name"]
    for nid, value in ((1, FAMILY), (3, f"{FAMILY} Regular"), (4, f"{FAMILY} Regular"), (6, PS)):
        name.setName(value, nid, 3, 1, 0x409)
    font.save(SVARA_OUT)
    counts = {k: sum(1 for v in layers.values() if v[0][1] == keys.index(k)) for k in keys}
    print(f"built {SVARA_OUT.name}: {counts}")


if __name__ == "__main__":
    main()
