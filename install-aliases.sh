#!/bin/bash
# Adds short commands for the FlashAir utility to the shell startup file
# (~/.zshrc for zsh, ~/.bash_profile for bash).
#
#   ./install-aliases.sh           add or update the aliases
#   ./install-aliases.sh --remove  remove the aliases
#
# The aliases are written as one block between markers, so running the script
# again replaces the block instead of adding a second one. A copy of the file
# is saved before any change. Another file can be given explicitly:
# RC_FILE=~/.zprofile ./install-aliases.sh

set -euo pipefail

PROJECT="$(cd "$(dirname "$0")" && pwd)"
BEGIN="# >>> flashair aliases >>>"
END="# <<< flashair aliases <<<"

# Name, utility arguments, description
ALIASES=(
    "fa||any command: fa status, fa --help"
    "fas|status|Wi-Fi, card and journal status"
    "fac|connect|join the card's network"
    "fadc|disconnect|leave the card's network"
    "fasc|scan|record the card's photos in the journal"
    "fadl|download|download new photos"
    "fadr|download --recheck|download everything missing on disk"
    "fal|list|journal without connecting to the card"
)

# Output in the same style as the utility
if [ -t 1 ]; then
    step() { printf '\n\033[1;36m▶ \033[0m\033[1m%s\033[0m\n' "$1"; }
    ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
    warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
    fail() { printf '\033[31m✗\033[0m %s\n' "$1" >&2; exit 1; }
else
    step() { printf '\n▶ %s\n' "$1"; }
    ok()   { printf '  ✓ %s\n' "$1"; }
    warn() { printf '  ! %s\n' "$1"; }
    fail() { printf '✗ %s\n' "$1" >&2; exit 1; }
fi
info() { printf '  %s\n' "$1"; }

# Shell startup file
if [ -z "${RC_FILE:-}" ]; then
    case "$(basename "${SHELL:-}")" in
        zsh)  RC_FILE="$HOME/.zshrc" ;;
        bash) RC_FILE="$HOME/.bash_profile" ;;
        *)    fail "Shell ${SHELL:-unknown} is not supported. Set the file explicitly: RC_FILE=… $0" ;;
    esac
fi

remove_block() {
    # Everything between the markers (inclusive) is dropped; cat > keeps the file's permissions
    local tmp
    tmp="$(mktemp)"
    awk -v b="$BEGIN" -v e="$END" '$0 == b { skip = 1 } !skip { print } $0 == e { skip = 0 }' "$RC_FILE" > "$tmp"
    cat "$tmp" > "$RC_FILE"
    rm -f "$tmp"
}

backup() {
    cp "$RC_FILE" "$RC_FILE.flashair-backup"
    info "Copy of the file before the change: $RC_FILE.flashair-backup"
}

if [ "${1:-}" = "--remove" ]; then
    step "Removing FlashAir aliases from $RC_FILE"
    if [ ! -f "$RC_FILE" ] || ! grep -qxF "$BEGIN" "$RC_FILE"; then
        ok "No aliases found, nothing to change"
        exit 0
    fi
    backup
    remove_block
    ok "Alias block removed"
    info "Terminal windows that are already open keep the aliases until restarted"
    exit 0
elif [ -n "${1:-}" ]; then
    fail "Unknown option $1. Usage: $0 [--remove]"
fi

step "Checking the environment"
info "Project folder: $PROJECT"
case "$PROJECT" in
    *\'*) fail "The project path contains an apostrophe — aliases can't be written with it" ;;
esac

command -v python3 > /dev/null || fail "python3 not found"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || fail "Python 3.10 or newer is required, found $(python3 --version 2>&1)"
ok "$(python3 --version 2>&1): $(command -v python3)"

[ -f "$PROJECT/settings.json" ] || warn "No settings.json — copy settings.example.json and set the card's SSID and password"

# An alias with the same name as an existing program shadows it
for entry in "${ALIASES[@]}"; do
    name="${entry%%|*}"
    if path="$(command -v "$name" 2>/dev/null)" && [ "${path#/}" != "$path" ]; then
        warn "The name $name is already taken by $path — the alias will shadow it"
    fi
done

step "Writing aliases to $RC_FILE"
if [ -f "$RC_FILE" ]; then
    backup
    if grep -qxF "$BEGIN" "$RC_FILE"; then
        info "Aliases were already there — replacing the block"
        remove_block
    fi
else
    info "The file doesn't exist — creating it"
fi

{
    echo "$BEGIN"
    echo "# Short commands for the FlashAir utility, added by $PROJECT/install-aliases.sh"
    for entry in "${ALIASES[@]}"; do
        IFS='|' read -r name args _ <<< "$entry"
        echo "alias $name='PYTHONPATH=\"$PROJECT\" python3 -m flashair${args:+ $args}'"
    done
    echo "$END"
} >> "$RC_FILE"

for entry in "${ALIASES[@]}"; do
    IFS='|' read -r name _ description <<< "$entry"
    printf '  %-6s %s\n' "$name" "$description"
done
ok "Aliases added: ${#ALIASES[@]}"

step "Done"
info "New terminal windows pick up the aliases automatically. In this window run:"
info "  source $RC_FILE"
