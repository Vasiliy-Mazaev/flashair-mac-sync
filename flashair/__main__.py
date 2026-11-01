"""Command line: python -m flashair <command>."""

import argparse
import fnmatch
import sys
import time
from pathlib import Path

from . import FlashAirError, connection, log, wifi
from .card import Card, CardFile
from .settings import DEFAULT_PATH, Settings, load
from .storage import Storage


def is_ignored(s: Settings, f: CardFile) -> bool:
    """A files.ignore pattern matches the name or the full card path (case-insensitive)."""
    return any(
        fnmatch.fnmatch(f.name.upper(), p.upper()) or fnmatch.fnmatch(f.path.upper(), p.upper())
        for p in s.ignore
    )


def scan(s: Settings, card: Card, db: Storage) -> list[CardFile]:
    log.step(f"Scanning the card, folder {s.root}")
    files = card.walk(s.root)

    ignored = [f for f in files if is_ignored(s, f)]
    if ignored:
        log.info(f"Ignored by the files.ignore setting: {', '.join(f.path for f in ignored)}")
        files = [f for f in files if f not in ignored]

    if s.extensions:
        media = [f for f in files if f.extension in s.extensions]
        skipped = len(files) - len(media)
        if skipped:
            log.info(f"Skipped files with other extensions: {skipped}")
        files = media

    new = db.record_scan(files)
    total = sum(f.size for f in files)
    log.ok(f"Files found: {len(files)} ({log.size(total)}), new: {new}")
    log.info(f"Journal updated: {db.path}")
    return files


def is_same_file(path: Path, f: CardFile) -> bool:
    """The local file is the same photo: size and time match (card.download sets the time)."""
    st = path.stat()
    return st.st_size == f.size and f.modified is not None and int(st.st_mtime) == int(f.modified.timestamp())


def local_target(s: Settings, f: CardFile) -> tuple[Path, bool]:
    """Where to save the photo and whether it is already there.

    Folders by capture date: downloads/2026-07-24/DSC00206.JPG. Names repeat
    after the card is formatted, so a different file with the same name is
    never overwritten — the new one gets a suffix: DSC00206_1.JPG.
    """
    folder = s.download_dir / (f.modified.strftime("%Y-%m-%d") if f.modified else "undated")
    name = Path(f.name)
    path = folder / f.name
    n = 0

    while path.exists():
        if is_same_file(path, f):
            return path, True
        n += 1
        path = folder / f"{name.stem}_{n}{name.suffix}"

    return path, False


def find_local(s: Settings, db: Storage, f: CardFile) -> Path | None:
    """Where the photo already is on disk: at the journal path or in its date folder."""
    recorded = db.local_path(f)
    if recorded and recorded.is_file() and is_same_file(recorded, f):
        return recorded

    path, exists = local_target(s, f)
    return path if exists else None


def download(s: Settings, card: Card, db: Storage, files: list[CardFile], recheck: bool = False):
    """Downloads new photos.

    recheck — don't trust the "downloaded" marks in the journal, check every
    photo on disk instead: this restores files deleted by accident.
    """
    log.step(f"Downloading to {s.download_dir}")

    if recheck:
        log.info("Ignoring journal marks: checking every file on disk")
        pending = files
    else:
        pending = [f for f in files if not db.is_downloaded(f)]

    if not pending:
        log.ok("All files are already downloaded")
        return

    # Files that are already on disk are not downloaded and not counted in the total
    queue = []
    present = 0
    for f in pending:
        path = find_local(s, db, f)
        if path:
            present += 1
            if not recheck:
                log.info(f"{f.name}: already on disk ({path}), marking as downloaded")
            db.mark_downloaded(f, path)
        else:
            if recheck and db.is_downloaded(f):
                log.info(f"{f.name}: marked as downloaded but missing on disk — downloading again")
            queue.append(f)

    if recheck:
        log.ok(f"Already on disk: {present} of {len(pending)}")

    if not queue:
        log.ok("All files are already downloaded")
        return

    log.info(f"To download: {len(queue)} file(s), {log.size(sum(f.size for f in queue))}")
    progress = log.Progress(len(queue), sum(f.size for f in queue))
    errors = 0

    try:
        for f in queue:
            progress.begin(f.name, f.size)

            # The target is picked right before downloading to account for files saved in this session
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
    summary = f"{log.size(progress.done)} in {int(elapsed) // 60}:{int(elapsed) % 60:02d}"
    if errors:
        log.warn(f"Downloaded {len(queue) - errors} of {len(queue)} ({summary}), errors: {errors}")
    else:
        log.ok(f"Files downloaded: {len(queue)} ({summary})")


def cmd_status(s: Settings, card: Card, args):
    log.step("Status")
    iface = connection.interface(s)
    ip = wifi.ip_address(iface)
    log.info(f"Wi-Fi: {'on' if wifi.is_powered(iface) else 'off'}, IP {ip or 'none'}")

    ssid = card.ssid(timeout=2)
    if ssid == s.ssid:
        log.ok(f"Card \"{ssid}\" is reachable, firmware {card.firmware()}")
    elif ssid:
        log.warn(f"A different card answers at {s.host}: \"{ssid}\"")
    else:
        log.info(f"The card at {s.host} is not reachable")

    # Without an IP on Wi-Fi the route to the card always goes through another interface
    if ip:
        connection.check_route(s, iface)

    if s.database.exists():
        rows = Storage(s.database).all()
        done = sum(1 for r in rows if r["downloaded_at"])
        log.info(f"Journal {s.database}: {len(rows)} files, {done} downloaded")


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
        download(s, card, db, files, recheck=args.recheck)
    db.close()


def cmd_list(s: Settings, card: Card, args):
    log.step(f"Journal {s.database}")
    if not s.database.exists():
        log.info("The journal is empty: run scan first")
        return

    rows = Storage(s.database).all()
    for r in rows:
        mark = "✓" if r["downloaded_at"] else "·"
        modified = r["modified"].replace("T", " ") or "undated"
        print(f"  {mark} {modified:<19}  {r['name']:<16} {log.size(r['size']):>10}  {r['card_path']}")
    log.info(f"Total: {len(rows)}, downloaded: {sum(1 for r in rows if r['downloaded_at'])}")


COMMANDS = {
    "status": (cmd_status, "show Wi-Fi, card and journal status"),
    "connect": (cmd_connect, "join the card's network"),
    "disconnect": (cmd_disconnect, "leave the card's network"),
    "scan": (cmd_scan, "connect, record the file list in the journal, disconnect"),
    "download": (cmd_download, "same as scan, plus download new files"),
    "list": (cmd_list, "show the journal without connecting to the card"),
}


HELP = """\
flashair-mac-sync — copy photos from a Toshiba FlashAir W-04 card over Wi-Fi

Usage:  python3 -m flashair [--settings FILE] COMMAND [OPTIONS]
        fa COMMAND [OPTIONS]               (after ./install-aliases.sh)

Commands:                                                         alias
  status                 Wi-Fi, card and journal status           fas
  connect                join the card's network                  fac
  disconnect             leave the card's network                 fadc
  scan [--keep]          record the card's photos in the journal  fasc
  download [--keep]      same + download new photos               fadl
  download --recheck     download everything missing on disk      fadr
  list                   journal without connecting to the card   fal

Options:
  --keep                 stay on the card's network at the end
  --recheck              ignore "downloaded" marks, check files on disk
  --settings FILE        settings file (default: settings.json in the project folder)
  -h, --help             this help; COMMAND --help — help for a command
"""


class Parser(argparse.ArgumentParser):
    def error(self, message: str):
        log.fail(f"{message}. Help: python3 -m flashair --help")
        sys.exit(2)


def main() -> int:
    parser = Parser(prog="python3 -m flashair", add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--settings", type=Path, default=DEFAULT_PATH)
    sub = parser.add_subparsers(dest="command", metavar="command", parser_class=Parser)

    for name, (_, help_text) in COMMANDS.items():
        p = sub.add_parser(name, description=help_text, add_help=False)
        group = p.add_argument_group("options")
        group.add_argument("-h", "--help", action="help", help="this help")
        if name in ("scan", "download"):
            group.add_argument("--keep", action="store_true", help="stay on the card's network at the end")
        if name == "download":
            group.add_argument(
                "--recheck", action="store_true",
                help="ignore \"downloaded\" marks: check every file on disk and download the missing ones",
            )

    args = parser.parse_args()

    if args.help or not args.command:
        print(HELP, end="")
        return 0 if args.help else 2

    try:
        s = load(args.settings)
        card = Card(s.host, s.timeout)
        COMMANDS[args.command][0](s, card, args)
    except FlashAirError as e:
        log.fail(str(e))
        return 1
    except KeyboardInterrupt:
        log.fail("Interrupted by user")
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
