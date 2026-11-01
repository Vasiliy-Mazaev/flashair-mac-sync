"""Управление Wi-Fi через штатные утилиты macOS: networksetup, ipconfig, route."""

import re
import subprocess

from . import FlashAirError, log


def run(args: list[str], secret: str | None = None, check: bool = True, quiet: bool = False) -> str:
    """Выполняет команду, показывая её в терминале (секрет заменяется звёздочками)."""
    if not quiet:
        log.cmd(["********" if secret and a == secret else a for a in args])

    p = subprocess.run(args, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()

    if check and p.returncode != 0:
        raise FlashAirError(f"{args[0]} завершилась с кодом {p.returncode}: {out}")

    return out


def find_interface() -> str:
    """Ищет устройство Wi-Fi (en0, en1, …) в списке аппаратных портов."""
    out = run(["networksetup", "-listallhardwareports"])
    match = re.search(r"Hardware Port: (?:Wi-Fi|AirPort)\s*\nDevice: (\S+)", out)

    if not match:
        raise FlashAirError("Не найден Wi-Fi-интерфейс")

    return match.group(1)


def is_powered(interface: str) -> bool:
    return run(["networksetup", "-getairportpower", interface]).endswith("On")


def set_power(interface: str, on: bool):
    run(["networksetup", "-setairportpower", interface, "on" if on else "off"])


def join(interface: str, ssid: str, password: str):
    # networksetup возвращает 0 и при ошибке, поэтому успех — это пустой вывод
    out = run(["networksetup", "-setairportnetwork", interface, ssid, password], secret=password)

    if out:
        raise FlashAirError(out)


def forget(interface: str, ssid: str) -> str | None:
    """Убирает сеть из списка известных. Возвращает текст ошибки или None."""
    out = run(["networksetup", "-removepreferredwirelessnetwork", interface, ssid], check=False)
    return None if out.startswith("Removed") else out


def ip_address(interface: str) -> str | None:
    out = run(["ipconfig", "getifaddr", interface], check=False, quiet=True)
    return out if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", out) else None


def route_interface(host: str) -> str | None:
    """Через какой интерфейс система отправит пакеты на host (VPN может перехватывать)."""
    out = run(["route", "-n", "get", host], check=False, quiet=True)
    match = re.search(r"interface: (\S+)", out)
    return match.group(1) if match else None
