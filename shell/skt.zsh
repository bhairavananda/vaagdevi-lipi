# Type Sanskrit at the zsh prompt in Baraha, and get Devanagari as you type.
#
#   source /path/to/vaagdevi-lipi/shell/skt.zsh     (in ~/.zshrc)
#
#   skt                  turn Sanskrit mode on
#   Ctrl-X s             turn it on or off, any time (in Sanskrit mode,
#                        typing "skt" would give you स्क्त्)
#   skt 'aqgnimI#LE'     print one line in Devanagari:  अ॒ग्निमी॑ळे
#   skt < in.brh         convert a whole file
#
# In Sanskrit mode each word turns into Devanagari while you type it, and
# backspace takes back the last thing you typed. A space starts a new word.
# The scheme is Baraha (see skt.py): e and o are ए and ओ, and after a vowel
# q is anudātta, # svarita and $ dīrgha svarita. Needs python3 (no packages).

zmodload zsh/zle 2>/dev/null
autoload -Uz add-zle-hook-widget

typeset -g _SKT_DIR=${${(%):-%x}:A:h}
typeset -gi _SKT_ON=0 _SKT_START=-1
typeset -g _SKT_RAW="" _SKT_SHOWN="" _SKT_TO="" _SKT_FROM="" _SKT_SAVED_RPS1=""

# One converter process for the whole session, so typing stays instant.
_skt_server() {
    [[ -n $_SKT_TO ]] && return 0
    command -v python3 >/dev/null || { print -u2 "skt: python3 is needed"; return 1 }
    # Started quietly and disowned: no job notice now, no "running jobs"
    # warning at exit. It ends by itself when the shell closes its input.
    setopt local_options no_monitor no_notify
    coproc python3 -I -u "$_SKT_DIR/skt.py" --serve
    exec {_SKT_TO}>&p {_SKT_FROM}<&p
    disown %+ 2>/dev/null
}

_skt_convert() {   # sets REPLY to the Devanagari for $1
    print -r -u $_SKT_TO -- "$1"
    IFS= read -r -u $_SKT_FROM REPLY
}

_skt_forget() { _SKT_RAW=""; _SKT_START=-1; _SKT_SHOWN="" }

# Is the cursor still right after the word we're building, unchanged?
_skt_in_word() {
    (( _SKT_START >= 0 && CURSOR == _SKT_START + ${#_SKT_SHOWN} )) &&
        [[ ${BUFFER[_SKT_START+1,CURSOR]} == "$_SKT_SHOWN" ]]
}

_skt_render() {
    local before=${BUFFER[1,_SKT_START]} after=${BUFFER[_SKT_START+${#_SKT_SHOWN}+1,-1]}
    _skt_convert "$_SKT_RAW"
    BUFFER="$before$REPLY$after"
    _SKT_SHOWN=$REPLY
    CURSOR=$(( _SKT_START + ${#REPLY} ))
    # zsh thinks ि ी ा take no width, iTerm2 gives each a cell, so zsh's
    # usual partial redraw lands in the wrong column. Redraw the whole line.
    zle reset-prompt
}

_skt_insert() {
    if [[ $KEYS == " " ]]; then
        _skt_forget
        zle .self-insert
        return
    fi
    _skt_in_word || { _SKT_RAW=""; _SKT_SHOWN=""; _SKT_START=$CURSOR }
    _SKT_RAW+=$KEYS
    _skt_render
}

_skt_backspace() {
    if [[ -n $_SKT_RAW ]] && _skt_in_word; then
        _SKT_RAW=${_SKT_RAW[1,-2]}
        _skt_render
        [[ -z $_SKT_RAW ]] && _skt_forget
    else
        _skt_forget
        zle .backward-delete-char
        zle reset-prompt
    fi
}

_skt_set() {   # 1 = on, 0 = off
    if (( $1 )); then
        _skt_server || return 1
        _SKT_ON=1
        _SKT_SAVED_RPS1=$RPS1
        RPS1="%F{yellow}संस्कृत%f${RPS1:+ $RPS1}"
    else
        _SKT_ON=0
        RPS1=$_SKT_SAVED_RPS1
    fi
    _skt_forget
}

_skt_toggle() {   # Ctrl-X s, inside a line
    _skt_set $(( ! _SKT_ON )) || return
    if (( _SKT_ON )); then zle -K skt; else zle -K main; fi
    zle reset-prompt
}

_skt_line_init() {
    _skt_forget
    (( _SKT_ON )) && zle -K skt
}

zle -N _skt_insert
zle -N _skt_backspace
zle -N _skt_toggle
zle -N _skt_line_init
add-zle-hook-widget line-init _skt_line_init

# Sanskrit mode is its own keymap, a copy of your main one with the printable
# keys and backspace taken over, so nothing changes when the mode is off.
bindkey -N skt main
bindkey -M skt -R ' '-'~' _skt_insert
bindkey -M skt '^?' _skt_backspace '^H' _skt_backspace
bindkey -M main '^Xs' _skt_toggle
bindkey -M skt '^Xs' _skt_toggle

skt() {
    if (( $# )); then
        python3 -I "$_SKT_DIR/skt.py" "$@"
    elif [[ ! -t 0 ]]; then
        python3 -I "$_SKT_DIR/skt.py"
    else
        _skt_set $(( ! _SKT_ON )) || return
        if (( _SKT_ON )); then
            print "Sanskrit mode on: type Baraha (aqgnimI#LE). Ctrl-X s turns it off."
        else
            print "Sanskrit mode off"
        fi
    fi
}
