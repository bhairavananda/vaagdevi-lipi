#!/usr/bin/env python3
"""Install Vaagdevi and Vaagdevi Svara, with an iTerm2 profile for each.

Copies dist/Vaagdevi-Regular.ttf and dist/VaagdeviSvara-Regular.ttf into
~/Library/Fonts and writes two iTerm2 dynamic profiles, "Vaagdevi" and
"Vaagdevi Svara". Each inherits everything from your default profile (or
--parent) and only sets the non-ASCII font, its ligatures and the line
spacing. Switch between them with `svara on` / `svara off` (shell/svara.sh).

    .venv/bin/python install.py [--size 12] [--parent "My Profile"]   (or: make install)

Quit and reopen iTerm2 after reinstalling a changed build: macOS caches fonts
by name.
"""

import argparse
import json
import shutil
from pathlib import Path

from build import LINE_SPACING

HERE = Path(__file__).resolve().parent
FONTS = Path.home() / "Library/Fonts"
PROFILES = Path.home() / "Library/Application Support/iTerm2/DynamicProfiles/vaagdevi.json"
BUILDS = [("Vaagdevi", "vaagdevi-0001", "Vaagdevi-Regular"),
          ("Vaagdevi Svara", "vaagdevi-svara-0001", "VaagdeviSvara-Regular")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--size", type=int, default=12, help="font size, same as your main font (default: 12)")
    ap.add_argument("--parent", help="profile to inherit from (default: your default profile)")
    args = ap.parse_args()

    profiles = []
    for name, guid, ps in BUILDS:
        src = HERE / "dist" / f"{ps}.ttf"
        if not src.exists():
            raise SystemExit(f"{src.relative_to(HERE)} is missing: run make first")
        shutil.copy2(src, FONTS / src.name)
        profile = {
            "Name": name,
            "Guid": guid,
            "Use Non-ASCII Font": True,
            "Non Ascii Font": f"{ps} {args.size}",
            "Non-ASCII Ligatures": True,
            "Vertical Spacing": LINE_SPACING,
        }
        if args.parent:
            profile["Dynamic Profile Parent Name"] = args.parent
        profiles.append(profile)
        print(f"installed {src.name}")
    PROFILES.parent.mkdir(parents=True, exist_ok=True)
    PROFILES.write_text(json.dumps({"Profiles": profiles}, indent=2))
    print(f"iTerm2 profiles: {', '.join(p['Name'] for p in profiles)} ({PROFILES})")


if __name__ == "__main__":
    main()
