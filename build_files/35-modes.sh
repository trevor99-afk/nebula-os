#!/usr/bin/bash
# The two modes, chosen on the login screen at every start:
#   NebulaOS Gaming Mode  (Steam Gaming Mode, session gamescope-session-steam)
#   NebulaOS Work Mode    (GNOME, session gnome)
#
# The session IDs stay the same; only the names shown on the login screen
# change, so AccountsService, nebula-os-switch-side and Bazzite's own tools keep
# working. The login screen message lives in system_files/etc/dconf/db/gdm.d/.
set -euo pipefail

SESSIONS=/usr/share/wayland-sessions

# rename_session FILE NAME COMMENT: set the visible name and drop translations,
# so every language shows the NebulaOS mode names.
rename_session() {
    local file="$SESSIONS/$1"
    if [[ ! -f "$file" ]]; then
        echo "Note: $file not found; skipping."
        return 0
    fi
    sed -i -e '/^Name\[/d' -e '/^Comment\[/d' \
        -e "s|^Name=.*|Name=$2|" -e "s|^Comment=.*|Comment=$3|" "$file"
    grep -E '^(Name|Comment|Exec)=' "$file"
}

rename_session gamescope-session-steam.desktop "NebulaOS Gaming Mode" \
    "Steam Gaming Mode: full screen and controller friendly"
rename_session gamescope-session-ogui-steam.desktop "NebulaOS Gaming Mode (with quick settings overlay)" \
    "Steam Gaming Mode plus the OpenGamepadUI quick settings overlay"
rename_session gnome.desktop "NebulaOS Work Mode" \
    "GNOME desktop with developer tools and the Bazaar app store"

# Make Bazzite's session-switching tools work under GDM (see nebula-os-steamosctl).
if [[ ! -e /usr/bin/steamosctl ]]; then
    ln -s /usr/libexec/nebula-os-steamosctl /usr/bin/steamosctl
    echo "Installed steamosctl compatibility shim."
else
    echo "Base image ships its own steamosctl; keeping it."
fi

# Steam's "Switch to Desktop" must reach NebulaOS's hook.
if ! grep -q '/usr/lib/os-session-select' /usr/bin/steamos-session-select 2>/dev/null; then
    echo "WARNING: /usr/bin/steamos-session-select no longer checks /usr/lib/os-session-select;" \
        "Steam's Switch to Desktop may not use NebulaOS's mode switching." >&2
fi
