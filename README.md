# FlashAir

**English** · [Русская версия ниже ↓](#russian)

A utility for the Toshiba FlashAir W-04 card. It connects your Mac to the card's Wi-Fi, reads the
file list, downloads new photos and switches the Mac back to its usual network. Runs on macOS with
Python 3.10+ and no third-party libraries: Wi-Fi is controlled with the built-in `networksetup`,
`ipconfig` and `route`.

The terminal output and `--help` are in Russian.

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
| `files.root`, `files.extensions` | folder on the card and file extensions (empty list — all files) |
| `files.ignore` | name or path patterns that are not photos; by default the FlashAir service image `FA000001.JPG` |
| `storage.database`, `storage.download_dir` | SQLite journal and download folder (relative to the settings file) |

`settings.json`, the journal and downloads are kept out of git.

## Journal and downloads

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

---

<a id="russian"></a>

# FlashAir — русская версия

[English version above ↑](#flashair) · **Русский**

Утилита для карты Toshiba FlashAir W-04: сама подключает Mac к Wi-Fi карты, читает список файлов,
скачивает новые и возвращает компьютер в обычную сеть. Работает на macOS, нужен только Python 3.10+
без сторонних библиотек: Wi-Fi управляется штатными `networksetup`, `ipconfig` и `route`.

## Настройка

```bash
cp settings.example.json settings.json
```

В `settings.json` укажите `card.ssid` и `card.password` своей карты. Остальные параметры:

| Ключ | Смысл |
|---|---|
| `card.host`, `card.timeout` | адрес карты и таймаут HTTP-запросов, с |
| `wifi.interface` | устройство Wi-Fi; пусто — найти автоматически |
| `wifi.connect_attempts`, `wifi.connect_wait` | число попыток подключения и ожидание ответа карты, с |
| `wifi.forget_network` | забывать сеть карты при отключении, чтобы macOS не подключалась к ней сама |
| `files.root`, `files.extensions` | папка на карте и расширения файлов (пустой список — все файлы) |
| `files.ignore` | шаблоны имён или путей, которые не считаются снимками; по умолчанию служебная картинка FlashAir `FA000001.JPG` |
| `storage.database`, `storage.download_dir` | журнал SQLite и папка загрузок (относительно файла настроек) |

`settings.json`, журнал и загрузки в git не попадают.

## Журнал и загрузки

Имена и пути на карте повторяются после форматирования или сброса счётчика, поэтому снимок
в журнале определяется по имени, размеру и дате съёмки. Файлы сохраняются в папки по дате
съёмки (`downloads/2026-07-24/DSC00206.JPG`); чужой файл с тем же именем не перезаписывается —
новый получает суффикс `_1`. Время файла выставляется равным времени съёмки.

Обычный `download` пропускает снимки, отмеченные в журнале как скачанные. `download --recheck`
отметкам не доверяет: проверяет каждый снимок с карты на диске (по пути из журнала и в папке
его даты, сравнивая размер и время) и скачивает только отсутствующие — например, случайно удалённые.

## Команды

```bash
python3 -m flashair status       # состояние Wi-Fi, карты и журнала
python3 -m flashair connect      # подключиться к сети карты
python3 -m flashair disconnect   # отключиться
python3 -m flashair scan         # подключиться → записать список файлов в журнал → отключиться
python3 -m flashair download     # то же + скачать новые файлы
python3 -m flashair download --recheck  # скачать заново всё, чего нет на диске
python3 -m flashair list         # журнал без подключения
```

`--keep` у `scan` и `download` оставляет компьютер в сети карты. Если Mac уже был подключён к карте
до запуска, утилита его не отключает. При ошибке или Ctrl+C отключение всё равно выполняется.

Если включён VPN, запросы к `192.168.0.1` могут уходить в туннель — утилита об этом предупредит.

Краткая справка: `python3 -m flashair --help`, по отдельной команде — `python3 -m flashair download --help`.

## Короткие команды

```bash
./install-aliases.sh
```

Скрипт добавляет алиасы в `~/.zshrc` (или `~/.bash_profile` для bash), предварительно сохранив
копию файла в `*.flashair-backup`. Повторный запуск обновляет алиасы, `./install-aliases.sh --remove`
удаляет их. Алиасы работают из любой папки: настройки по умолчанию берутся из папки проекта.

| Алиас | Команда |
|---|---|
| `fa` | любая: `fa status`, `fa --help` |
| `fas` | `status` |
| `fac` | `connect` |
| `fadc` | `disconnect` |
| `fasc` | `scan` |
| `fadl` | `download` |
| `fadr` | `download --recheck` |
| `fal` | `list` |

Параметры дописываются в конце: `fadl --keep`.

## Автор

Vasiliy Mazaev · designed by Claude

## Лицензия

[MIT](LICENSE)
