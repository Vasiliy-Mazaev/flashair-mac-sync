"""Подключение к сети карты и возврат к обычной сети."""

import time
from contextlib import contextmanager

from . import FlashAirError, log, wifi
from .card import Card
from .settings import Settings


def interface(s: Settings) -> str:
    if s.interface:
        return s.interface

    iface = wifi.find_interface()
    log.info(f"Wi-Fi-интерфейс: {iface}")
    return iface


def check_route(s: Settings, iface: str):
    """Предупреждает, если запросы к карте уходят не через Wi-Fi (например, в VPN)."""
    route = wifi.route_interface(s.host)
    if route and route != iface:
        log.warn(f"Запросы к {s.host} идут через {route}, а не {iface}. Если карта не отвечает — отключите VPN.")


def wait_for_card(s: Settings, card: Card, iface: str) -> bool:
    log.info(f"Жду IP-адрес и ответ карты (до {s.connect_wait:.0f} с)")
    deadline = time.monotonic() + s.connect_wait

    while time.monotonic() < deadline:
        ip = wifi.ip_address(iface)
        if ip and card.ssid(timeout=2) == s.ssid:
            log.ok(f"Получен IP {ip}, карта {s.host} отвечает")
            return True
        time.sleep(1)

    return False


def connect(s: Settings, card: Card) -> bool:
    """Подключается к сети карты. Возвращает False, если подключение уже было."""
    log.step(f"Подключение к сети карты «{s.ssid}»")

    log.info(f"Проверяю, отвечает ли карта на {s.host}")
    if card.ssid(timeout=2) == s.ssid:
        log.ok("Компьютер уже в сети карты, переподключаться не нужно")
        return False

    iface = interface(s)

    if not wifi.is_powered(iface):
        log.info("Wi-Fi выключен — включаю")
        wifi.set_power(iface, True)

    for attempt in range(1, s.connect_attempts + 1):
        log.info(f"Попытка {attempt} из {s.connect_attempts}: подключаюсь к «{s.ssid}»")

        try:
            wifi.join(iface, s.ssid, s.password)
        except FlashAirError as e:
            log.warn(f"macOS не смогла подключиться: {e}")
            time.sleep(3)
            continue

        log.ok("Wi-Fi подключён к сети карты")
        if wait_for_card(s, card, iface):
            check_route(s, iface)
            return True

        log.warn("Карта не ответила вовремя")
        check_route(s, iface)

    raise FlashAirError(f"Не удалось подключиться к карте «{s.ssid}». Карта включена и рядом?")


def disconnect(s: Settings, card: Card):
    """Уходит из сети карты: macOS сама переподключится к обычной известной сети."""
    log.step(f"Отключение от сети карты «{s.ssid}»")
    iface = interface(s)

    if s.forget_network:
        log.info("Убираю сеть карты из списка известных, чтобы macOS не подключалась к ней сама")
        error = wifi.forget(iface, s.ssid)
        if error:
            log.warn(f"Не получилось: {error}")
        else:
            log.ok("Сеть карты забыта")

    log.info("Перезапускаю Wi-Fi, чтобы macOS выбрала обычную сеть")
    wifi.set_power(iface, False)
    time.sleep(2)
    wifi.set_power(iface, True)

    log.info(f"Жду подключения к другой сети (до {s.connect_wait:.0f} с)")
    deadline = time.monotonic() + s.connect_wait

    while time.monotonic() < deadline:
        ip = wifi.ip_address(iface)
        if ip:
            if card.ssid(timeout=1) == s.ssid:
                log.warn(f"macOS снова подключилась к карте (IP {ip})")
                return
            log.ok(f"Подключено к обычной сети, IP {ip}")
            return
        time.sleep(1)

    log.warn("Wi-Fi включён, но сеть пока не выбрана — macOS подключится сама, когда найдёт известную сеть")


@contextmanager
def session(s: Settings, card: Card, keep: bool = False):
    """Сеть карты на время работы; отключается и при ошибке, и при Ctrl+C."""
    connected = connect(s, card)

    try:
        yield
    finally:
        if keep:
            log.step("Остаюсь в сети карты (--keep)")
        elif connected:
            disconnect(s, card)
        else:
            log.step("Сеть не меняю: подключение к карте было до запуска")
