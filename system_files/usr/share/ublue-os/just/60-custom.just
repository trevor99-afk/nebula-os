# vim: set ft=make :
# NebulaOS commands. Run `ujust` to list everything, e.g. `ujust nebula-info`.

alias nebula-side := nebula-mode

# Show NebulaOS version, live system status and which bundled apps are installed
[group("NebulaOS")]
nebula-info:
    #!/usr/bin/bash
    nebula status
    echo
    echo "App bundle (/usr/share/nebula-os/flatpaks.list):"
    grep -oE '^[^#[:space:]]+' /usr/share/nebula-os/flatpaks.list | while read -r app; do
        if flatpak info "$app" &>/dev/null; then
            echo "  [installed] $app"
        else
            echo "  [missing]   $app"
        fi
    done
    echo
    echo "Install missing apps with: ujust nebula-install-apps"

# Check the system for common problems and suggest fixes (changes nothing)
[group("NebulaOS")]
nebula-doctor:
    nebula doctor

# Hardware and capability report: GPUs, drivers, Vulkan, video acceleration, displays, VRR, HDR
[group("NebulaOS")]
nebula-hw:
    nebula hw

# Choose the mode started at login: gaming | work | status (add "now" to switch right away)
[group("NebulaOS")]
nebula-mode MODE="" NOW="":
    #!/usr/bin/bash
    source /usr/lib/ujust/ujust.sh
    set -euo pipefail
    MODE="{{ MODE }}"
    if [[ -z "$MODE" ]]; then
        echo "Mode selected at login: $(/usr/libexec/nebula-os-switch-side status)"
        MODE=$(Choose gaming work)
    fi
    if [[ "$MODE" == "status" ]]; then
        echo "Mode selected at login: $(/usr/libexec/nebula-os-switch-side status)"
        exit 0
    fi
    if [[ "{{ NOW }}" == "now" ]]; then
        /usr/libexec/nebula-os-switch-side "$MODE" --now
    else
        /usr/libexec/nebula-os-switch-side "$MODE"
    fi

# Install the NebulaOS app bundle now (also brings back bundled apps you removed)
[group("NebulaOS")]
nebula-install-apps:
    sudo /usr/libexec/nebula-os-flatpak-setup --all

# Set up the MangoHud FPS overlay preset. Options: on | off | status
[group("NebulaOS")]
nebula-fps-overlay ACTION="":
    #!/usr/bin/bash
    source /usr/lib/ujust/ujust.sh
    set -euo pipefail
    CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/MangoHud"
    CONF="$CONF_DIR/MangoHud.conf"
    BACKUP="$CONF.before-nebula"
    PRESET=/usr/share/nebula-os/MangoHud.conf
    MARKER="NebulaOS MangoHud preset"
    ACTION="{{ ACTION }}"
    if [[ -z "$ACTION" ]]; then
        ACTION=$(Choose on off status)
    fi
    preset_active() { [[ -f "$CONF" ]] && grep -q "$MARKER" "$CONF"; }
    case "$ACTION" in
        on)
            mkdir -p "$CONF_DIR"
            if [[ -f "$CONF" ]] && ! preset_active; then
                cp "$CONF" "$BACKUP"
                echo "Saved your previous MangoHud config as $BACKUP"
            fi
            cp "$PRESET" "$CONF"
            echo "FPS overlay preset installed: $CONF"
            echo
            echo "Turn the overlay on for a Steam game:"
            echo "  right-click the game > Properties > Launch Options:  mangohud %command%"
            echo "Other launchers (Heroic, Lutris, Bottles) have a MangoHud switch in their game settings."
            echo "In game, press Right Shift + F12 to show or hide it."
            ;;
        off)
            if preset_active; then
                rm -f "$CONF"
                if [[ -f "$BACKUP" ]]; then
                    mv "$BACKUP" "$CONF"
                    echo "Restored your previous MangoHud config."
                fi
                echo "NebulaOS FPS overlay preset removed."
            else
                echo "The NebulaOS preset is not active; nothing to do."
            fi
            ;;
        status)
            if preset_active; then
                echo "NebulaOS FPS overlay preset: ON ($CONF)"
            else
                echo "NebulaOS FPS overlay preset: OFF"
            fi
            ;;
        *)
            echo "Usage: ujust nebula-fps-overlay [on|off|status]" >&2
            exit 1
            ;;
    esac

# Only accept NebulaOS updates signed with your key (run once after switching to NebulaOS)
[group("NebulaOS")]
nebula-enable-signed-updates:
    #!/usr/bin/bash
    set -euo pipefail
    TARGET="ostree-image-signed:docker://$(cat /usr/share/nebula-os/image-ref)"
    CURRENT=$(rpm-ostree status --json | jq -r '.deployments[] | select(.booted == true) | .["container-image-reference"]')
    if [[ "$CURRENT" == "$TARGET" ]]; then
        echo "Signed updates are already on: $TARGET"
        exit 0
    fi
    echo "Current: $CURRENT"
    echo "New:     $TARGET"
    echo "(This fails safely if your published images are not signed yet.)"
    sudo rpm-ostree rebase "$TARGET"
    echo "Done. Reboot to finish."

# Go back to the stock Bazzite edition NebulaOS is built on (your files, settings and apps stay)
[group("NebulaOS")]
nebula-switch-to-bazzite:
    #!/usr/bin/bash
    set -euo pipefail
    BASE=$(cat /usr/share/nebula-os/base-image)
    echo "Switching this system to ${BASE} ..."
    sudo rpm-ostree rebase "ostree-image-signed:docker://${BASE}"
    echo "Done. Reboot to start Bazzite."
