"""Командная строка: python -m flashair <команда>."""

import argparse
import sys
import time
from pathlib import Path

from . import FlashAirError, connection, log, wifi
from .card import Card, CardFile
from .settings import DEFAULT_PATH, Settings, load
from .storage import Storage


def scan(s: Settings, card: Card, db: Storage) -> list[CardFile]:
    log.step(f"Сканирование карты, папка {s.root}")
    files = card.walk(s.root)

    if s.extensions:
        media = [f for f in files if f.extension in s.extensions]
        skipped = len(files) - len(media)
        if skipped:
            log.info(f"Пропущено файлов с другими расширениями: {skipped}")
        files = media

    new = db.record_scan(files)
    total = sum(f.size for f in files)
    log.ok(f"Найдено файлов: {len(files)} ({log.size(total)}), новых: {new}")
    log.info(f"Журнал обновлён: {db.path}")
    return files


def is_same_file(path: Path, f: CardFile) -> bool:
    """Локальный файл — тот же снимок: совпадают размер и время (его ставит card.download)."""
    st = path.stat()
    return st.st_size == f.size and f.modified is not None and int(st.st_mtime) == int(f.modified.timestamp())


def local_target(s: Settings, f: CardFile) -> tuple[Path, bool]:
    """Куда сохранить снимок и лежит ли он там уже.

    Папки по дате съёмки: downloads/2026-07-24/DSC00206.JPG. Имена после
    форматирования карты повторяются, поэтому чужой файл с тем же именем
    не перезаписывается — новый получает суффикс: DSC00206_1.JPG.
    """
    folder = s.download_dir / (f.modified.strftime("%Y-%m-%d") if f.modified else "без даты")
    name = Path(f.name)
    path = folder / f.name
    n = 0

    while path.exists():
        if is_same_file(path, f):
            return path, True
        n += 1
        path = folder / f"{name.stem}_{n}{name.suffix}"

    return path, False


def download(s: Settings, card: Card, db: Storage, files: list[CardFile]):
    pending = [f for f in files if not db.is_downloaded(f)]

    log.step(f"Загрузка в {s.download_dir}")
    if not pending:
        log.ok("Все файлы уже скачаны")
        return

    # Файлы, которые уже лежат локально, не скачиваем и не учитываем в общем объёме
    queue = []
    for f in pending:
        path, exists = local_target(s, f)
        if exists:
            log.info(f"{f.name}: уже есть локально ({path}), отмечаю как скачанный")
            db.mark_downloaded(f, path)
        else:
            queue.append(f)

    if not queue:
        log.ok("Все файлы уже скачаны")
        return

    log.info(f"К загрузке: {len(queue)} файл(ов), {log.size(sum(f.size for f in queue))}")
    progress = log.Progress(len(queue), sum(f.size for f in queue))
    errors = 0

    try:
        for f in queue:
            progress.begin(f.name, f.size)

            # Место выбирается прямо перед загрузкой, чтобы учесть файлы, скачанные в этой сессии
            path, exists = local_target(s, f)
            if exists:
                progress.drop()
                db.mark_downloaded(f, path)
                continue

            try:
                card.download(f, path, progress.advance)
            except FlashAirError as e:
                progress.drop()
                log.warn(str(e))
                errors += 1
                continue

            db.mark_downloaded(f, path)
            progress.finish()
    finally:
        progress.close()

    elapsed = time.monotonic() - progress.start
    summary = f"{log.size(progress.done)} за {int(elapsed) // 60}:{int(elapsed) % 60:02d}"
    if errors:
        log.warn(f"Скачано {len(queue) - errors} из {len(queue)} ({summary}), ошибок: {errors}")
    else:
        log.ok(f"Скачано файлов: {len(queue)} ({summary})")


def cmd_status(s: Settings, card: Card, args):
    log.step("Состояние")
    iface = connection.interface(s)
    ip = wifi.ip_address(iface)
    log.info(f"Wi-Fi: {'включён' if wifi.is_powered(iface) else 'выключен'}, IP {ip or 'нет'}")

    ssid = card.ssid(timeout=2)
    if ssid == s.ssid:
        log.ok(f"Карта «{ssid}» доступна, прошивка {card.firmware()}")
    elif ssid:
        log.warn(f"На {s.host} отвечает другая карта: «{ssid}»")
    else:
        log.info(f"Карта на {s.host} недоступна")

    # Без IP на Wi-Fi маршрут к карте неизбежно идёт через другой интерфейс
    if ip:
        connection.check_route(s, iface)

    if s.database.exists():
        rows = Storage(s.database).all()
        done = sum(1 for r in rows if r["downloaded_at"])
        log.info(f"Журнал {s.database}: файлов {len(rows)}, скачано {done}")


def cmd_connect(s: Settings, card: Card, args):
    connection.connect(s, card)


def cmd_disconnect(s: Settings, card: Card, args):
    connection.disconnect(s, card)


def cmd_scan(s: Settings, card: Card, args):
    db = Storage(s.database)
    with connection.session(s, card, keep=args.keep):
        scan(s, card, db)
    db.close()


def cmd_download(s: Settings, card: Card, args):
    db = Storage(s.database)
    with connection.session(s, card, keep=args.keep):
        files = scan(s, card, db)
        download(s, card, db, files)
    db.close()


def cmd_list(s: Settings, card: Card, args):
    log.step(f"Журнал {s.database}")
    if not s.database.exists():
        log.info("Журнал пуст: сначала выполните scan")
        return

    rows = Storage(s.database).all()
    for r in rows:
        mark = "✓" if r["downloaded_at"] else "·"
        modified = r["modified"].replace("T", " ") or "без даты"
        print(f"  {mark} {modified:<19}  {r['name']:<16} {log.size(r['size']):>10}  {r['card_path']}")
    log.info(f"Всего: {len(rows)}, скачано: {sum(1 for r in rows if r['downloaded_at'])}")


COMMANDS = {
    "status": (cmd_status, "показать состояние Wi-Fi, карты и журнала"),
    "connect": (cmd_connect, "подключиться к сети карты"),
    "disconnect": (cmd_disconnect, "отключиться от сети карты"),
    "scan": (cmd_scan, "подключиться, прочитать список файлов в журнал, отключиться"),
    "download": (cmd_download, "то же, что scan, плюс скачать новые файлы"),
    "list": (cmd_list, "показать журнал без подключения к карте"),
}


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m flashair", description="Работа с картой FlashAir по Wi-Fi")
    parser.add_argument("--settings", type=Path, default=DEFAULT_PATH, help=f"файл настроек (по умолчанию {DEFAULT_PATH})")
    sub = parser.add_subparsers(dest="command", required=True, metavar="команда")

    for name, (_, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        if name in ("scan", "download"):
            p.add_argument("--keep", action="store_true", help="не отключаться от карты в конце")

    args = parser.parse_args()

    try:
        s = load(args.settings)
        card = Card(s.host, s.timeout)
        COMMANDS[args.command][0](s, card, args)
    except FlashAirError as e:
        log.fail(str(e))
        return 1
    except KeyboardInterrupt:
        log.fail("Прервано пользователем")
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
