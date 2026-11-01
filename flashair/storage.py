"""Журнал файлов карты в SQLite: что видели и что уже скачали.

Путь на карте не годится как идентификатор: после форматирования карты или
сброса счётчика камера снова создаёт /DCIM/100MSDCF/DSC00001.JPG. Поэтому
снимок определяется тройкой «имя + размер + дата съёмки», а путь хранится
только как место, где файл видели в последний раз.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from . import log
from .card import CardFile

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _key(f: CardFile) -> tuple[str, int, str]:
    # Пустая строка вместо NULL: в SQLite NULL не участвуют в UNIQUE
    return f.name, f.size, f.modified.isoformat() if f.modified else ""


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and self._has_old_table():
            self._migrate_from_path_key()
        elif version == 0:
            self._create()

    def _create(self):
        self.conn.executescript(f"""
            CREATE TABLE files (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                modified TEXT NOT NULL,      -- дата съёмки из FAT, '' если не прочиталась
                card_path TEXT NOT NULL,     -- где файл видели на карте в последний раз
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                downloaded_at TEXT,
                local_path TEXT,
                UNIQUE (name, size, modified)
            );
            PRAGMA user_version = {SCHEMA_VERSION};
        """)

    def _has_old_table(self) -> bool:
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(files)")}
        return "path" in columns

    def _migrate_from_path_key(self):
        """Первая версия журнала была с ключом по пути на карте — переносим записи."""
        log.info(f"Обновляю журнал {self.path} до новой структуры")
        self.conn.execute("ALTER TABLE files RENAME TO files_old")
        self._create()
        self.conn.execute("""
            INSERT OR IGNORE INTO files
                (name, size, modified, card_path, first_seen, last_seen, downloaded_at, local_path)
            SELECT name, size, COALESCE(modified, ''), path, first_seen, last_seen, downloaded_at, local_path
            FROM files_old
        """)
        self.conn.execute("DROP TABLE files_old")
        self.conn.commit()

    def close(self):
        self.conn.close()

    def record_scan(self, files: list[CardFile]) -> int:
        """Сохраняет результат сканирования, возвращает число новых снимков."""
        before = self.count()
        now = _now()

        self.conn.executemany("""
            INSERT INTO files (name, size, modified, card_path, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (name, size, modified) DO UPDATE SET
                card_path = excluded.card_path,
                last_seen = excluded.last_seen
        """, [(*_key(f), f.path, now, now) for f in files])
        self.conn.commit()

        return self.count() - before

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    def is_downloaded(self, f: CardFile) -> bool:
        row = self.conn.execute(
            "SELECT downloaded_at FROM files WHERE name = ? AND size = ? AND modified = ?", _key(f)
        ).fetchone()
        return bool(row and row["downloaded_at"])

    def local_path(self, f: CardFile) -> Path | None:
        row = self.conn.execute(
            "SELECT local_path FROM files WHERE name = ? AND size = ? AND modified = ?", _key(f)
        ).fetchone()
        return Path(row["local_path"]) if row and row["local_path"] else None

    def mark_downloaded(self, f: CardFile, local_path: Path):
        self.conn.execute(
            "UPDATE files SET downloaded_at = ?, local_path = ? WHERE name = ? AND size = ? AND modified = ?",
            (_now(), str(local_path), *_key(f)),
        )
        self.conn.commit()

    def all(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM files ORDER BY modified, name").fetchall()
