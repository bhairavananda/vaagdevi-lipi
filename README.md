# Vaagdevi (वाग्देवी)

A terminal font for **accented Vedic Sanskrit in iTerm2**. Devanagari akṣaras,
conjuncts, and svara marks (anudātta ॒, svarita ॑, kampa, pluta) render
correctly on the terminal grid, and every column stays aligned.

```
अ॒ग्निमी॑ळे पु॒रोहि॑तं य॒ज्ञस्य॑ दे॒वमृ॒त्विज॑म् ।
होता॑रं रत्न॒धात॑मम् ॥
```

Vaagdevi is a **companion font**. Keep your usual monospace font (Monaco,
Menlo, SF Mono) for ASCII and set Vaagdevi as iTerm2's non-ASCII font.

## Install

1. Build it (macOS, Homebrew Python 3.12 or newer):

   ```
   make venv
   make
   ```

   This writes `dist/Vaagdevi-Regular.ttf`.

2. Copy `dist/Vaagdevi-Regular.ttf` to `~/Library/Fonts/`.

3. In **iTerm2 → Settings → Profiles → Text**:
   - turn on **Use a different font for non-ASCII text** and choose **Vaagdevi**,
     at the same size as your main font;
   - turn on **ligatures** for the non-ASCII font.

The cell width is 0.6 em, which matches Monaco, Menlo and most terminal fonts.

## How it works

Getting Devanagari right in a terminal needs more than a font with the
glyphs, because of how iTerm2 draws text.

1. **The cell grid.** iTerm2 gives each letter or spacing vowel sign
   (ा ि ी ो ौ ः) one cell, and zero-width marks (् ु ृ े ं ॒ ॑) share the cell
   before them. Measured with `probe.py`; results in `data/probe_results.json`.

2. **iTerm2 re-places glyphs.** After CoreText shapes a line, iTerm2 moves
   each glyph to the cell of the character it came from
   (`CoreTextLineRenderingHelper.swift`). It also draws a lone spacing vowel
   sign together with the previous cell (`iTermAttributedStringBuilder.m`).
   Devanagari draws some glyphs out of character order (ि before its
   consonant, reph after it), so this pulls akṣaras apart.

3. **One glyph per akṣara.** Vaagdevi turns every multi-glyph akṣara into a
   single composite glyph, drawn from Noto Sans Devanagari's own layout of
   that akṣara. iTerm2 can't pull a single glyph apart. Each composite is
   pre-shifted by exactly the amount iTerm2 will move it. There are about
   4,800 composites: every akṣara in the Ṛgveda, plus every consonant with ि
   or reph and the svara marks.

4. **Samānam.** Every akṣara keeps Noto's natural proportions at one common
   size. Space left over in a cell becomes continuous shirorekha, so words
   read as one line. Letters too wide for their cells (आ, औ) use Noto's own
   condensed design rather than being squeezed.

5. **Svara on fixed lines.** Every anudātta hangs at one fixed low line and
   every svarita stands on one fixed line above the headline, so a run of
   them reads level. A mark only moves if it would collide with ink (ॄ below,
   ं above).

## Checks

| Script | What it checks |
|---|---|
| `verify.py` | HarfBuzz: every Ṛgveda word takes exactly the cells iTerm2 gives it |
| `verify_iterm.py` | CoreText plus a port of iTerm2's glyph placement: every glyph lands where CoreText meant it to |
| `preview.py out.png "text"` | Draws text exactly as iTerm2 will, without needing a screenshot |
| `probe.py` | Run inside iTerm2: measures how many cells it gives each test string |

Current result: **457,200 of 457,202** Ṛgveda word occurrences are drawn
correctly. The two misses are typos in the source text (doubled vowel signs).

## Development

`make dev` builds the font and installs it into iTerm2 under a fresh name
(`Vaagdevi Dev <time>`). It points a separate **Vaagdevi Test** profile at
it, which inherits everything from your default profile. macOS caches fonts
by name, so reusing a name would leave a running iTerm2 drawing the old
build.

`DESIGN.md` is the original design, including the Phase 0 measurements of
iTerm2. This README describes how the font ended up working.

## Limits

- **iTerm2 only** (3.5, macOS). Other terminals place glyphs differently.
- **Akṣaras outside the Ṛgveda and the generated set** fall back to per-glyph
  fitting. They're drawn in the right cells but look less natural.
- **Words have a little air between akṣaras,** because every spacing vowel
  sign must take a whole terminal cell. The shirorekha bridges the gaps.
- **The tallest stacks** (svarita over the ि arc, anudātta under ु) can reach
  about half a pixel beyond a 12 pt line.

## Sources and license

Vaagdevi is built from **Noto Sans Devanagari** and **Noto Sans Mono** (The
Noto Project Authors), both under the SIL Open Font License 1.1. Vaagdevi is
released under the same license: see `OFL.txt`, with the changes in
`FONTLOG.txt`. `data/rigveda_words.tsv` is the word list of the accented
Ṛgveda (public domain).
