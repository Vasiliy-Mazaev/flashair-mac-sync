"""Wi-Fi control with the built-in macOS tools: networksetup, ipconfig, route."""

import re
import subprocess

from . import FlashAirError, log


def run(args: list[str], secret: str | None = None, check: bool = True, quiet: bool = False) -> str:
    """Runs a command and shows it in the terminal (the secret is replaced with asterisks)."""
    if not quiet:
        log.cmd(["********" if secret and a == secret else a for a in args])

    p = subprocess.run(args, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()

    if check and p.returncode != 0:
        raise FlashAirError(f"{args[0]} exited with code {p.returncode}: {out}")

    return out


def find_interface() -> str:
    """Finds the Wi-Fi device (en0, en1, …) in the list of hardware ports."""
    out = run(["networksetup", "-listallhardwareports"])
    match = re.search(r"Hardware Port: (?:Wi-Fi|AirPort)\s*\nDevice: (\S+)", out)

    if not match:
        raise FlashAirError("No Wi-Fi interface found")

    return match.group(1)


def is_powered(interface: str) -> bool:
    return run(["networksetup", "-getairportpower", interface]).endswith("On")


def set_power(interface: str, on: bool):
    run(["networksetup", "-setairportpower", interface, "on" if on else "off"])


def join(interface: str, ssid: str, password: str):
    # networksetup returns 0 even on failure, so success means empty output
    out = run(["networksetup", "-setairportnetwork", interface, ssid, password], secret=password)

    if out:
        raise FlashAirError(out)


def forget(interface: str, ssid: str) -> str | None:
    """Removes the network from known networks. Returns the error text or None."""
    out = run(["networksetup", "-removepreferredwirelessnetwork", interface, ssid], check=False)
    return None if out.startswith("Removed") else out


def ip_address(interface: str) -> str | None:
    out = run(["ipconfig", "getifaddr", interface], check=False, quiet=True)
    return out if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", out) else None


def route_interface(host: str) -> str | None:
    """Which interface the system will send packets to host through (a VPN may intercept them)."""
    out = run(["route", "-n", "get", host], check=False, quiet=True)
    match = re.search(r"interface: (\S+)", out)
    return match.group(1) if match else None
