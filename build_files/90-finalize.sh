#!/usr/bin/bash
# Final steps: rebuild the caches that depend on files added in earlier steps.
set -euo pipefail

SCHEMAS=/usr/share/glib-2.0/schemas

# The wallpaper override only makes sense on GNOME editions.
if [[ ! -f "$SCHEMAS/org.gnome.desktop.background.gschema.xml" ]]; then
    echo "No GNOME background schema (non-GNOME base image); removing the wallpaper override."
    rm -f "$SCHEMAS/zz1-nebula-os.gschema.override"
fi

# Compile GNOME default settings. --strict makes typos in overrides fail the build.
glib-compile-schemas --strict "$SCHEMAS"

# Refresh the icon cache so the NebulaOS logo is found. Every file in an ostree
# image has the same timestamp, so a stale cache would still look up to date.
if command -v gtk-update-icon-cache >/dev/null; then
    gtk-update-icon-cache --force --ignore-theme-index /usr/share/icons/hicolor
fi
