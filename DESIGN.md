# Vaagdevi (वाग्देवी): design

A monospaced terminal font that renders accented Vedic Sanskrit correctly in
**iTerm2**. One font file covers Devanagari with svara marks and Latin with IAST,
so you select a single font in iTerm2 and accented mantras render properly.

Status: the original design and the Phase 0 measurements of iTerm2 (§2.2).
The built font changed in places: one composite glyph per akṣara and svara on
fixed lines. README.md describes how it ended up working.

---

## 1. Goal and scope

**Goal:** `python3 tools/render_pss.py 1.1.1` in iTerm2 shows:
- correct akṣaras: कि with ि before क, conjuncts like क्ष and ज्ञ, reph, rakāra;
- ॒ and ॑ sitting under and over the right akṣara;
- columns that line up, so the IAST line and the contour strip under a
  Devanagari line stay aligned.

**In scope:**
- iTerm2 3.5 on macOS (you have 3.5.14), with one profile setting changed.
- The Devanagari block, the Vedic marks the Ṛgveda corpus uses (॑ ॒ १ ३ ँ ऽ ळ),
  the Vedic Extensions that Noto covers, ASCII, and full IAST.

**Out of scope:** other terminals, Windows and Linux, proportional use (in an
editor, use Noto Sans Devanagari or Balambika instead), and Devanagari
Extended beyond what the sources already cover.

---

## 2. Why this is hard: how iTerm2 draws text

A terminal is a grid. Before anything is drawn, iTerm2 gives every character
a number of cells (0, 1 or 2). Devanagari breaks the "one character, one box"
assumption in three ways:

| Problem | Example | Needs |
|---|---|---|
| Reordering | कि is stored क + ि but drawn ि क | a shaping engine |
| Conjuncts | क + ् + ष draws as one glyph क्ष | the font's GSUB rules plus shaping |
| Mark placement | ॒ under ग्नि, ॑ over मी | the font's GPOS anchors plus shaping |

iTerm2 only runs a shaping engine (Apple's CoreText) when **Settings → Profiles
→ Text → "Use ligatures"** is on. With it off, iTerm2 draws one character per
cell and no font can fix reordering. **So Vaagdevi needs ligatures turned on.**
This is the one setting the user has to change.

With ligatures on, CoreText shapes each run of same-styled text and draws the
glyphs at the positions the font gives them, starting from the run's first
cell. The text renders correctly, but it lines up with the grid only if **the
shaped glyphs' total width equals the cells iTerm2 gave the run**. If it
doesn't:
- text after a color change starts in the wrong place;
- the cursor lands in the middle of glyphs;
- the columns after a Devanagari word drift.

**Making those two widths always match is the core of this design.**

### 2.1 Unknowns we measure first (Phase 0)

The design depends on facts about iTerm2 that aren't documented, so we
measure them instead of guessing:

| # | Question | Why it matters |
|---|---|---|
| U1 | How many cells does iTerm2 give each Devanagari character? Are spacing vowel signs (ा ि ी ो ौ ः, category Mc) 1 cell or 0? | Sets every glyph's target width |
| U2 | Does iTerm2 group a whole grapheme cluster (an akṣara, or a conjunct under Unicode 15.1 rule GB9c) into one cell? | If yes, the width model changes completely (see §3.2) |
| U3 | Does "Unicode version 9+ widths" change U1 or U2? | Picks the iTerm2 setting we document |
| U4 | Are glyphs that spill past their cell clipped? | Decides how reph and wide conjuncts may be drawn |

A probe script settles U1 to U3 automatically. It prints each test string,
then asks the terminal where the cursor is (the `ESC [6n` report), which gives
the cell count iTerm2 actually used. U4 needs a screenshot from you.

### 2.2 Phase 0 results (2026-11-23, iTerm2 3.5.14, profile Gruvbox Dark)

**Your current settings,** read from iTerm2's preferences: Monaco 12, no
separate non-ASCII font, ligatures off, default Unicode version, spacing 1.0,
bold font on. The design keeps all of them except the ones listed in §6.

**The probe answered U1 to U3** (`probe.py`, raw data in `probe_results.json`):

- **U1: per character, exactly Model A.** Lo, Nd, Po and Mc characters (including
  ा ि ी ो ौ ः) take 1 cell. Mn characters (् ु ू ृ े ै ं ँ ॒ ॑) take 0 cells and
  share the cell before them.
- **U2: no grapheme-cluster grouping.** क्ष, र्क and क्र are each 2 cells, and
  ग्नि॑ is 3. RV 1.1.1's first half-verse is 72 characters in 47 cells.
- **U3:** Unicode version is left at the default. Model A holds there, so no
  change is needed.
- **U4** (clipping) and how per-cell drawing looks with ligatures off still need
  a screenshot.

**What this means for your settings.** iTerm2 sizes cells from the ASCII font,
which is Monaco 12. Monaco is 0.6 em wide (1229/2048), and Vaagdevi's 600/1000
cell matches that, so Vaagdevi can serve as the **non-ASCII font** next to
Monaco. Monaco also fixes the line height: about 1.53 em (ascent 2500 plus
descent 640, over 2048). So Vaagdevi's tallest Vedic stack (॑ above the
headline) and deepest (॒ under ृ) must fit inside Monaco's ascent and descent,
not Vaagdevi's own.

---

## 3. The width model

### 3.1 Model A: per character (the expected result)

iTerm2 uses Unicode general categories for width, like `wcwidth`:

| Characters | Category | Cells |
|---|---|---|
| Consonants, independent vowels, digits, daṇḍa, avagraha | Lo, Nd, Po | 1 |
| Spacing vowel signs ा ि ी ो ौ, visarga ः | Mc | 1 |
| Virāma ्, vowel signs ु ू ृ ॄ े ै ॢ, anusvāra ं, candrabindu ँ, svara ॑ ॒ | Mn | 0 |
| IAST combining accents (U+0300, U+0301) | Mn | 0 |

The **cell budget** of an akṣara is the sum of its characters' widths. For
example:

| Akṣara | Characters | Cells |
|---|---|---|
| क | क | 1 |
| कि | क ि | 2 |
| क्ष | क ् ष | 2 |
| ग्नि | ग ् न ि | 3 |
| र्क (reph) | र ् क | 2 |
| क्र (rakāra) | क ् र | 2 |
| मी॑ | म ी ॑ | 2 |

### 3.2 Model B: per grapheme cluster (fallback)

If Phase 0 shows iTerm2 gives each grapheme cluster a fixed width, the budget
becomes per cluster instead. The build is set up by one width table
(`widths.json`, written by the probe), so switching models means changing data,
not code.

### 3.3 Fitting glyphs to the budget

After shaping, every glyph's advance width is set so that each akṣara's total
equals its budget. The cell width is **600 units** at 1000 units per em
(Noto Sans Mono's). Rules by glyph type:

| Glyph type | Example | Advance | How it's drawn |
|---|---|---|---|
| Full consonant or vowel | क अ | 600 (1 cell) | condensed to fit, centered |
| Half form | क् in क्य | 600 | the half form is narrow, so it's centered |
| Conjunct ligature | क्ष ज्ञ त्त | 600 × (spacing characters it replaces) | fitted to 2 cells |
| Pre-base ि | ि in कि | 600 | its hook spans the next consonant, as normal |
| Post-base ा ी ो ौ, visarga ः | | 600 | condensed, centered |
| Marks: virāma, ु ृ े ं ॑ ॒ | | 0 | placed by the font's GPOS anchors |
| Reph र् | र्क | 600 | drawn over the base consonant, shifted back one cell, which leaves a blank cell. That's the price of a 2-cell budget for a 1-consonant-wide shape. |
| Rakāra form | क्र प्र | 1200 (2 cells) | the glyph is centered in 2 cells, not stretched |

**The blank-cell trade-off.** Reph and rakāra show as an akṣara with a little
space after it. The alternatives are horizontal stretching, which looks bad, or
widths that don't match the budget, which breaks alignment. Space is the least
bad of the three. pra, tra and kra are common in the Ṛgveda, so we'll judge this
from screenshots in Phase 3.

**How advances get assigned.** A conjunct can come out of shaping as one
ligature glyph or as a chain of half forms. We don't guess which glyph covers
which characters. The build shapes every distinct akṣara that occurs in the
Ṛgveda (saṃhitā, padapāṭha and krama), reads HarfBuzz's cluster mapping, and
works out each glyph's advance from it. When a glyph is used in contexts with
different budgets, the build reports a conflict and resolves it with a
contextual GPOS adjustment.

---

## 4. Building the font

### 4.1 Sources (all SIL OFL 1.1, none with a Reserved Font Name)

| Part | Source | Why |
|---|---|---|
| Devanagari + Vedic marks | Noto Sans Devanagari (variable; `sources/noto-sans-devanagari/`) | Has ॑ ॒, kampa digits and 41 Vedic Extension characters, with mark anchors. Its `wdth` axis condenses the letters: at the narrowest setting (62.5), consonants are 308 to 616 units wide, median 451, so they fit a 600-unit cell with almost no distortion. Sans suits a terminal. |
| Latin, IAST, box drawing, the blocks ▂▄▇ | Noto Sans Mono (download) | Monospace with a 600-unit cell. Full Latin Extended Additional (ṛ ṝ ḷ ḹ ṃ ḥ ṅ ñ ṭ ḍ ṇ ś ṣ ḻ), combining accents, box drawing and blocks for the contour strip. Matching Noto design. |

Balambika and its patched Vedic version are **not** used, for two reasons:
"Balambika" is a Reserved Font Name, and it is a serif font.

### 4.2 Pipeline (`build.py`, fontTools)

1. **Fix the Devanagari design:** instance Noto Sans Devanagari at weight 400
   and a width between 62.5 and 75. The width is chosen so the median
   consonant is about 520 units, leaving room inside the cell.
2. **Scale vertically:** scale the Devanagari to match the Latin. The
   shirorekha (headline) sits at Noto Mono's cap height. Line metrics have
   to fit the tallest stack, ॑ above the headline, and the deepest, ॒ under ृ.
3. **Merge:** combine with Noto Sans Mono. Keep Mono's Latin glyphs, cmap
   entries and `latn` features, and Devanagari's `dev2`/`deva` GSUB and GPOS.
4. **Fit advances:** apply the advances from §3.3. Center each outline in its
   cells by shifting the outline itself, not by changing its side bearings
   alone. Shift mark anchors by the same amount so the marks follow.
5. **Vedic mark check:** for every combination in the corpus (॑ and ॒ on every
   akṣara, kampa १॒॑ and ॒३॒॑, ँ with ॑), confirm the GPOS anchors put the mark
   inside its akṣara's cells. Fix any that don't.
6. **Metrics:** set `hhea`, `OS/2` typo and win ascent/descent to the Latin
   line height plus the room the Vedic stacks need. This is the line spacing
   iTerm2 will use.
7. **Naming:** family "Vaagdevi", style "Regular", PostScript name
   `Vaagdevi-Regular`. Mark it monospaced (`post.isFixedPitch = 1`, PANOSE
   monospace) so it appears in iTerm2's font list. Include OFL.txt and a
   FONTLOG listing the sources and changes.

The build pins both source fonts by URL and SHA-256, so it is reproducible.

---

## 5. Verification

The corpus is the test suite. A width mismatch anywhere is a bug.

| Check | Tool | Pass condition |
|---|---|---|
| **Widths (HarfBuzz)** | `uharfbuzz` shapes every saṃhitā, padapāṭha and krama line, and every distinct akṣara | Total advance = the line's cell budget, for 100% of lines |
| **Widths (CoreText)** | `pyobjc` CoreText, the same engine iTerm2 uses | Same as above. CoreText and HarfBuzz shape Indic text slightly differently, so this is the check that counts. |
| **Marks** | Glyph bounding boxes after shaping | ॑ and ॒ fall inside their akṣara's cells; nothing above the ascent or below the descent |
| **Visual sheet** | A PNG specimen rendered with CoreText | Looked at by eye: Ṛgveda 1.1.1, 10.129.5 (pluta), kampa verses, reph and rakāra, the 50 most common conjuncts |
| **In iTerm2** | Probe (Phase 0) plus a test sheet you run, plus your screenshot | Matches the PNG; cursor and color changes line up |

---

## 6. Installing it

```
cp dist/Vaagdevi-Regular.ttf ~/Library/Fonts/
```

Then in **iTerm2 → Settings → Profiles → Gruvbox Dark → Text**, keeping
Monaco 12 as the main font:
1. Turn on **Use a different font for non-ASCII text** and pick **Vaagdevi 12**.
2. Turn on **ligatures for the non-ASCII font**. Monaco's ASCII text is
   unaffected.

Everything else stays as it is. Devanagari, the svara marks and IAST letters
like ṛ ṃ ḥ come from Vaagdevi, and plain ASCII stays in Monaco.

`tools/render_pss.py` then goes back to coloring Devanagari, per word rather
than per akṣara so shaping runs aren't broken. A `--vaagdevi` check tells you
if the setup is wrong.

---

## 7. Phases

| Phase | Work | Output | Your part |
|---|---|---|---|
| **0. Measure** | Write `probe.py` and a test sheet | `widths.json`; answers to U1 to U3 | Run one command in iTerm2, then send one screenshot (U4) |
| **1. Prototype** | Build with just the akṣaras in RV 1.1.1 | First `Vaagdevi-Regular.ttf` | Install it and screenshot `render_pss.py 1.1.1` |
| **2. Full build** | Every akṣara in the corpus; HarfBuzz and CoreText width checks at 100% | Font, report, PNG specimen | none |
| **3. Polish** | Reph/rakāra spacing, mark heights, line spacing | v1.0 | Judge the screenshots |

**Downloads needed:** Noto Sans Mono (font file), `uharfbuzz` and
`pyobjc-framework-CoreText` (pip, into `font/.venv`).

---

## 8. Risks

| Risk | Effect | Response |
|---|---|---|
| iTerm2 groups grapheme clusters (Model B) | Budgets change | Width table is data (§3.2). Phase 0 finds out before any glyph work starts. |
| iTerm2 clips glyphs at cell edges | Reph and wide conjuncts get cut off | Keep every outline inside its own cells. Reph then sits a little right of the traditional position. |
| CoreText and HarfBuzz shape differently | Widths pass one check, fail the other | CoreText is the reference (§5) |
| Ligature mode is slow or buggy in iTerm2 | Rendering glitches | Known iTerm2 behavior. Documented and reported, not worked around. |
| Condensed Devanagari is hard to read at small sizes | Eye strain | 14 pt minimum. Phase 3 can choose a less condensed `wdth` and pay with more 2-cell glyphs. |
| Tall Vedic stacks force wide line spacing | Latin text looks loosely spaced | Measure it in Phase 1. The option is to slightly shrink the Devanagari, not to clip the marks. |

---

## 9. Open questions

1. Is a blank cell after reph and rakāra acceptable (§3.3)? The answer comes
   from Phase 3 screenshots.
2. ~~Font size~~: answered. It's 12 pt (Monaco 12), so marks have to stay
   legible at 12 pt.
3. Weight: Regular only, or Bold too? "Use bold font" is on in your profile,
   so bold Devanagari needs a real Bold.
4. **Reph and rakāra perfect, not gapped:** you want this fixed properly, after
   v1. That means a way to give a 1-consonant-wide shape 2 cells without
   visible space, for example a wider reph/rakāra design drawn for 2 cells.
