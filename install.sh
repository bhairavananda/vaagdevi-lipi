#!/bin/sh
# Install Vaagdevi from the latest GitHub release: no Python, no build.
#
#   curl -fsSL https://github.com/bhairavananda/vaagdevi-lipi/releases/latest/download/install.sh | sh
#
# It downloads Vaagdevi and Vaagdevi Svara into ~/Library/Fonts, adds the
# "Vaagdevi" and "Vaagdevi Svara" iTerm2 profiles (they inherit everything
# else from your default profile), and puts the svara toggle and the
# Sanskrit typing mode in ~/.local/share/vaagdevi. It doesn't edit your
# shell config.
#
# Set VAAGDEVI_SIZE to match your main font size (default 12), or
# VAAGDEVI_VERSION to install a specific release tag instead of the latest.
# The line spacing (1.3) matches LINE_SPACING in build.py.

set -eu

REPO="bhairavananda/vaagdevi-lipi"
SIZE="${VAAGDEVI_SIZE:-12}"
if [ -n "${VAAGDEVI_BASE:-}" ]; then
    BASE="$VAAGDEVI_BASE"     # a directory URL holding the release files (for testing)
elif [ -n "${VAAGDEVI_VERSION:-}" ]; then
    BASE="https://github.com/$REPO/releases/download/$VAAGDEVI_VERSION"
else
    BASE="https://github.com/$REPO/releases/latest/download"
fi
FONTS="$HOME/Library/Fonts"
PROFILES="$HOME/Library/Application Support/iTerm2/DynamicProfiles"
SHARE="$HOME/.local/share/vaagdevi"

case "$SIZE" in
    ''|*[!0-9]*) echo "VAAGDEVI_SIZE must be a whole number, got '$SIZE'" >&2; exit 1 ;;
esac
case "${VAAGDEVI_VERSION:-}" in
    *[!A-Za-z0-9._-]*) echo "VAAGDEVI_VERSION should be a release tag like v0.2" >&2; exit 1 ;;
esac
if [ "$(uname -s)" != Darwin ]; then
    echo "Vaagdevi is built for iTerm2 on macOS." >&2
    exit 1
fi

# Download everything first, so a failed download leaves nothing half-written.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for f in Vaagdevi-Regular.ttf VaagdeviSvara-Regular.ttf svara.sh skt.zsh skt.py; do
    echo "downloading $f"
    curl -fsSL -o "$TMP/$f" "$BASE/$f"
done

mkdir -p "$FONTS" "$PROFILES" "$SHARE"
mv "$TMP/Vaagdevi-Regular.ttf" "$TMP/VaagdeviSvara-Regular.ttf" "$FONTS/"
mv "$TMP/svara.sh" "$TMP/skt.zsh" "$TMP/skt.py" "$SHARE/"

cat > "$PROFILES/vaagdevi.json" <<EOF
{
  "Profiles": [
    {
      "Name": "Vaagdevi",
      "Guid": "vaagdevi-0001",
      "Use Non-ASCII Font": true,
      "Non Ascii Font": "Vaagdevi-Regular $SIZE",
      "Non-ASCII Ligatures": true,
      "Vertical Spacing": 1.3
    },
    {
      "Name": "Vaagdevi Svara",
      "Guid": "vaagdevi-svara-0001",
      "Use Non-ASCII Font": true,
      "Non Ascii Font": "VaagdeviSvara-Regular $SIZE",
      "Non-ASCII Ligatures": true,
      "Vertical Spacing": 1.3
    }
  ]
}
EOF

cat <<EOF

Vaagdevi is installed.

  1. Quit and reopen iTerm2 so it picks up the fonts.
  2. Open a window with the "Vaagdevi" profile (Profiles menu).
  3. Add these lines to ~/.zshrc:

       source "$SHARE/svara.sh"     # 'svara on' / 'svara off': svara colours
       source "$SHARE/skt.zsh"      # 'skt': type Sanskrit in Baraha

     (In bash, only the first line works: Sanskrit typing needs zsh.)
EOF
