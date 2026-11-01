"""Наглядный вывод в терминал: этапы, системные команды, результаты."""

import shutil
import sys
import time

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


class Progress:
    """Прогресс всей сессии загрузки.

    В терминале одна строка перерисовывается на месте: сначала общий прогресс,
    в конце — текущий файл. Если строка не влезает в ширину окна, обрезается
    часть про файл. Над строкой остаётся список уже скачанных файлов.
    """

    REDRAW = 0.1  # не чаще раза в 0,1 с

    def __init__(self, count: int, total: int):
        self.count = count
        self.total = total
        self.done = 0  # байт за сессию, включая завершённые файлы
        self.index = 0
        self.start = time.monotonic()
        self.drawn = 0.0

    def begin(self, name: str, file_size: int):
        self.index += 1
        self.name = name
        self.file_size = file_size
        self.file_done = 0
        self._draw(force=True)

    def advance(self, n: int):
        self.file_done += n
        self.done += n
        self._draw()

    def finish(self):
        self._clear()
        percent = self.done * 100 // self.total if self.total else 100
        print(f"  {_paint('32', '✓')} [{self.index}/{self.count}] {self.name}  {size(self.file_size)}  (всего {percent}%)")

    def drop(self):
        """Файл не скачан или не нужен: его байты исключаются из общего объёма."""
        self.done -= self.file_done
        self.total -= self.file_size
        self._clear()

    def close(self):
        self._clear()

    def line(self) -> str:
        percent = self.done * 100 // self.total if self.total else 100
        elapsed = time.monotonic() - self.start
        speed = self.done / elapsed if elapsed > 0 else 0
        text = f"  ↓ Всего {percent:3d}%  [{self.index}/{self.count}]  {size(self.done)} / {size(self.total)}"

        # Оставшееся время важнее скорости, поэтому идёт раньше и обрезается позже
        if speed:
            left = int((self.total - self.done) / speed)
            text += f"  ~{left // 60}:{left % 60:02d}  {size(int(speed))}/с"

        if self.file_done < self.file_size:
            file_percent = self.file_done * 100 // self.file_size
            text += f"  · {self.name} {file_percent}%"

        return text

    def _draw(self, force: bool = False):
        now = time.monotonic()
        if not _COLOR or (not force and now - self.drawn < self.REDRAW):
            return

        self.drawn = now
        width = shutil.get_terminal_size().columns - 1
        # \033[K стирает остаток прошлой строки, если новая короче
        print("\r" + self.line()[:width] + "\033[K", end="", flush=True)

    def _clear(self):
        if _COLOR:
            print("\r\033[K", end="", flush=True)


def size(n: int) -> str:
    for unit in ("Б", "КБ", "МБ"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ГБ"
