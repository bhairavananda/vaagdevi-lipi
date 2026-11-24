#!/usr/bin/env python3
"""Install Vaagdevi and Vaagdevi Svara, with an iTerm2 profile for each.

Copies dist/Vaagdevi-Regular.ttf and dist/VaagdeviSvara-Regular.ttf into
~/Library/Fonts and writes two iTerm2 dynamic profiles, "Vaagdevi" and
"Vaagdevi Svara". Each inherits everything from your default profile (or
--parent) and only sets the non-ASCII font, its ligatures and the line
spacing. Also copies the svara toggle and the Sanskrit typing mode
(shell/svara.sh, shell/skt.zsh, shell/skt.py) and the Neovim preview plugin
(nvim/plugin/vaagdevi.lua) to ~/.local/share/vaagdevi, the same place
install.sh puts them.

    .venv/bin/python install.py [--size 12] [--parent "My Profile"] [--default]   (or: make install)

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
SHARE = Path.home() / ".local/share/vaagdevi"
BUILDS = [("Vaagdevi", "vaagdevi-0001", "Vaagdevi-Regular"),
          ("Vaagdevi Svara", "vaagdevi-svara-0001", "VaagdeviSvara-Regular")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--size", type=int, default=12, help="font size, same as your main font (default: 12)")
    ap.add_argument("--parent", help="profile to inherit from (default: your default profile)")
    ap.add_argument("--default", action="store_true",
                    help="make Vaagdevi the default profile for new windows and tabs; "
                         "use with --parent, and remove the default flag from any other "
                         "dynamic profile that sets one")
    args = ap.parse_args()

    # Keep the parent and default choices from an earlier install unless new
    # ones are given, so reinstalling doesn't quietly undo them.
    earlier = {}
    if PROFILES.exists():
        try:
            earlier = {p["Name"]: p for p in json.loads(PROFILES.read_text())["Profiles"]}
        except (ValueError, KeyError, TypeError):
            earlier = {}

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
        before = earlier.get(name, {})
        parent = args.parent or before.get("Dynamic Profile Parent Name")
        if parent:
            profile["Dynamic Profile Parent Name"] = parent
        if name == "Vaagdevi" and (args.default or before.get("Default Bookmark") == "Yes"):
            profile["Default Bookmark"] = "Yes"
        profiles.append(profile)
        print(f"installed {src.name}")
    PROFILES.parent.mkdir(parents=True, exist_ok=True)
    PROFILES.write_text(json.dumps({"Profiles": profiles}, indent=2))
    print(f"iTerm2 profiles: {', '.join(p['Name'] for p in profiles)} ({PROFILES})")
    SHARE.mkdir(parents=True, exist_ok=True)
    for f in ("svara.sh", "skt.zsh", "skt.py"):
        shutil.copy2(HERE / "shell" / f, SHARE / f)
    (SHARE / "nvim/plugin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "nvim/plugin/vaagdevi.lua", SHARE / "nvim/plugin/vaagdevi.lua")
    print(f"\nAdd to ~/.zshrc:\n  source {SHARE}/svara.sh\n  source {SHARE}/skt.zsh")
    print(f"Add to the end of ~/.config/nvim/init.lua:\n  vim.opt.rtp:append(\"{SHARE}/nvim\")\n"
          f"  vim.cmd.runtime(\"plugin/vaagdevi.lua\")")


if __name__ == "__main__":
    main()
