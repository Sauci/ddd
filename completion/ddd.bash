# Terminal completion of DDD variable names, for bash (and zsh via bashcompinit).
#
#   export DDD_CONVENTION=/path/to/convention.ddd.json
#   source /path/to/ddd/completion/ddd.bash
#   ddd name val_Inlet<TAB>
#
# The work is done by `ddd complete`, which prints one candidate per line and never fails: a
# completion that reports an error instead of offering nothing is worse than useless. Every
# early return below leaves COMPREPLY untouched for the same reason.
_ddd_complete() {
    local convention="${DDD_CONVENTION:-}"
    # Names are only meaningful for the `name` subcommand; -o default lets the shell fall
    # back to file names for the others.
    if [ "${COMP_WORDS[1]:-}" != "name" ]; then
        return 0
    fi
    if [ -z "$convention" ] || [ ! -f "$convention" ]; then
        return 0
    fi

    local current="${COMP_WORDS[COMP_CWORD]}"
    local candidates
    candidates="$(ddd complete --convention "$convention" -- "$current" 2>/dev/null)" || return 0
    [ -n "$candidates" ] || return 0

    # Read as data, never as shell words. `compgen -W` would re-parse the list and perform
    # command substitution on it, so a token from somebody else's convention file would run
    # in this shell the moment TAB is pressed. `ddd complete` already filters on the prefix,
    # so there is nothing compgen would add.
    #
    # -o nospace: a completed segment is rarely the end of a name, so leaving the cursor glued
    # to the separator lets the next TAB carry on where this one stopped.
    mapfile -t COMPREPLY <<< "$candidates"
}

complete -o nospace -o default -F _ddd_complete ddd
