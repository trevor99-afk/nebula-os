#!/usr/bin/bash
# The two modes:
#   NebulaOS Gaming Mode  (Steam Gaming Mode, session gamescope-session-steam)
#   NebulaOS Work Mode    (GNOME, session gnome)
# and the default session "NebulaOS" (nebula-os.desktop), which shows a
# full-screen chooser for them after login (/usr/libexec/nebula-os-start).
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

# New users get the full-screen mode chooser: GDM starts the "NebulaOS" session
# for anyone without a saved session. (Users with a saved session keep it;
# `ujust nebula-mode chooser` turns the chooser on for them.)
GDM_CONF=/etc/gdm/custom.conf
if [[ -f "$GDM_CONF" ]] && grep -q '^\[daemon\]' "$GDM_CONF"; then
    sed -i -e '/^DefaultSession=/d' -e '/^\[daemon\]/a DefaultSession=nebula-os.desktop' "$GDM_CONF"
else
    printf '[daemon]\nDefaultSession=nebula-os.desktop\n' >>"$GDM_CONF"
fi
grep -A2 '^\[daemon\]' "$GDM_CONF"
