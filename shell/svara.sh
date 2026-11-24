# Toggle Vaagdevi's svara colours in the current iTerm2 tab.
#
#   source /path/to/vaagdevi-lipi/shell/svara.sh     (e.g. in ~/.zshrc or ~/.bashrc)
#
#   svara on      switch this tab to the "Vaagdevi Svara" profile (coloured)
#   svara off     switch back to the "Vaagdevi" profile (plain)
#   svara         toggle
#
# It uses iTerm2's SetProfile escape sequence, so it changes the whole tab at
# once, text already on screen included. The profiles come from `make install`.
# Inside tmux, the sequence is wrapped so tmux passes it through (this needs
# `set -g allow-passthrough on` in tmux 3.3 or later).

VAAGDEVI_PLAIN_PROFILE="${VAAGDEVI_PLAIN_PROFILE:-Vaagdevi}"
VAAGDEVI_SVARA_PROFILE="${VAAGDEVI_SVARA_PROFILE:-Vaagdevi Svara}"

_vaagdevi_set_profile() {
    if [ -n "$TMUX" ]; then
        printf '\033Ptmux;\033\033]1337;SetProfile=%s\007\033\\' "$1"
    else
        printf '\033]1337;SetProfile=%s\007' "$1"
    fi
}

svara() {
    case "${1:-toggle}" in
        on)  _vaagdevi_set_profile "$VAAGDEVI_SVARA_PROFILE"; VAAGDEVI_SVARA=1 ;;
        off) _vaagdevi_set_profile "$VAAGDEVI_PLAIN_PROFILE"; VAAGDEVI_SVARA=0 ;;
        toggle)
            if [ "${VAAGDEVI_SVARA:-0}" = 1 ]; then svara off; else svara on; fi ;;
        *) echo "usage: svara [on|off]" >&2; return 2 ;;
    esac
}
