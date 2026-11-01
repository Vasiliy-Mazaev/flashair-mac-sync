# FlashAir

Утилита для карты Toshiba FlashAir: сама подключает Mac к Wi-Fi карты, читает список файлов,
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
| `storage.database`, `storage.download_dir` | журнал SQLite и папка загрузок (относительно файла настроек) |

`settings.json`, журнал и загрузки в git не попадают.

## Команды

```bash
python3 -m flashair status       # состояние Wi-Fi, карты и журнала
python3 -m flashair connect      # подключиться к сети карты
python3 -m flashair disconnect   # отключиться
python3 -m flashair scan         # подключиться → записать список файлов в журнал → отключиться
python3 -m flashair download     # то же + скачать новые файлы
python3 -m flashair list         # журнал без подключения
```

`--keep` у `scan` и `download` оставляет компьютер в сети карты. Если Mac уже был подключён к карте
до запуска, утилита его не отключает. При ошибке или Ctrl+C отключение всё равно выполняется.

Если включён VPN, запросы к `192.168.0.1` могут уходить в туннель — утилита об этом предупредит.

Старый код лежит в `old/` для справки.
