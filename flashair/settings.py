"""Загрузка настроек из JSON-файла (по умолчанию settings.json в папке проекта)."""

import json
from dataclasses import dataclass
from pathlib import Path

from . import FlashAirError

# Папка проекта, а не текущая: утилита запускается из любого места (алиасы)
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "settings.json"


@dataclass
class Settings:
    # Карта
    ssid: str
    password: str
    host: str
    timeout: float

    # Wi-Fi
    interface: str  # пусто — определить автоматически
    connect_attempts: int
    connect_wait: float
    forget_network: bool  # убирать сеть карты из списка известных при отключении

    # Файлы на карте
    root: str
    extensions: frozenset[str]  # пусто — все файлы
    ignore: tuple[str, ...]  # шаблоны имён или путей, которые не считаются снимками

    # Локальное хранилище
    database: Path
    download_dir: Path


def load(path: Path = DEFAULT_PATH) -> Settings:
    if not path.exists():
        raise FlashAirError(
            f"Нет файла настроек {path}. Скопируйте settings.example.json в {path} и укажите SSID и пароль карты."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FlashAirError(f"Ошибка в {path}: {e}") from e

    card = data.get("card", {})
    wifi = data.get("wifi", {})
    files = data.get("files", {})
    storage = data.get("storage", {})

    if not card.get("ssid") or not card.get("password"):
        raise FlashAirError(f"В {path} не заданы card.ssid и card.password")

    # Относительные пути считаются от папки с файлом настроек
    base = path.resolve().parent

    def resolve(value: str) -> Path:
        p = Path(value).expanduser()
        return p if p.is_absolute() else base / p

    return Settings(
        ssid=card["ssid"],
        password=card["password"],
        host=card.get("host", "192.168.0.1"),
        timeout=float(card.get("timeout", 5)),
        interface=wifi.get("interface", ""),
        connect_attempts=int(wifi.get("connect_attempts", 3)),
        connect_wait=float(wifi.get("connect_wait", 30)),
        forget_network=bool(wifi.get("forget_network", True)),
        root=files.get("root", "/DCIM"),
        extensions=frozenset(e.upper().lstrip(".") for e in files.get("extensions", [])),
        # FA000001.JPG — служебная картинка FlashAir, лежит на каждой карте
        ignore=tuple(files.get("ignore", ["FA000001.JPG"])),
        database=resolve(storage.get("database", "flashair.db")),
        download_dir=resolve(storage.get("download_dir", "downloads")),
    )
