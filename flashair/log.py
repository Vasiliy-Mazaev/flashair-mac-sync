"""Наглядный вывод в терминал: этапы, системные команды, результаты."""

import sys

_COLOR = sys.stdout.isatty()


def _paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def step(text: str):
    """Начало крупного этапа."""
    print()
    print(_paint("1;36", "▶ ") + _paint("1", text))


def info(text: str):
    print("  " + text)


def cmd(args: list[str]):
    """Системная команда, которую утилита сейчас выполняет."""
    print("  " + _paint("2", "$ " + " ".join(args)))


def ok(text: str):
    print("  " + _paint("32", "✓ ") + text)


def warn(text: str):
    print("  " + _paint("33", "! ") + text)


def fail(text: str):
    print(_paint("31", "✗ ") + text, file=sys.stderr)


def progress(name: str, done: int, total: int):
    """Строка прогресса загрузки; в терминале перерисовывается на месте."""
    percent = done * 100 // total if total else 100
    line = f"  ↓ {name}  {percent:3d}%  {size(done)} / {size(total)}"

    if _COLOR:
        print("\r" + line, end="", flush=True)
        if done >= total:
            print()
    elif done >= total:
        print(line)


def size(n: int) -> str:
    for unit in ("Б", "КБ", "МБ"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ГБ"
