"""
get_wifi_info.py — List saved WiFi SSIDs and extended info on Windows, macOS, and Linux.

Windows : uses `netsh wlan`
macOS   : uses `networksetup`, `airport`, `ipconfig`, `system_profiler`
Linux   : uses `nmcli` (NetworkManager) or reads /etc/NetworkManager/system-connections/
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from subprocess import PIPE
from pathlib import Path


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, stdout=PIPE, stderr=PIPE)
    return result.stdout.decode(errors="replace")


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _get_wifi_windows() -> list[dict]:
    output = _run(["netsh", "wlan", "show", "profiles"])
    names = re.findall(r"All User Profile\s+: (.*)\r", output)
    profiles = []
    for name in names:
        info = _run(["netsh", "wlan", "show", "profiles", name])
        if re.search(r"Security key\s+: Absent", info):
            continue
        detail = _run(["netsh", "wlan", "show", "profile", name, "key=clear"])
        match = re.search(r"Key Content\s+: (.*)\r", detail)
        profiles.append({"ssid": name, "password": match[1] if match else None})
    return profiles


# ---------------------------------------------------------------------------
# macOS helpers
# ---------------------------------------------------------------------------

def _macos_wifi_interface() -> str | None:
    """Return the first Wi-Fi device name (e.g. 'en0')."""
    output = _run(["networksetup", "-listallhardwareports"])
    match = re.search(r"Wi-Fi.*?Device:\s+(\S+)", output, re.DOTALL)
    return match[1] if match else None


def _system_profiler_wifi() -> tuple[dict, dict]:
    """
    Parse `system_profiler SPAirPortDataType -json`.
    Returns (nearby_networks, current_network) where each is a dict of fields.
    nearby_networks is keyed by SSID.
    """
    raw = _run(["system_profiler", "SPAirPortDataType", "-json"])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}, {}

    nearby: dict[str, dict] = {}
    current: dict = {}

    for entry in data.get("SPAirPortDataType", []):
        for iface in entry.get("spairport_airport_interfaces", []):
            for net in iface.get("spairport_airport_other_local_wireless_networks", []):
                ssid = net.get("_name", "")
                if ssid:
                    rssi, noise = _parse_signal_noise(net.get("spairport_signal_noise", ""))
                    nearby[ssid] = {
                        "channel": net.get("spairport_network_channel"),
                        "band": _band_from_channel_str(net.get("spairport_network_channel", "")),
                        "security": _friendly_security(net.get("spairport_security_mode", "")),
                        "phy_mode": net.get("spairport_network_phymode"),
                        "rssi": rssi,
                        "noise": noise,
                    }

            cur = iface.get("spairport_current_network_information", {})
            ssid = cur.get("_name", "")
            if ssid:
                rssi, noise = _parse_signal_noise(cur.get("spairport_signal_noise", ""))
                current = {
                    "ssid": ssid,
                    "channel": cur.get("spairport_network_channel"),
                    "band": _band_from_channel_str(cur.get("spairport_network_channel", "")),
                    "security": _friendly_security(cur.get("spairport_security_mode", "")),
                    "phy_mode": cur.get("spairport_network_phymode"),
                    "tx_rate": cur.get("spairport_network_rate"),
                    "mcs": cur.get("spairport_network_mcs"),
                    "rssi": rssi,
                    "noise": noise,
                    "mac_address": iface.get("spairport_wireless_mac_address"),
                }

    return nearby, current


def _parse_signal_noise(value: str) -> tuple[str | None, str | None]:
    """Split 'spairport_signal_noise' like '-46 dBm / -93 dBm' into (rssi, noise)."""
    parts = value.split("/")
    if len(parts) == 2:
        return parts[0].strip() or None, parts[1].strip() or None
    return value.strip() or None, None


def _band_from_channel_str(channel: str) -> str | None:
    """Extract band from strings like '149 (5GHz, 80MHz)' or '6 (2GHz, 20MHz)'."""
    m = re.search(r"\((\d+)GHz", channel)
    if m:
        return f"{m.group(1)} GHz"
    return None


def _friendly_security(raw: str) -> str | None:
    """Convert 'spairport_security_mode_wpa2_personal' → 'WPA2 Personal'."""
    if not raw:
        return None
    label = raw.replace("spairport_security_mode_", "").replace("_", " ").title()
    return label or None


def _macos_network_info(iface: str) -> dict:
    """IP, subnet, router, and DNS for the given interface via networksetup."""
    info: dict = {}
    out = _run(["networksetup", "-getinfo", "Wi-Fi"])
    for line in out.splitlines():
        if line.startswith("IP address:"):
            info["ip_address"] = line.split(":", 1)[1].strip()
        elif line.startswith("Subnet mask:"):
            info["subnet_mask"] = line.split(":", 1)[1].strip()
        elif line.startswith("Router:"):
            info["router"] = line.split(":", 1)[1].strip()

    dns_out = _run(["networksetup", "-getdnsservers", "Wi-Fi"])
    servers = [l.strip() for l in dns_out.splitlines() if l.strip() and "There aren't" not in l]
    if servers:
        info["dns_servers"] = servers

    return info


def _macos_current_ssid(iface: str) -> str | None:
    out = _run(["networksetup", "-getairportnetwork", iface])
    m = re.search(r"Current Wi-Fi Network:\s+(.+)", out)
    return m[1].strip() if m else None


# ---------------------------------------------------------------------------
# macOS main
# ---------------------------------------------------------------------------

def _get_wifi_macos() -> list[dict]:
    iface = _macos_wifi_interface()
    if not iface:
        print("Could not detect Wi-Fi interface.", file=sys.stderr)
        return []

    # Saved SSIDs
    output = _run(["networksetup", "-listpreferredwirelessnetworks", iface])
    lines = output.splitlines()
    ssids = [l.strip() for l in lines[1:] if l.strip()]

    nearby, current = _system_profiler_wifi()
    # system_profiler redacts SSIDs as "<redacted>", so use networksetup for the real name.
    current_ssid = _macos_current_ssid(iface)
    conn_info = _macos_network_info(iface) if current_ssid else {}

    profiles = []
    for ssid in ssids:
        profile: dict = {"ssid": ssid, "connected": ssid == current_ssid}

        if ssid == current_ssid:
            # system_profiler redacts nearby SSIDs but the current network metrics are
            # still available — we just know which saved network is current via networksetup.
            for key in ("channel", "band", "security", "phy_mode", "tx_rate", "mcs", "rssi", "noise", "mac_address"):
                profile[key] = current.get(key)
            profile.update(conn_info)

        profiles.append(profile)

    return profiles


# ---------------------------------------------------------------------------
# Linux (NetworkManager)
# ---------------------------------------------------------------------------

def _get_wifi_linux() -> list[dict]:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        stdout=PIPE, stderr=PIPE,
    )
    if result.returncode == 0:
        return _wifi_linux_nmcli(result.stdout.decode(errors="replace"))
    return _wifi_linux_files()


def _wifi_linux_nmcli(output: str) -> list[dict]:
    profiles = []
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and "wireless" in parts[1]:
            ssid = parts[0]
            pw_result = subprocess.run(
                ["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", ssid],
                stdout=PIPE, stderr=PIPE,
            )
            password = pw_result.stdout.decode(errors="replace").strip() or None
            profiles.append({"ssid": ssid, "password": password})
    return profiles


def _wifi_linux_files() -> list[dict]:
    conn_dir = Path("/etc/NetworkManager/system-connections")
    if not conn_dir.exists():
        print("NetworkManager connections directory not found.", file=sys.stderr)
        return []

    profiles = []
    for conf in conn_dir.iterdir():
        try:
            text = conf.read_text(errors="replace")
        except PermissionError:
            print(f"Permission denied reading {conf}. Try running as root.", file=sys.stderr)
            continue

        if "type=wifi" not in text and "type = wifi" not in text:
            continue

        ssid_match = re.search(r"ssid\s*=\s*(.+)", text)
        pw_match = re.search(r"psk\s*=\s*(.+)", text)
        if ssid_match:
            profiles.append({
                "ssid": ssid_match[1].strip(),
                "password": pw_match[1].strip() if pw_match else None,
            })
    return profiles


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    platform = sys.platform
    if platform == "win32":
        profiles = _get_wifi_windows()
    elif platform == "darwin":
        profiles = _get_wifi_macos()
    elif platform.startswith("linux"):
        profiles = _get_wifi_linux()
    else:
        print(f"Unsupported platform: {platform}", file=sys.stderr)
        sys.exit(1)

    if not profiles:
        print("No saved WiFi profiles found.")
        return

    for profile in profiles:
        print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()
