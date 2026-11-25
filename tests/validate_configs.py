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
# Installs must check update signatures from the start (repository audit, 2026-11-22):
# without this the system followed "ostree-unverified-registry:" until the user acted.
if "%post --erroronfail" not in kickstart:
    errors.append("disk_config/iso.toml: %post must use --erroronfail so a failed update-source switch stops the install")
switches = [line for line in kickstart.splitlines() if line.strip().startswith(("bootc switch", "if ! bootc switch"))]
if not switches or any("--enforce-container-sigpolicy" not in line for line in switches):
    errors.append("disk_config/iso.toml: every kickstart 'bootc switch' must use --enforce-container-sigpolicy "
                  "(no unverified fallback: red-team R06-1 / security review)")
if "/etc/hostname" not in kickstart or "DEFAULT_HOSTNAME" not in kickstart:
    errors.append("disk_config/iso.toml: the kickstart %post must write /etc/hostname from DEFAULT_HOSTNAME")

# Supply chain (security review and red team, 2026-11-23): builds use pinned, verified images.
DIGEST_REF = re.compile(r"^[a-z0-9./-]+@sha256:[0-9a-f]{64}$")
lock = [l.strip() for l in (ROOT / "base-images.lock").read_text().splitlines() if l.strip() and not l.startswith("#")]
for line in lock:
    if not DIGEST_REF.match(line):
        errors.append(f"base-images.lock: not a pinned digest reference: {line}")
build_yml = (ROOT / ".github/workflows/build.yml").read_text()
for base in re.findall(r"base_image:\s*(\S+)", build_yml):
    repo = base.rsplit(":", 1)[0]
    if not any(l.startswith(repo + "@sha256:") for l in lock):
        errors.append(f"base-images.lock: no reviewed digest for {repo} (used in build.yml)")
for needle in ("cosign verify --new-bundle-format=false --key keys/ublue-os.pub", "base-images.lock",
               "BASE_IMAGE: ${{ env.BASE_IMAGE_PINNED }}"):
    if needle not in build_yml:
        errors.append(f".github/workflows/build.yml: missing base image verification ({needle})")
if "BEGIN PUBLIC KEY" not in (ROOT / "keys/ublue-os.pub").read_text():
    errors.append("keys/ublue-os.pub: not a PEM public key")
disk_yml = (ROOT / ".github/workflows/build-disk.yml").read_text()
bib = re.search(r'BIB_IMAGE:\s*"([^"]+)"', disk_yml)
if not bib or not DIGEST_REF.match(bib.group(1)):
    errors.append(".github/workflows/build-disk.yml: BIB_IMAGE must be pinned by digest (it runs --privileged)")
if "cosign verify --key cosign.pub" not in disk_yml or "PROVENANCE.txt" not in disk_yml:
    errors.append(".github/workflows/build-disk.yml: must verify the source image signature and record provenance")
justfile = (ROOT / "Justfile").read_text()
if re.search(r"quay\.io/coreos/chunkah:(?!.*@sha256)", justfile) or "quay.io/coreos/chunkah@sha256:" not in justfile:
    errors.append("Justfile: chunkah must be pinned by digest")

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
