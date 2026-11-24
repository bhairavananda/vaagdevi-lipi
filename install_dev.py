#!/usr/bin/env python3
"""Install the current build into iTerm2 under a fresh name.

macOS caches fonts by name, so a running iTerm2 keeps drawing an old build
even after the file in ~/Library/Fonts is replaced. This installs the build
as "Vaagdevi Dev <n>" (a new name each time), removes older dev builds, and
points the "Vaagdevi Test" profile at it. If the svara-coloured build exists
(make svara), it is installed the same way for a "Vaagdevi Svara Test" profile.

    .venv/bin/python install_dev.py      (or: make dev)
"""

import json
import time
from pathlib import Path

from fontTools.ttLib import TTFont

from build import LINE_SPACING

HERE = Path(__file__).resolve().parent
FONTS = Path.home() / "Library/Fonts"
PROFILE = Path.home() / "Library/Application Support/iTerm2/DynamicProfiles/vaagdevi-test.json"


def install(src, stem, n):
    """Save `src` into ~/Library/Fonts as "<stem> Dev <n>"; return its PostScript name."""
    family, ps = f"{stem} Dev {n}", f"{stem.replace(' ', '')}Dev{n}-Regular"
    font = TTFont(src)
    name = font["name"]
    for nid, value in ((1, family), (3, f"{family} Regular"), (4, f"{family} Regular"), (6, ps)):
        name.setName(value, nid, 3, 1, 0x409)
    font.save(FONTS / f"{ps}.ttf")
    return ps


def profile(name, guid, ps):
    return {
        "Name": name,
        "Guid": guid,
        "Use Non-ASCII Font": True,
        "Non Ascii Font": f"{ps} 12",
        "Non-ASCII Ligatures": True,
        "Vertical Spacing": LINE_SPACING,
    }


def main():
    n = time.strftime("%H%M%S")
    for old in list(FONTS.glob("VaagdeviDev*.ttf")) + list(FONTS.glob("VaagdeviSvaraDev*.ttf")):
        old.unlink()
    profiles = [profile("Vaagdevi Test", "vaagdevi-test-0001",
                        install(HERE / "dist/Vaagdevi-Regular.ttf", "Vaagdevi", n))]
    svara = HERE / "dist/VaagdeviSvara-Regular.ttf"
    if svara.exists():
        profiles.append(profile("Vaagdevi Svara Test", "vaagdevi-svara-test-0001",
                                install(svara, "Vaagdevi Svara", n)))
    PROFILE.write_text(json.dumps({"Profiles": profiles}, indent=2))
    for p in profiles:
        print(f"profile '{p['Name']}' uses {p['Non Ascii Font']}")

if __name__ == "__main__":
    main()
