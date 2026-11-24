#!/usr/bin/env python3
"""Baraha → Devanagari, for typing Sanskrit (Vedic accents included).

    skt.py 'aqgnimI#LE puqrOhi#taM'     →  अ॒ग्निमी॑ळे पु॒रोहि॑तं
    skt.py < sukta.brh > sukta.txt       (a whole file)
    skt.py --serve                       (one line in, one line out; used by skt.zsh)

The scheme is Baraha's. A few notes for Sanskrit:
- e and o are ए and ओ (Sanskrit has no short e or o); E and O work too.
- After a vowel, q is anudātta ॒, # is svarita ॑, $ is the dīrgha svarita ᳚.
- | and || are the daṇḍas, & is avagraha ऽ, OM is ॐ, digits become
  Devanagari digits. A full stop stays a full stop.
- _ separates letters that would otherwise combine (ka_i → कइ, k_h → क्ह),
  ^^ is a zero-width non-joiner (~j^^ja → ञ्‌ज), ^ a zero-width joiner.
Anything else (spaces, other punctuation, non-ASCII) passes through.
"""

import re
import sys

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


def main():
    args = sys.argv[1:]
    if args == ["--serve"]:
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
