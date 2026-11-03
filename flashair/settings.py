"""Loads settings from a JSON file (settings.json in the project folder by default)."""

import json
from dataclasses import dataclass
from pathlib import Path

from . import FlashAirError

# The project folder, not the current one: the utility runs from anywhere (aliases)
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "settings.json"

# Photos and videos of common cameras. The whole card is scanned, so the
# camera's service files (XML, BIN, INP…) are filtered out by extension
DEFAULT_EXTENSIONS = [
    "JPG", "JPEG", "HEIC", "HIF",
    "ARW", "CR2", "CR3", "NEF", "RAF", "ORF", "RW2", "DNG",
    "MP4", "MOV", "MTS", "M2TS", "AVI",
]

DEFAULT_IGNORE = [
    "FA000001.JPG",                # FlashAir service image found on every card
    "/PRIVATE/M4ROOT/THMBNL/*",    # Sony: video thumbnails
    "/PRIVATE/M4ROOT/SUB/*",       # Sony: low-quality proxy copies of videos
]


@dataclass
class Settings:
    # Card
    ssid: str
    password: str
    host: str
    timeout: float

    # Wi-Fi
    interface: str  # empty — detect automatically
    connect_attempts: int
    connect_wait: float
    forget_network: bool  # remove the card's network from known networks on disconnect

    # Files on the card
    root: str
    extensions: frozenset[str]  # empty — all files
    ignore: tuple[str, ...]  # name or path patterns that are not photos

    # Local storage
    database: Path
    download_dir: Path


def load(path: Path = DEFAULT_PATH) -> Settings:
    if not path.exists():
        raise FlashAirError(
            f"No settings file {path}. Copy settings.example.json to {path} and set the card's SSID and password."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FlashAirError(f"Error in {path}: {e}") from e

    card = data.get("card", {})
    wifi = data.get("wifi", {})
    files = data.get("files", {})
    storage = data.get("storage", {})

    if not card.get("ssid") or not card.get("password"):
        raise FlashAirError(f"card.ssid and card.password are not set in {path}")

    # Relative paths are resolved from the settings file's folder
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
        root=files.get("root", "/"),
        extensions=frozenset(e.upper().lstrip(".") for e in files.get("extensions", DEFAULT_EXTENSIONS)),
        ignore=tuple(files.get("ignore", DEFAULT_IGNORE)),
        database=resolve(storage.get("database", "flashair.db")),
        download_dir=resolve(storage.get("download_dir", "downloads")),
    )
