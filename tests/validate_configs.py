#!/usr/bin/env python3
"""Static checks for config files that CI can run without building the image."""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$")
errors = []

for toml_file in sorted((ROOT / "disk_config").glob("*.toml")):
    try:
        tomllib.loads(toml_file.read_text())
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"{toml_file.relative_to(ROOT)}: {exc}")

# The base image has no GNOME first-boot setup, so the installer must create the user
# account: an ISO without the Users module installs a system nobody can log in to.
iso = tomllib.loads((ROOT / "disk_config/iso.toml").read_text())
modules = iso.get("customizations", {}).get("installer", {}).get("modules", {})
users = "org.fedoraproject.Anaconda.Modules.Users"
if users not in modules.get("enable", []) or users in modules.get("disable", []):
    errors.append(f"disk_config/iso.toml: the installer must enable {users} (no other way to create an account)")

# The installer leaves /etc/hostname empty, and the computer was then called "bazzite"
# (VM install, 2026-11-22): the kickstart %post must name it.
kickstart = iso.get("customizations", {}).get("installer", {}).get("kickstart", {}).get("contents", "")
if "/etc/hostname" not in kickstart or "DEFAULT_HOSTNAME" not in kickstart:
    errors.append("disk_config/iso.toml: the kickstart %post must write /etc/hostname from DEFAULT_HOSTNAME")

for list_file in (ROOT / "system_files/usr/share/nebula-os/flatpaks.list",):
    for number, line in enumerate(list_file.read_text().splitlines(), 1):
        app = line.split("#", 1)[0].strip()
        if app and not APP_ID.match(app):
            errors.append(f"{list_file.relative_to(ROOT)}:{number}: not a Flatpak app ID: {app}")

bazaar = ROOT / "build_files/bazaar-dev-work.yaml"
for number, line in enumerate(bazaar.read_text().splitlines(), 1):
    match = re.match(r"^\s+- ([^\s:]+)$", line)
    if match and not APP_ID.match(match.group(1)):
        errors.append(f"{bazaar.relative_to(ROOT)}:{number}: not a Flatpak app ID: {match.group(1)}")
    if line.strip() and not line.startswith("  "):
        errors.append(f"{bazaar.relative_to(ROOT)}:{number}: must be indented as a Bazaar 'rows' entry")

for unit in sorted((ROOT / "system_files").rglob("*.service")):
    text = unit.read_text()
    for section in ("[Unit]", "[Service]"):
        if section not in text:
            errors.append(f"{unit.relative_to(ROOT)}: missing {section}")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print("Config files OK.")
