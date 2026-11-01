"""HTTP-API карты FlashAir (command.cgi) на urllib."""

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import FlashAirError, log

ATTR_DIRECTORY = 0x10
CHUNK = 64 * 1024

# Карта в локальной сети: системные прокси обходим
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class CardFile:
    path: str
    name: str
    size: int
    attributes: int
    modified: datetime | None

    @property
    def is_dir(self) -> bool:
        return bool(self.attributes & ATTR_DIRECTORY)

    @property
    def extension(self) -> str:
        return Path(self.name).suffix.lstrip(".").upper()


def fat_datetime(date: int, time: int) -> datetime | None:
    """Дата и время в формате FAT (два 16-битных числа)."""
    try:
        return datetime(
            (date >> 9) + 1980, (date >> 5) & 0x0F, date & 0x1F,
            time >> 11, (time >> 5) & 0x3F, (time & 0x1F) * 2,
        )
    except ValueError:
        return None


class Card:
    def __init__(self, host: str, timeout: float):
        self.base = f"http://{host}"
        self.timeout = timeout

    def command(self, op: int, timeout: float | None = None, **params) -> str:
        query = urllib.parse.urlencode({"op": op, **params}, safe="/")
        url = f"{self.base}/command.cgi?{query}"

        try:
            with _opener.open(url, timeout=timeout or self.timeout) as r:
                return r.read().decode("utf-8", "replace").strip()
        except (urllib.error.URLError, OSError) as e:
            raise FlashAirError(f"Карта не отвечает ({url}): {e}") from e

    def ssid(self, timeout: float | None = None) -> str | None:
        """SSID карты (op=104) или None, если карта недоступна."""
        try:
            return self.command(104, timeout=timeout)
        except FlashAirError:
            return None

    def firmware(self) -> str:
        return self.command(108)

    def list_dir(self, directory: str) -> list[CardFile]:
        """Содержимое одной папки (op=100). Строка: папка,имя,размер,атрибуты,дата,время."""
        text = self.command(100, DIR=directory)
        prefix = directory.rstrip("/") + ","
        result = []

        for line in text.splitlines():
            line = line.strip()
            if not line or line == "WLANSD_FILELIST":
                continue

            # Имя может содержать запятые, поэтому числовые поля отделяем справа
            head, *numbers = line.rsplit(",", 4)
            if len(numbers) != 4:
                continue

            name = head[len(prefix):] if head.startswith(prefix) else head.split(",", 1)[-1]
            size, attributes, date, time = map(int, numbers)

            result.append(CardFile(
                path=f"{directory.rstrip('/')}/{name}",
                name=name,
                size=size,
                attributes=attributes,
                modified=fat_datetime(date, time),
            ))

        return result

    def walk(self, directory: str) -> list[CardFile]:
        """Все файлы в папке и вложенных папках."""
        log.info(f"Читаю папку {directory}")
        files = []

        for entry in self.list_dir(directory):
            if entry.is_dir:
                files.extend(self.walk(entry.path))
            else:
                files.append(entry)

        return files

    def download(self, file: CardFile, target: Path, on_chunk: Callable[[int], None]):
        """Скачивает файл во временный .part и переименовывает после проверки размера.

        on_chunk получает размер каждого принятого куска — для прогресса.
        """
        url = self.base + urllib.parse.quote(file.path)
        part = target.with_name(target.name + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        done = 0

        try:
            with _opener.open(url, timeout=self.timeout) as r, part.open("wb") as f:
                while chunk := r.read(CHUNK):
                    f.write(chunk)
                    done += len(chunk)
                    on_chunk(len(chunk))
        except (urllib.error.URLError, OSError) as e:
            part.unlink(missing_ok=True)
            raise FlashAirError(f"Ошибка загрузки {file.path}: {e}") from e

        if done != file.size:
            part.unlink(missing_ok=True)
            raise FlashAirError(f"{file.path}: получено {done} байт вместо {file.size}")

        part.replace(target)
