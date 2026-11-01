"""Журнал файлов карты в SQLite: что видели и что уже скачали."""

import sqlite3
from datetime import datetime
from pathlib import Path

from .card import CardFile


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                modified TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                downloaded_at TEXT,
                local_path TEXT
            )
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def record_scan(self, files: list[CardFile]) -> int:
        """Сохраняет результат сканирования, возвращает число новых файлов."""
        known = {row["path"] for row in self.conn.execute("SELECT path FROM files")}
        now = _now()

        # Если размер файла изменился, отметка о загрузке сбрасывается
        self.conn.executemany("""
            INSERT INTO files (path, name, size, modified, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                size = excluded.size,
                modified = excluded.modified,
                last_seen = excluded.last_seen,
                downloaded_at = CASE WHEN files.size = excluded.size THEN files.downloaded_at END,
                local_path = CASE WHEN files.size = excluded.size THEN files.local_path END
        """, [
            (f.path, f.name, f.size, f.modified.isoformat() if f.modified else None, now, now)
            for f in files
        ])
        self.conn.commit()

        return sum(f.path not in known for f in files)

    def is_downloaded(self, path: str) -> bool:
        row = self.conn.execute("SELECT downloaded_at FROM files WHERE path = ?", (path,)).fetchone()
        return bool(row and row["downloaded_at"])

    def mark_downloaded(self, path: str, local_path: Path):
        self.conn.execute(
            "UPDATE files SET downloaded_at = ?, local_path = ? WHERE path = ?",
            (_now(), str(local_path), path),
        )
        self.conn.commit()

    def all(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM files ORDER BY path").fetchall()
