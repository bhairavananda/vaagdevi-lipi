#!/usr/bin/env python3
"""Install the current build into iTerm2 under a fresh name.

macOS caches fonts by name, so a running iTerm2 keeps drawing an old build
even after the file in ~/Library/Fonts is replaced. This installs the build
as "Vaagdevi Dev <n>" (a new name each time), removes older dev builds, and
points the "Vaagdevi Test" profile at it.

    .venv/bin/python install_dev.py      (or: make dev)
"""

import json
import time
from pathlib import Path

from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONTS = Path.home() / "Library/Fonts"
PROFILE = Path.home() / "Library/Application Support/iTerm2/DynamicProfiles/vaagdevi-test.json"


def main():
    n = time.strftime("%H%M%S")
    family, ps = f"Vaagdevi Dev {n}", f"VaagdeviDev{n}-Regular"
    font = TTFont(HERE / "dist/Vaagdevi-Regular.ttf")
    name = font["name"]
    for nid, value in ((1, family), (3, f"{family} Regular"), (4, f"{family} Regular"), (6, ps)):
        name.setName(value, nid, 3, 1, 0x409)
    for old in FONTS.glob("VaagdeviDev*.ttf"):
        old.unlink()
    out = FONTS / f"{ps}.ttf"
    font.save(out)
    PROFILE.write_text(json.dumps({"Profiles": [{
        "Name": "Vaagdevi Test",
        "Guid": "vaagdevi-test-0001",
        "Dynamic Profile Parent Name": "Gruvbox Dark",
        "Use Non-ASCII Font": True,
        "Non Ascii Font": f"{ps} 12",
        "Non-ASCII Ligatures": True,
    }]}, indent=2))
    print(f"installed {out.name}; profile 'Vaagdevi Test' now uses {ps}")


if __name__ == "__main__":
    main()
