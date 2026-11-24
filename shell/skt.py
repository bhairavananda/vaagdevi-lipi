#!/usr/bin/env python3
"""Baraha → Devanagari, for typing Sanskrit (Vedic accents included).

    skt.py 'aqgnimI#LE puqrOhi#taM'     →  अ॒ग्निमी॑ळे पु॒रोहि॑तं
    skt.py < sukta.brh > sukta.txt       (a whole file)
    skt.py --serve                       (one line in, one line out; used by skt.zsh)
    skt.py --watch FILE                  (live preview of FILE; used by the nvim plugin)

The scheme is Baraha's. A few notes for Sanskrit:
- e and o are ए and ओ (Sanskrit has no short e or o); E and O work too.
- After a vowel, q is anudātta ॒, # is svarita ॑, $ is the dīrgha svarita ᳚.
- | and || are the daṇḍas, & is avagraha ऽ, OM is ॐ, digits become
  Devanagari digits. A full stop stays a full stop.
- _ separates letters that would otherwise combine (ka_i → कइ, k_h → क्ह),
  ^^ is a zero-width non-joiner (~j^^ja → ञ्‌ज), ^ a zero-width joiner.
Anything else (spaces, other punctuation, non-ASCII) passes through.
"""

import json
import os
import re
import shutil
import sys
import time

VOWELS = {  # independent form, vowel sign
    "a": ("अ", ""), "A": ("आ", "ा"), "aa": ("आ", "ा"),
    "i": ("इ", "ि"), "I": ("ई", "ी"), "ee": ("ई", "ी"),
    "u": ("उ", "ु"), "U": ("ऊ", "ू"), "oo": ("ऊ", "ू"),
    "Ru": ("ऋ", "ृ"), "RU": ("ॠ", "ॄ"), "~lu": ("ऌ", "ॢ"), "~lU": ("ॡ", "ॣ"),
    "e": ("ए", "े"), "E": ("ए", "े"), "ai": ("ऐ", "ै"),
    "o": ("ओ", "ो"), "O": ("ओ", "ो"), "au": ("औ", "ौ"), "ou": ("औ", "ौ"),
}
CONSONANTS = {
    "k": "क", "kh": "ख", "K": "ख", "g": "ग", "gh": "घ", "G": "घ", "~g": "ङ",
    "ch": "च", "c": "च", "Ch": "छ", "C": "छ", "j": "ज", "jh": "झ", "J": "झ", "~j": "ञ",
    "T": "ट", "Th": "ठ", "D": "ड", "Dh": "ढ", "N": "ण",
    "t": "त", "th": "थ", "d": "द", "dh": "ध", "n": "न",
    "p": "प", "ph": "फ", "P": "फ", "b": "ब", "bh": "भ", "B": "भ", "m": "म",
    "y": "य", "r": "र", "l": "ल", "v": "व", "w": "व",
    "sh": "श", "S": "श", "Sh": "ष", "s": "स", "h": "ह", "L": "ळ",
    "kSh": "क्ष", "j~j": "ज्ञ",
    "kx": "क़", "Kx": "ख़", "gx": "ग़", "z": "ज़", "jx": "ज़", "Dx": "ड़", "Dhx": "ढ़",
    "f": "फ़", "Px": "फ़", "Y": "य़", "yx": "य़", "rx": "ऱ", "Lx": "ऴ", "nx": "ऩ",
}
MARKS = {"M": "ं", "H": "ः", "~M": "ँ", "(gg)": "ꣳ"}          # yogavāhas
ACCENTS = {"q": "॒", "#": "॑", "$": "᳚", "V": "᳝", "W": "᳸", "Q": "᳒"}
SYMBOLS = {"||": "॥", "|": "।", "&": "ऽ", "OM": "ॐ",
           **{str(d): "०१२३४५६७८९"[d] for d in range(10)}}
JOINERS = {"^^": "‌", "^": "‍", "_": ""}
VIRAMA = "्"

TOKENS = sorted({*VOWELS, *CONSONANTS, *MARKS, *ACCENTS, *SYMBOLS, *JOINERS},
                key=len, reverse=True)
TOKEN = re.compile("|".join(re.escape(t) for t in TOKENS) + "|.", re.S)
TRAILING = re.compile("([॒᳝॑᳚᳸᳒]+)([ंःँꣳ]+)")


def to_devanagari(text):
    out, pending = [], False   # pending: last consonant still owes its vowel
    for tok in TOKEN.findall(text):
        if tok == "OM" and pending:          # tOM is तों, not त + ॐ
            out += [VOWELS["O"][1], MARKS["M"]]
            pending = False
        elif tok in CONSONANTS:
            if pending:
                out.append(VIRAMA)
            out.append(CONSONANTS[tok])
            pending = True
        elif tok in VOWELS:
            independent, sign = VOWELS[tok]
            out.append(sign if pending else independent)
            pending = False
        else:
            if pending and tok not in ACCENTS and tok not in MARKS:
                out.append(VIRAMA)     # a consonant with no vowel after it: halanta
                pending = False
            elif pending and tok in (*ACCENTS, *MARKS):
                pending = False        # the inherent a, then the mark
            out.append(MARKS.get(tok) or ACCENTS.get(tok) or SYMBOLS.get(tok)
                       or JOINERS.get(tok, tok))
    if pending:
        out.append(VIRAMA)
    # Anusvāra and visarga before svara marks, as in the Ṛgveda text Vaagdevi
    # is built from (यं॑, not य॑ं).
    return TRAILING.sub(r"\2\1", "".join(out))


DEVANAGARI = re.compile("[\u0900-\u097F]")


def render(text, cursor, rows):
    """The preview screen: the text (converted unless it is already
    Devanagari), scrolled so the cursor line is in view and marked with ▸."""
    if not DEVANAGARI.search(text):
        text = to_devanagari(text)
    lines = text.split("\n")
    top = max(0, min(cursor - 1 - rows // 2, len(lines) - rows))
    shown = []
    for i, line in enumerate(lines[top:top + rows], start=top + 1):
        shown.append(("\033[33m▸\033[0m " if i == cursor else "  ") + line)
    return "\n".join(shown)


def watch(path):
    """Redraw FILE whenever it (or FILE.state, which holds the cursor line
    and the svara setting) changes. Ends when FILE is deleted."""
    state_path = path + ".state"
    out = sys.stdout
    # The alternate screen (like less or nvim) keeps redraws out of scrollback.
    out.write("\033]0;Vaagdevi preview\007\033[?1049h\033[?25l")
    last, svara, seen, missing_since = None, None, False, None
    try:
        while True:
            try:
                stamp = (os.stat(path).st_mtime_ns,
                         os.stat(state_path).st_mtime_ns if os.path.exists(state_path) else 0,
                         shutil.get_terminal_size())
                seen, missing_since = True, None
            except FileNotFoundError:
                if seen:
                    missing_since = missing_since or time.monotonic()
                    if time.monotonic() - missing_since > 1.0:
                        return          # nvim closed the preview or exited
                time.sleep(0.1)
                continue
            if stamp != last:
                last = stamp
                try:
                    with open(state_path, encoding="utf-8") as f:
                        state = json.load(f)
                except (OSError, ValueError):
                    state = {}
                if state.get("svara") is not None and state["svara"] != svara:
                    svara = state["svara"]
                    out.write("\033]1337;SetProfile=%s\007" % state.get(
                        "svara_profile" if svara else "profile", "Vaagdevi"))
                with open(path, encoding="utf-8") as f:
                    text = f.read().rstrip("\n")
                rows = stamp[2].lines
                # Overwrite in place (erase each line's tail and what's below)
                # instead of clearing, so nothing is pushed into scrollback.
                frame = render(text, int(state.get("cursor", 1)), rows - 1)
                out.write("\033[H" + "\033[K\n".join(frame.split("\n")) + "\033[K\033[J")
                out.flush()
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\033[?25h\033[?1049l")
        out.flush()


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--watch":
        watch(args[1])
    elif args == ["--serve"]:
        for line in sys.stdin:
            sys.stdout.write(to_devanagari(line.rstrip("\n")) + "\n")
            sys.stdout.flush()
    elif args:
        print(to_devanagari(" ".join(args)))
    else:
        for line in sys.stdin:
            sys.stdout.write(to_devanagari(line.rstrip("\n")) + "\n")


if __name__ == "__main__":
    main()
