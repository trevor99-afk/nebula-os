#!/usr/bin/bash
# Branding: gives the OS its own name in the boot menu, Settings > About, the
# terminal welcome message and the default hostname, and records where updates
# come from.
#
# NOTE: /usr/share/ublue-os/image-info.json is deliberately NOT changed. Bazzite's
# own tools (Steam launcher, hardware setup, flatpak manager) read "image-name"
# from it to detect deck/nvidia variants, so it must keep Bazzite's values.
# ID=bazzite in os-release stays for the same reason.
set -euo pipefail

: "${IMAGE_NAME:?}" "${IMAGE_PRETTY_NAME:?}" "${IMAGE_REGISTRY:?}" "${IMAGE_TAG:?}" "${BASE_IMAGE:?}"

OS_RELEASE=/usr/lib/os-release
REPO_URL="https://github.com/${IMAGE_REGISTRY#ghcr.io/}/${IMAGE_NAME}"

# set_os_release KEY VALUE: writes KEY="VALUE", replacing any existing KEY line.
set_os_release() {
    local key=$1 value=$2 tmp
    # Escape the characters that are special inside double quotes (os-release uses shell syntax).
    value=${value//\\/\\\\}
    value=${value//\"/\\\"}
    value=${value//\$/\\\$}
    value=${value//\`/\\\`}
    tmp=$(mktemp)
    grep -v "^${key}=" "$OS_RELEASE" >"$tmp" || true
    printf '%s="%s"\n' "$key" "$value" >>"$tmp"
    cat "$tmp" >"$OS_RELEASE"
    rm -f "$tmp"
}

# Keep Bazzite's channel and version in the boot menu name,
# e.g. "Bazzite Stable (F45.20261117.1)" -> "NebulaOS Stable (F45.20261117.1)".
# shellcheck source=/dev/null
old_bootloader_name=$(. "$OS_RELEASE" && echo "${BOOTLOADER_NAME:-}")
if [[ "$old_bootloader_name" == "Bazzite "* ]]; then
    bootloader_name="${IMAGE_PRETTY_NAME} ${old_bootloader_name#Bazzite }"
else
    bootloader_name="${IMAGE_PRETTY_NAME}"
fi

set_os_release NAME "$IMAGE_PRETTY_NAME"
set_os_release PRETTY_NAME "$IMAGE_PRETTY_NAME"
set_os_release BOOTLOADER_NAME "$bootloader_name"
set_os_release IMAGE_ID "$IMAGE_NAME"
set_os_release DEFAULT_HOSTNAME "$IMAGE_NAME"
set_os_release LOGO "nebula-os-logo"
set_os_release ANSI_COLOR "0;38;2;167;139;250"
set_os_release HOME_URL "$REPO_URL"
set_os_release SUPPORT_URL "$REPO_URL/issues"
set_os_release BUG_REPORT_URL "$REPO_URL/issues"
# DOCUMENTATION_URL keeps pointing at docs.bazzite.gg: those docs apply to NebulaOS too.

# Terminal welcome message (shown when you open a terminal).
MOTD=/usr/share/ublue-os/motd/template.md
if [[ -f "$MOTD" ]] && grep -q '^# Welcome to Bazzite' "$MOTD"; then
    pretty_sed=$(printf '%s' "$IMAGE_PRETTY_NAME" | sed 's/[&|\\]/\\&/g')
    sed -i "s|^# Welcome to Bazzite|# Welcome to ${pretty_sed} (built on Bazzite)|" "$MOTD"
    # The backticks are literal Markdown, not command substitution.
    # shellcheck disable=SC2016
    sed -i '/^| `ujust --choose`/a | `ujust nebula-info` | NebulaOS version, apps and tools |' "$MOTD"
else
    echo "Note: Bazzite's MOTD template changed; skipping welcome-message branding."
fi

# Where this image is published and what it is built on. Read by the ISO
# installer (disk_config/iso.toml) and the `ujust nebula-*` commands.
install -d /usr/share/nebula-os
echo "${IMAGE_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}" >/usr/share/nebula-os/image-ref
echo "${BASE_IMAGE}" >/usr/share/nebula-os/base-image

echo "--- Resulting os-release:"
cat "$OS_RELEASE"
echo "--- Update source: $(cat /usr/share/nebula-os/image-ref)"
