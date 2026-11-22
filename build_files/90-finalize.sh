#!/usr/bin/bash
# Final steps: rebuild caches for files added earlier, and check the result.
set -euo pipefail

SCHEMAS=/usr/share/glib-2.0/schemas
OVERRIDE="$SCHEMAS/zz1-nebula-os.gschema.override"

# The wallpaper and dock override only make sense on GNOME editions.
if [[ ! -f "$SCHEMAS/org.gnome.desktop.background.gschema.xml" ]]; then
    echo "No GNOME background schema (non-GNOME base image); removing the GNOME override."
    rm -f "$OVERRIDE"
fi

# Every dock entry must exist, except Flatpak apps (exported at runtime, not in the image).
FLATPAK_FAVORITES=" org.mozilla.firefox.desktop "
if [[ -f "$OVERRIDE" ]]; then
    favorites=$(sed -n "s/^favorite-apps=\[\(.*\)\]$/\1/p" "$OVERRIDE" | tr -d "' " | tr ',' ' ')
    for app in $favorites; do
        if [[ ! -f "/usr/share/applications/$app" && "$FLATPAK_FAVORITES" != *" $app "* ]]; then
            echo "ERROR: dock favorite $app has no /usr/share/applications/$app" >&2
            exit 1
        fi
    done
    echo "Dock favorites OK: $favorites"
fi

# Compile GNOME default settings. The NebulaOS override is checked on its own first,
# with --strict, so a typo in it fails the build. The full compile is not strict:
# override files from the base image can name keys its GNOME no longer has (the
# Bazzite NVIDIA image sets org.gnome.mutter experimental-features), and GNOME skips
# those keys, as it does on the base image itself.
if [[ -f "$OVERRIDE" ]]; then
    check_dir=$(mktemp -d)
    cp "$SCHEMAS"/*.xml "$OVERRIDE" "$check_dir"/
    glib-compile-schemas --strict --targetdir="$check_dir" "$check_dir"
    rm -rf "$check_dir"
    echo "NebulaOS settings override OK."
fi
glib-compile-schemas "$SCHEMAS"

# Compile dconf databases (login screen message in /etc/dconf/db/gdm.d).
dconf update

# Refresh the icon cache so the NebulaOS logo is found. Every file in an ostree
# image has the same timestamp, so a stale cache would still look up to date.
if command -v gtk-update-icon-cache >/dev/null; then
    gtk-update-icon-cache --force --ignore-theme-index /usr/share/icons/hicolor
fi

# Precompile the nebula tools (/usr is read-only at runtime) and make sure they start.
python3 -m compileall -q /usr/lib/nebula-os
nebula --version
