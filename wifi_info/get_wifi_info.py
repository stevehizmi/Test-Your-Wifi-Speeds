"""
get_wifi_info.py — List saved WiFi SSIDs and passwords on Windows, macOS, and Linux.

Windows : uses `netsh wlan`
macOS   : uses `networksetup` + the system keychain (`security` CLI)
Linux   : uses `nmcli` (NetworkManager) or reads /etc/NetworkManager/system-connections/
"""

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
# macOS
# ---------------------------------------------------------------------------

def _macos_wifi_interface() -> str | None:
    """Return the first Wi-Fi device name (e.g. 'en0')."""
    output = _run(["networksetup", "-listallhardwareports"])
    # Look for the device name on the line after "Wi-Fi"
    match = re.search(r"Wi-Fi.*?Device:\s+(\S+)", output, re.DOTALL)
    return match[1] if match else None


def _get_wifi_macos() -> list[dict]:
    iface = _macos_wifi_interface()
    if not iface:
        print("Could not detect Wi-Fi interface.", file=sys.stderr)
        return []

    output = _run(["networksetup", "-listpreferredwirelessnetworks", iface])
    # Output format: header line, then one SSID per line with leading whitespace
    lines = output.splitlines()
    ssids = [l.strip() for l in lines[1:] if l.strip()]

    profiles = []
    for ssid in ssids:
        # Retrieve password from the macOS keychain (may prompt for keychain access)
        result = subprocess.run(
            ["security", "find-generic-password", "-D", "AirPort network password", "-wa", ssid],
            stdout=PIPE,
            stderr=PIPE,
        )
        password = result.stdout.decode(errors="replace").strip() or None
        if result.returncode != 0 and not password:
            password = None
        profiles.append({"ssid": ssid, "password": password})
    return profiles


# ---------------------------------------------------------------------------
# Linux (NetworkManager)
# ---------------------------------------------------------------------------

def _get_wifi_linux() -> list[dict]:
    # Try nmcli first
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        stdout=PIPE, stderr=PIPE,
    )
    if result.returncode == 0:
        return _wifi_linux_nmcli(result.stdout.decode(errors="replace"))

    # Fall back to reading connection files directly (may need root)
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
        print(profile)


if __name__ == "__main__":
    main()
