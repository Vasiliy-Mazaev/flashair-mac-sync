"""Joining the card's network and returning to the usual network."""

import time
from contextlib import contextmanager

from . import FlashAirError, log, wifi
from .card import Card
from .settings import Settings


def interface(s: Settings) -> str:
    if s.interface:
        return s.interface

    iface = wifi.find_interface()
    log.info(f"Wi-Fi interface: {iface}")
    return iface


def check_route(s: Settings, iface: str):
    """Warns if requests to the card don't go through Wi-Fi (for example, into a VPN)."""
    route = wifi.route_interface(s.host)
    if route and route != iface:
        log.warn(f"Requests to {s.host} go through {route}, not {iface}. If the card doesn't respond, turn off the VPN.")


def wait_for_card(s: Settings, card: Card, iface: str) -> bool:
    log.info(f"Waiting for an IP address and a response from the card (up to {s.connect_wait:.0f} s)")
    deadline = time.monotonic() + s.connect_wait

    while time.monotonic() < deadline:
        ip = wifi.ip_address(iface)
        if ip and card.ssid(timeout=2) == s.ssid:
            log.ok(f"Got IP {ip}, the card at {s.host} responds")
            return True
        time.sleep(1)

    return False


def connect(s: Settings, card: Card) -> bool:
    """Joins the card's network. Returns False if it was already connected."""
    log.step(f"Joining the card's network \"{s.ssid}\"")

    log.info(f"Checking whether the card responds at {s.host}")
    if card.ssid(timeout=2) == s.ssid:
        log.ok("Already on the card's network, no need to reconnect")
        return False

    iface = interface(s)

    if not wifi.is_powered(iface):
        log.info("Wi-Fi is off — turning it on")
        wifi.set_power(iface, True)

    for attempt in range(1, s.connect_attempts + 1):
        log.info(f"Attempt {attempt} of {s.connect_attempts}: joining \"{s.ssid}\"")

        try:
            wifi.join(iface, s.ssid, s.password)
        except FlashAirError as e:
            log.warn(f"macOS couldn't join: {e}")
            time.sleep(3)
            continue

        log.ok("Wi-Fi joined the card's network")
        if wait_for_card(s, card, iface):
            check_route(s, iface)
            return True

        log.warn("The card didn't respond in time")
        check_route(s, iface)

    raise FlashAirError(f"Couldn't connect to the card \"{s.ssid}\". Is the card on and nearby?")


def disconnect(s: Settings, card: Card):
    """Leaves the card's network: macOS rejoins the usual known network by itself."""
    log.step(f"Leaving the card's network \"{s.ssid}\"")
    iface = interface(s)

    if s.forget_network:
        log.info("Removing the card's network from known networks so macOS doesn't rejoin it by itself")
        error = wifi.forget(iface, s.ssid)
        if error:
            log.warn(f"Failed: {error}")
        else:
            log.ok("The card's network is forgotten")

    log.info("Restarting Wi-Fi so macOS picks the usual network")
    wifi.set_power(iface, False)
    time.sleep(2)
    wifi.set_power(iface, True)

    log.info(f"Waiting for another network (up to {s.connect_wait:.0f} s)")
    deadline = time.monotonic() + s.connect_wait

    while time.monotonic() < deadline:
        ip = wifi.ip_address(iface)
        if ip:
            if card.ssid(timeout=1) == s.ssid:
                log.warn(f"macOS rejoined the card (IP {ip})")
                return
            log.ok(f"Connected to the usual network, IP {ip}")
            return
        time.sleep(1)

    log.warn("Wi-Fi is on but no network is picked yet — macOS will join one by itself once it finds a known network")


@contextmanager
def session(s: Settings, card: Card, keep: bool = False):
    """The card's network for the duration of the work; disconnects on errors and Ctrl+C too."""
    connected = connect(s, card)

    try:
        yield
    finally:
        if keep:
            log.step("Staying on the card's network (--keep)")
        elif connected:
            disconnect(s, card)
        else:
            log.step("Leaving the network as is: it was on the card before the run")
