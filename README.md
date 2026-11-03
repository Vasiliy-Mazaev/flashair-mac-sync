# flashair-mac-sync

[Русская версия →](https://github.com/Vasiliy-Mazaev/flashair-mac-sync/tree/Russian)

Download photos from a Toshiba FlashAir W-04 Wi-Fi SD card on macOS. The utility automatically joins
the card's Wi-Fi and switches back to your network, skips already downloaded photos, sorts them into
date folders and restores accidentally deleted ones. Pure Python 3.10+, no dependencies: Wi-Fi is
controlled with the built-in `networksetup`, `ipconfig` and `route`.

## Setup

```bash
cp settings.example.json settings.json
```

Put your card's `card.ssid` and `card.password` into `settings.json`. Other settings:

| Key | Meaning |
|---|---|
| `card.host`, `card.timeout` | card address and HTTP timeout, s |
| `wifi.interface` | Wi-Fi device; empty — detect automatically |
| `wifi.connect_attempts`, `wifi.connect_wait` | connection attempts and how long to wait for the card, s |
| `wifi.forget_network` | forget the card's network on disconnect so macOS doesn't rejoin it by itself |
| `files.root`, `files.extensions` | folder on the card (default `/` — the whole card) and photo/video extensions; empty list — all files |
| `files.ignore` | name or path patterns that are not photos; folders covered by a `/FOLDER/*` pattern are not entered. By default: the FlashAir service image `FA000001.JPG`, Sony video thumbnails and proxy copies (`/PRIVATE/M4ROOT/THMBNL/*`, `/PRIVATE/M4ROOT/SUB/*`) |
| `storage.database`, `storage.download_dir` | SQLite journal and download folder (relative to the settings file) |

`settings.json`, the journal and downloads are kept out of git.

## Journal and downloads

The whole card is scanned: cameras store files differently (Sony, for example, writes videos to
`/PRIVATE/M4ROOT/CLIP`, not `/DCIM`). The camera's service files are filtered out by the extension list.

File names and paths on the card repeat after formatting or a counter reset, so a photo is
identified in the journal by its name, size and capture time. Files are saved into folders by
capture date (`downloads/2026-07-24/DSC00206.JPG`); a different file with the same name is never
overwritten — the new one gets a `_1` suffix. The file's modification time is set to the capture time.

Plain `download` skips photos the journal marks as downloaded. `download --recheck` ignores those
marks: it looks for every photo from the card on disk (at the journal path and in its date folder,
comparing size and time) and downloads only the missing ones — for example, ones deleted by accident.

## Commands

```bash
python3 -m flashair status       # Wi-Fi, card and journal state
python3 -m flashair connect      # join the card's network
python3 -m flashair disconnect   # leave it
python3 -m flashair scan         # connect → record the file list in the journal → disconnect
python3 -m flashair download     # same + download new files
python3 -m flashair download --recheck  # re-download everything missing on disk
python3 -m flashair list         # show the journal without connecting
```

`--keep` on `scan` and `download` leaves the Mac on the card's network. If the Mac was already on the
card's network before the run, the utility doesn't disconnect it. On an error or Ctrl+C it still
disconnects.

With a VPN on, requests to `192.168.0.1` may go into the tunnel — the utility warns about it.

Short help: `python3 -m flashair --help`; for a single command: `python3 -m flashair download --help`.

## Short commands

```bash
./install-aliases.sh
```

The script adds aliases to `~/.zshrc` (or `~/.bash_profile` for bash) after saving a copy of the file
as `*.flashair-backup`. Running it again updates the aliases; `./install-aliases.sh --remove` removes
them. The aliases work from any folder: settings are read from the project folder by default.

| Alias | Command |
|---|---|
| `fa` | any: `fa status`, `fa --help` |
| `fas` | `status` |
| `fac` | `connect` |
| `fadc` | `disconnect` |
| `fasc` | `scan` |
| `fadl` | `download` |
| `fadr` | `download --recheck` |
| `fal` | `list` |

Options go at the end: `fadl --keep`.

## Author

Vasiliy Mazaev · designed by Claude

## License

[MIT](LICENSE)
