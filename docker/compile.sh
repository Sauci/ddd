#!/usr/bin/env bash
#
# Generate the c code of a DDD project and prove that it really compiles.
#
#   ddd-compile [PROJECT] [OUTPUT_DIR]
#
# Environment:
#   CDEFS    extra preprocessor defines, compiled as a second variant
#            (e.g. CDEFS="-DFEATURE_X")
#   GENFLAGS extra flags for 'ddd generate' (e.g. GENFLAGS="--const-inputs")
#   TEMPLATES  directory of the c templates, defaulting to the examples shipped with DDD
#   CFLAGS   override the default warning set
#   CC       override the compiler
set -euo pipefail

PROJECT="${1:-examples/demo/demo.ddd.json}"
OUTPUT="${2:-build/gen}"
CC="${CC:-gcc}"
CFLAGS="${CFLAGS:--std=c11 -Wall -Wextra -Wpedantic -Werror -Wconversion -Wshadow -Wcast-qual -Wstrict-prototypes}"
CDEFS="${CDEFS:-}"
GENFLAGS="${GENFLAGS:-}"
TEMPLATES="${TEMPLATES:-$(ddd templates-dir)}"

log() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

log "generate  $PROJECT -> $OUTPUT ${GENFLAGS}"
read -r -a generate_flags <<<"$GENFLAGS"
ddd generate "$PROJECT" -o "$OUTPUT" --template-dir "$TEMPLATES" "${generate_flags[@]}"
# The severity overrides in GENFLAGS apply here too: pointed at a single component file,
# 'ddd list' would otherwise exit 1 on the missing producers that the generate step was
# explicitly told to tolerate, and take the whole run down with it.
read -r -a policy_flags <<<"$(printf '%s\n' "$GENFLAGS" | grep -oE -- '(-W [^ ]+|--strict)' | tr '\n' ' ')"
ddd list "$PROJECT" --format json "${policy_flags[@]}" >"$OUTPUT/variables.json"

compile_variant() {
    local label="$1"
    shift
    local defines=("$@")
    local objdir="$OUTPUT/obj-$label"
    rm -rf "$objdir"
    mkdir -p "$objdir"

    # One translation unit per generated header proves that every header is self
    # contained (compiles without anything included before it) and that its
    # include guard survives being included twice.
    local header name
    for header in "$OUTPUT"/*.h; do
        name="$(basename "$header" .h)"
        printf '#include "%s.h"\n#include "%s.h"\n' "$name" "$name" >"$objdir/tu_$name.c"
    done

    log "compile   [$label] ${defines[*]:-without extra defines}"
    local source object
    local objects=()
    local globals_objects=()
    for source in "$objdir"/tu_*.c; do
        object="$objdir/$(basename "${source%.c}").o"
        $CC $CFLAGS "${defines[@]}" -I"$OUTPUT" -c "$source" -o "$object"
        objects+=("$object")
    done
    for source in "$OUTPUT"/*.c; do
        object="$objdir/$(basename "${source%.c}").o"
        $CC $CFLAGS "${defines[@]}" -I"$OUTPUT" -c "$source" -o "$object"
        objects+=("$object")
        globals_objects+=("$object")
    done

    # Linking everything together is what actually proves the DDD promise: no
    # duplicate definition and no declaration without a definition behind it.
    log "link      [$label]"
    printf 'int main(void)\n{\n    return 0;\n}\n' >"$objdir/main.c"
    $CC $CFLAGS "${defines[@]}" -I"$OUTPUT" -o "$objdir/app" "${objects[@]}" "$objdir/main.c"
    "$objdir/app"

    log "symbols   [$label]"
    nm --defined-only --extern-only --format=posix "${globals_objects[@]}" \
        | awk 'NF >= 2 { print $1 }' | sort -u >"$objdir/symbols.txt"
    python3 /opt/ddd/bin/verify_symbols.py "$OUTPUT/variables.json" "$objdir/symbols.txt"
}

compile_variant base

if [ -n "$CDEFS" ]; then
    read -r -a extra_defines <<<"$CDEFS"
    compile_variant defines "${extra_defines[@]}"
fi

log "done      everything compiled, linked and verified"
