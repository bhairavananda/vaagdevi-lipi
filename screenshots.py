#!/usr/bin/env python3
"""Take the README screenshots: the same text in iTerm2 without Vaagdevi, with
Vaagdevi, and with Vaagdevi Svara.

Opens one iTerm2 window per profile (the default profile, a profile that uses
Vaagdevi, and one that uses Vaagdevi Svara), waits for them to draw, captures
each window with screencapture, and closes them. No shell prompt or cursor
appears in the images.

    python3 screenshots.py                     (or: make screenshots)
    python3 screenshots.py --profile Vaagdevi  --text examples/rv-1.1.txt

Needs macOS, iTerm2, and Screen Recording permission for the app running this
script (System Settings → Privacy & Security → Screen Recording). Without that
permission macOS returns images of the desktop instead of the windows; the
script checks for this and stops.
"""

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Window bounds {left, top, right, bottom} in points. Sized for rv-1.1.txt at
# 12 pt with 1.3 line spacing.
BOUNDS = (60, 60, 900, 900)


def osascript(script):
    r = subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"osascript failed: {r.stderr.strip()}")
    return r.stdout.strip()


def applescript_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def open_window(profile, title, text, hold):
    """Open an iTerm2 window that shows `text` with no prompt or cursor.
    Returns its window number, which is the CGWindowID screencapture wants."""
    cmd = (f"printf '\\033[?25l\\033]0;%s\\007' {shlex.quote(title)}; clear; "
           f"printf '%s\\n\\n' {shlex.quote('— ' + title + ' —')}; "
           f"cat {shlex.quote(str(text))}; sleep {hold}")
    shell = "/bin/sh -c " + shlex.quote(cmd)
    create = ("create window with default profile" if profile is None
              else f"create window with profile {applescript_str(profile)}")
    return int(osascript(f"""
tell application "iTerm2"
  set w to ({create} command {applescript_str(shell)})
  set bounds of w to {{{', '.join(map(str, BOUNDS))}}}
  return id of w
end tell"""))


def close_window(wid):
    osascript(f"""
tell application "iTerm2"
  repeat with w in windows
    if id of w is {wid} then close w
  end repeat
end tell""")


def capture(wid, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    # -l: this window only, -o: no drop shadow, -x: no sound
    r = subprocess.run(["screencapture", "-o", "-x", "-l", str(wid), str(out)],
                       capture_output=True, text=True)
    if r.returncode or not out.exists() or out.stat().st_size < 20_000:
        sys.exit(f"could not capture iTerm2 window {wid} ({r.stderr.strip() or 'empty image'}).\n"
                 "Give the app running this script (e.g. iTerm2) Screen Recording permission:\n"
                 "System Settings → Privacy & Security → Screen Recording, then quit and reopen it.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--text", default=HERE / "examples/rv-1.1.txt", type=Path)
    ap.add_argument("--profile", default="Vaagdevi Test",
                    help="iTerm2 profile that uses Vaagdevi (default: %(default)s, set up by make dev)")
    ap.add_argument("--svara-profile", default="Vaagdevi Svara Test",
                    help="profile that uses Vaagdevi Svara (default: %(default)s; '' to skip)")
    ap.add_argument("--without-profile", default=None,
                    help="profile for the 'without' window (default: iTerm2's default profile)")
    ap.add_argument("--out", default=HERE / "docs/images", type=Path)
    ap.add_argument("--name", default="rv-1.1", help="image name prefix (default: %(default)s)")
    ap.add_argument("--wait", default=3.0, type=float, help="seconds to let the windows draw")
    args = ap.parse_args()

    shots = [
        (args.without_profile, "without Vaagdevi", args.out / f"{args.name}-without.png"),
        (args.profile, "with Vaagdevi", args.out / f"{args.name}-vaagdevi.png"),
    ]
    if args.svara_profile:
        shots.append((args.svara_profile, "Vaagdevi Svara", args.out / f"{args.name}-svara.png"))
    hold = int(args.wait * len(shots) + 30)
    windows = []
    try:
        for profile, title, out in shots:
            windows.append((open_window(profile, title, args.text.resolve(), hold), out))
        time.sleep(args.wait)
        for wid, out in windows:
            capture(wid, out)
            print(f"wrote {out.relative_to(HERE) if out.is_relative_to(HERE) else out}")
    finally:
        for wid, _ in windows:
            close_window(wid)


if __name__ == "__main__":
    main()
