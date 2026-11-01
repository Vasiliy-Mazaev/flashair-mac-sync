#!/bin/bash
# Добавляет короткие команды утилиты FlashAir в файл настроек оболочки
# (~/.zshrc для zsh, ~/.bash_profile для bash).
#
#   ./install-aliases.sh           добавить или обновить алиасы
#   ./install-aliases.sh --remove  удалить алиасы
#
# Алиасы записываются одним блоком между метками, поэтому повторный запуск
# заменяет блок, а не дописывает второй. Перед изменением делается копия файла.
# Другой файл можно указать явно: RC_FILE=~/.zprofile ./install-aliases.sh

set -euo pipefail

PROJECT="$(cd "$(dirname "$0")" && pwd)"
BEGIN="# >>> flashair aliases >>>"
END="# <<< flashair aliases <<<"

# Имя, аргументы утилиты, описание
ALIASES=(
    "fa||любая команда: fa status, fa --help"
    "fas|status|состояние Wi-Fi, карты и журнала"
    "fac|connect|подключиться к сети карты"
    "fadc|disconnect|отключиться от сети карты"
    "fasc|scan|записать снимки с карты в журнал"
    "fadl|download|скачать новые снимки"
    "fadr|download --recheck|скачать всё, чего нет на диске"
    "fal|list|журнал без подключения к карте"
)

# Вывод в том же стиле, что и у утилиты
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

# Файл настроек оболочки
if [ -z "${RC_FILE:-}" ]; then
    case "$(basename "${SHELL:-}")" in
        zsh)  RC_FILE="$HOME/.zshrc" ;;
        bash) RC_FILE="$HOME/.bash_profile" ;;
        *)    fail "Оболочка ${SHELL:-неизвестна} не поддерживается. Укажите файл: RC_FILE=… $0" ;;
    esac
fi

remove_block() {
    # Всё между метками (включительно) выбрасывается; cat > сохраняет права файла
    local tmp
    tmp="$(mktemp)"
    awk -v b="$BEGIN" -v e="$END" '$0 == b { skip = 1 } !skip { print } $0 == e { skip = 0 }' "$RC_FILE" > "$tmp"
    cat "$tmp" > "$RC_FILE"
    rm -f "$tmp"
}

backup() {
    cp "$RC_FILE" "$RC_FILE.flashair-backup"
    info "Копия файла до изменения: $RC_FILE.flashair-backup"
}

if [ "${1:-}" = "--remove" ]; then
    step "Удаление алиасов FlashAir из $RC_FILE"
    if [ ! -f "$RC_FILE" ] || ! grep -qxF "$BEGIN" "$RC_FILE"; then
        ok "Алиасов нет, менять нечего"
        exit 0
    fi
    backup
    remove_block
    ok "Блок алиасов удалён"
    info "В уже открытых окнах терминала алиасы останутся до перезапуска"
    exit 0
elif [ -n "${1:-}" ]; then
    fail "Неизвестный параметр $1. Запуск: $0 [--remove]"
fi

step "Проверка окружения"
info "Папка проекта: $PROJECT"
case "$PROJECT" in
    *\'*) fail "В пути к проекту есть апостроф — алиасы с ним не записать" ;;
esac

command -v python3 > /dev/null || fail "Не найден python3"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || fail "Нужен Python 3.10 или новее, найден $(python3 --version 2>&1)"
ok "$(python3 --version 2>&1): $(command -v python3)"

[ -f "$PROJECT/settings.json" ] || warn "Нет settings.json — скопируйте settings.example.json и укажите SSID и пароль карты"

# Алиас с тем же именем, что у существующей программы, перекроет её
for entry in "${ALIASES[@]}"; do
    name="${entry%%|*}"
    if path="$(command -v "$name" 2>/dev/null)" && [ "${path#/}" != "$path" ]; then
        warn "Имя $name уже занято программой $path — алиас её перекроет"
    fi
done

step "Запись алиасов в $RC_FILE"
if [ -f "$RC_FILE" ]; then
    backup
    if grep -qxF "$BEGIN" "$RC_FILE"; then
        info "Алиасы уже были — заменяю блок"
        remove_block
    fi
else
    info "Файла нет — создаю"
fi

{
    echo "$BEGIN"
    echo "# Короткие команды утилиты FlashAir, добавлены $PROJECT/install-aliases.sh"
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
ok "Добавлено алиасов: ${#ALIASES[@]}"

step "Готово"
info "Новые окна терминала подхватят алиасы сами. В этом окне выполните:"
info "  source $RC_FILE"
