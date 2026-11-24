# How Vaagdevi works

A Devanagari font isn't enough to get accented Vedic Sanskrit right in a
terminal. iTerm2 lays text out on a grid and moves glyphs after they've been
shaped. This page explains what iTerm2 does and how Vaagdevi is built to
survive it. The original design, with the measurements that led here, is in
[`DESIGN.md`](../DESIGN.md).

## 1. The cell grid

iTerm2 gives every character a number of cells before anything is drawn.
`probe.py` measured this in iTerm2 3.5.14 by printing test strings and asking
the terminal where the cursor ended up (`ESC [6n`). The results are in
`data/probe_results.json`.

| Characters | Unicode category | Cells |
|---|---|---|
| Consonants, independent vowels, digits, daṇḍa, avagraha | Lo, Nd, Po | 1 |
| Spacing vowel signs ा ि ी ो ौ, visarga ः | Mc | 1 |
| Virāma ्, ु ू ृ ॄ े ै, anusvāra ं, candrabindu ँ, svara ॒ ॑ | Mn | 0 |

So कि is 2 cells, क्ष is 2 (क ् ष), and ग्नि॑ is 3. Conjuncts are not grouped
into one cell.

## 2. What iTerm2 does to shaped glyphs

iTerm2 only shapes complex scripts with CoreText when **ligatures** are on for
the font. After shaping, it doesn't draw the glyphs where CoreText put them.
`CoreTextLineRenderingHelper.swift` re-places them:

1. sort the glyphs by the cell of the character each came from;
2. at each new cell, re-anchor to that cell's left edge, offset by how far
   the glyph sat past the previous glyph in CoreText's layout.

`iTermAttributedStringBuilder.m` adds one special case: a cell holding nothing
but a spacing vowel sign (ि ा ी ो ौ ः) keeps its cell on the grid but is drawn
together with the cell before it.

This works when glyphs come out in character order. Devanagari reorders on
purpose: ि is drawn *before* its consonant, reph is drawn *after* the consonant
it belongs to, and a half form sits under the next consonant. iTerm2's rule
then moves those glyphs by whole cells, so अग्नि came out as अ‾नि with the
half-ग hidden.

`ligate.iterm_x()` is a line-for-line port of this rule. `preview.py` draws text
with it, and `verify_iterm.py` checks every Ṛgveda word with it.

## 3. One glyph per akṣara

iTerm2 can't pull a single glyph apart. So Vaagdevi makes every akṣara one
composite glyph:

1. Split each word into akṣaras (orthographic syllables): any number of
   consonant + virāma, a consonant, its vowel signs or a final virāma, then
   marks. स्य॑ is one akṣara; in र्ऋ the virāma before an independent vowel
   ends the syllable, as CoreText draws it.
2. Shape the akṣara with CoreText using the cell-fitted font, to learn the
   exact glyph sequence iTerm2 will see.
3. Lay the akṣara out with Noto Sans Devanagari's own natural shaping, so
   marks, vowel signs and conjuncts sit where Noto's designers put them.
4. Bake that layout into one composite glyph whose advance is exactly the
   akṣara's cell budget.
5. Pre-shift the drawing by the offset iTerm2 will add: CoreText gives the
   composite the string index of its first glyph (for वि that's ि, the
   second cell).
6. Add a late GSUB ligature (in `psts`/`haln`) that swaps the shaped
   sequence for the composite.

About 7,700 composites cover every akṣara in the accented Ṛgveda, plus every
consonant with ि or reph and the common mark combinations.

## 4. Packing words

An akṣara's cell budget rarely matches its natural width. ता owns 2 cells but
is about 1.4 cells wide; स॒त्यश्चि॒त्रश्र॑वस्तमः owns 15 cells for 8 akṣaras.
Stretching each akṣara to fit gives every letter a different size; centring
it leaves uneven gaps inside words. Vaagdevi sets words as in print instead:

- Every akṣara is drawn at **one common size**: Noto's natural proportions,
  all 20% wider (`XSCALE`), so words fill more of their cells.
- Each akṣara is **left-aligned and pulled left by the slack carried from the
  akṣaras before it** in the word, so akṣaras touch as in print and the
  word's spare cells collect after it.
- A composite can't see its neighbours, so each akṣara gets **pre-shifted
  copies**, one per shift step of 50 units (`PACK_Q`) it actually takes in
  the Ṛgveda (about 42,000 copies). Each copy also records the slack it hands
  on. A chained contextual GSUB lookup picks the copy from the previous glyph.
- That lookup lives in **`calt`**, not with the Devanagari features. Shapers
  apply `psts`, `haln` and the rest one syllable at a time, so a rule there
  can't see the previous akṣara. `calt` runs after them across the whole run
  and is on by default in CoreText and HarfBuzz.
- A word may run up to half a cell (`OVERHANG`) into the space after it.
  An akṣara that would run further is narrowed, or uses Noto's **condensed**
  design (its `wdth` axis) rather than being squeezed.
- Once a word has carried more than ¾ cell of slack (`TRACK_FROM`), each later
  akṣara keeps a small gap before it, up to 0.4 cell, bridged by the
  shirorekha. A slack-heavy word reads slightly spread instead of leaving a
  hole after it.

The space between words is ASCII, so iTerm2 draws it with the main font in a
separate run. Packing restarts at every word, and spacing between words
can't be evened out.

## 5. Svara on fixed lines

- **Anudātta** hangs from one fixed low line, just below ु and ृ, so ई॒ळे॒ reads
  level. Only ink that reaches below the line (ॄ) pushes it lower.
- **Svarita** stands on one fixed line above the headline. It may meet the
  ि/ी arc or a reph, as in traditional typesetting. Other ink at that height
  (ं) lifts it just clear. Its stroke is 30% taller than Noto's, so ज॑ can't
  be mistaken for जं.

## 6. Line spacing

iTerm2's row height comes from the main font: Monaco's line is 1,333 units
(ascent 1,000, descent 250, gap 83). Vaagdevi's ink reaches about 1,350 up
(svarita) and −450 down (anudātta under ु), so at 100% a svarita can touch
the anudātta of the line above. The profile's vertical spacing should be
130% (`LINE_SPACING` in `build.py`, which `make dev` writes into the test
profiles and `preview.py` uses for its rows).

## 7. Svara colours

Vaagdevi Svara (`svara_color.py`) is the same font plus COLR/CPAL tables.
Every composite carrying an anudātta is drawn as one layer of itself in blue,
every one carrying a svarita or kampa in salmon, one carrying both in violet.
Other glyphs keep the terminal's text colour.

ANSI colour can't do this. iTerm2's `iTermAttributedStringBuilder.m`
(`shouldSegmentWithAttributes`) starts a new attributed string whenever the
foreground colour changes, and each one is shaped on its own, which would
cut the packing chain at every colour change. Udātta and pracaya are both
unmarked and differ only by context across words, so the font can't tell
them apart.

## 8. Things that would otherwise break the grid

- **GPOS advance changes** (kern, dist) are zeroed. Mark placement stays.
- **Reph and below-base rakāra** owe their र a cell. A contextual GSUB rule
  adds a cell of headline filler after them, except where Noto reuses the
  reph shape inside ई and ऋ.
- **The dotted circle** (U+25CC) is left out. Shapers insert it when a mark
  is typed out of order (॒ before ः), and it would cost a cell.
- **Side bearings** of the natural outlines equal their `xMin`. Apple's
  renderer places TrueType outlines from the stored bearing, so a wrong value
  shifts the glyph.

## 9. Verification

| Check | Result on the accented Ṛgveda (457,202 word occurrences) |
|---|---|
| `verify.py`: HarfBuzz advance = cells iTerm2 gives | 457,201 (100.000%) |
| `verify_iterm.py`: CoreText + iTerm2 placement = intended position | 457,198 (99.999%) |

The misses are typos in the source text, such as doubled vowel signs, and one
word (पूर्वे॑भि॒र्ऋषि॑भि॒रीड्यो॒) where HarfBuzz forms र्ऋ differently from CoreText.
Apart from daṇḍas and those typos, every word is packed as one glyph per
akṣara.
