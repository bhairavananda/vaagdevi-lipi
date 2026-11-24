#!/usr/bin/env python3
"""Phase 0 probe: measure how iTerm2 gives cells to Devanagari.

Run it inside iTerm2. For each test string it prints the string, asks the
terminal where the cursor is (ESC [6n), and records how many cells the string
took. Results go to probe_results.json next to this file. Then it shows a test
sheet to screenshot.

    python3 probe.py      (run inside iTerm2)
"""

import json
import os
import re
import sys
import termios
import tty
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent

SINGLE = list("कषमरळअइउएऋ१३ऽ।") + ["ि", "ी", "ा", "ो", "ौ", "ः", "्", "ु", "ू", "ृ", "े", "ै",
                                   "ं", "ँ", "॒", "॑"]
CLUSTERS = [
    "क", "कि", "की", "का", "को", "कः", "कं", "कु", "के", "क्", "क्ष", "ज्ञ", "त्त", "ग्नि",
    "र्क", "क्र", "प्र", "मी॑", "अ॒", "ग्नि॑", "हि॑तं", "त॒े", "स्व१॒॑", "यो॒३॒॑", "सी३",
    "दे॒वाँ", "पु॒रोहि॑तं",
    "अ॒ग्निमी॑ळे पु॒रोहि॑तं य॒ज्ञस्य॑ दे॒वमृ॒त्विज॑म् ।होता॑रं रत्न॒धात॑मम् ॥",
    "agním", "agním", "ṛtvíjam", "ḻ", "m̐", "▂▄▇",
]


def cells(fd, s):
    os.write(fd, b"\r\x1b[2K" + s.encode() + b"\x1b[6n")
    buf = b""
    while not buf.endswith(b"R"):
        buf += os.read(fd, 32)
    m = re.search(rb"\[(\d+);(\d+)R", buf)
    return int(m.group(2)) - 1


def main():
    fd = os.open("/dev/tty", os.O_RDWR)
    old = termios.tcgetattr(fd)
    results = {"term": os.environ.get("TERM_PROGRAM"),
               "version": os.environ.get("TERM_PROGRAM_VERSION"),
               "profile": os.environ.get("ITERM_PROFILE"), "strings": []}
    try:
        tty.setraw(fd)
        for s in SINGLE + CLUSTERS:
            n = cells(fd, s)
            results["strings"].append({
                "text": s,
                "codepoints": [f"U+{ord(c):04X} {unicodedata.category(c)}" for c in s][:12],
                "cells": n,
                "chars": len(s),
            })
        os.write(fd, b"\r\x1b[2K")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    out = HERE / "data/probe_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    # Test sheet for the screenshot: a ruler so cell positions are visible.
    ruler = "".join(str(i % 10) for i in range(60))
    print("Vaagdevi probe — test sheet   (written: " + str(out) + ")\n")
    print("     " + ruler)
    for s in ["कि की का को", "क्ष ज्ञ त्त ग्नि", "र्क क्र प्र", "मी॑ अ॒ ग्नि॑ हि॑तं",
              "स्व१॒॑ यो॒३॒॑ सी३ दे॒वाँ",
              "अ॒ग्निमी॑ळे पु॒रोहि॑तं य॒ज्ञस्य॑ दे॒वमृ॒त्विज॑म् ।",
              "होता॑रं रत्न॒धात॑मम् ॥ १ ॥",
              "agním īḻe puróhitaṃ ▂▄▇▄"]:
        print("     " + s + "|")
    print("     " + ruler)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
