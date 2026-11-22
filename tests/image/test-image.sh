#!/usr/bin/bash
# shellcheck disable=SC2016  # $vars inside single quotes are jq/bash -c code, on purpose
# Smoke tests that run inside a freshly built NebulaOS image (no systemd, no D-Bus):
#   just test-image            (or)
#   podman run --rm -v ./tests/image:/tests:ro IMAGE bash /tests/test-image.sh EXPECTED_IMAGE_REF [EXPECTED_REPO_URL]
# Exits non-zero if any test fails, so CI never publishes a broken image.
set -uo pipefail

EXPECTED_REF="${1:-}"
EXPECTED_REPO_URL="${2:-}"
FAILED=0
pass() { echo "PASS  $*"; }
fail() {
    echo "FAIL  $*"
    FAILED=$((FAILED + 1))
}
check() {
    local desc=$1
    shift
    if "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi
}
export HOME=/tmp XDG_RUNTIME_DIR=/tmp

# --- Identity -----------------------------------------------------------------------
# shellcheck source=/dev/null
. /usr/lib/os-release
check "os-release is branded (NAME=$NAME)" test "$NAME" != "Bazzite"
check "os-release keeps ID=bazzite for compatibility" test "$ID" = "bazzite"
check "image-info.json still names the Bazzite base" grep -q '"image-name": *"bazzite' /usr/share/ublue-os/image-info.json
check "build-info.json is valid JSON with a version" jq -e '.version and .base_image' /usr/share/nebula-os/build-info.json
if [[ -n "$EXPECTED_REF" ]]; then
    check "update address is $EXPECTED_REF" test "$(cat /usr/share/nebula-os/image-ref)" = "$EXPECTED_REF"
    repo="${EXPECTED_REF%:*}"
    check "signature policy covers $repo" jq -e --arg r "$repo" '.transports.docker[$r][0].type == "sigstoreSigned"' /etc/containers/policy.json
    check "registries.d enables sigstore attachments" grep -q "$repo" /etc/containers/registries.d/nebula-os.yaml
fi
if [[ -n "$EXPECTED_REPO_URL" ]]; then
    check "os-release links to $EXPECTED_REPO_URL" \
        test "${HOME_URL:-}|${BUG_REPORT_URL:-}" = "$EXPECTED_REPO_URL|$EXPECTED_REPO_URL/issues"
fi

# --- Services and executables ------------------------------------------------------------
check "app bundle service is enabled" test -L /etc/systemd/system/multi-user.target.wants/nebula-os-flatpak-setup.service
check "app bundle service unit is valid" systemd-analyze verify /usr/lib/systemd/system/nebula-os-flatpak-setup.service
for exe in /usr/bin/nebula /usr/libexec/nebula-os-flatpak-setup /usr/libexec/nebula-os-switch-side \
    /usr/libexec/nebula-os-steamosctl /usr/lib/os-session-select; do
    check "$exe is executable" test -x "$exe"
done
check "nebula tools are precompiled" compgen -G "/usr/lib/nebula-os/nebula/__pycache__/*.pyc"

# --- The nebula command --------------------------------------------------------------------
check "nebula --version runs" nebula --version
check "nebula hw --json is valid" bash -c 'nebula hw --json --no-probe | jq -e ".schema == \"nebula.hardware/v1\""'
check "nebula status --json is valid" bash -c 'nebula status --json | jq -e ".schema == \"nebula.status/v1\""'
check "nebula doctor --json is valid" bash -c 'nebula doctor --json | jq -e ".schema == \"nebula.doctor/v1\""'

# --- Modes (login screen) -------------------------------------------------------------------
S=/usr/share/wayland-sessions
check "Gaming Mode session is named" grep -qx 'Name=NebulaOS Gaming Mode' "$S/gamescope-session-steam.desktop"
check "Work Mode session is named" grep -qx 'Name=NebulaOS Work Mode' "$S/gnome.desktop"
check "Work Mode has no leftover translated names" bash -c "! grep -q '^Name\\[' $S/gnome.desktop"
check "steamosctl is available for Bazzite's switching tools" test -x /usr/bin/steamosctl
# This container has no system bus, so the saved mode cannot be read: both must fail, not guess.
check "mode status fails when AccountsService is unreachable" bash -c '! /usr/libexec/nebula-os-switch-side status'
check "steamosctl get-default-login-mode fails the same way" bash -c '! steamosctl get-default-login-mode'
check "Steam's Switch to Desktop reaches /usr/lib/os-session-select" grep -q '/usr/lib/os-session-select' /usr/bin/steamos-session-select
check "GDM profile reads the gdm database" bash -c 'grep -qs "system-db:gdm" /etc/dconf/profile/gdm /usr/share/dconf/profile/gdm'
check "login screen message is compiled into the gdm database" grep -qa 'banner-message-text' /etc/dconf/db/gdm
check "login screen shows the NebulaOS logo" bash -c 'grep -qa nebula-os-gdm-logo /etc/dconf/db/gdm && test -s /usr/share/pixmaps/nebula-os-gdm-logo.png'
# The terminal welcome message must name this image and send bug reports to NebulaOS.
check "welcome message shows the NebulaOS image" bash -c '! grep -q MOTD_IMAGE_NAME /usr/share/ublue-os/motd/template.md && grep -q "$(cat /usr/share/nebula-os/image-ref)" /usr/share/ublue-os/motd/template.md'
check "welcome message reports issues to NebulaOS" bash -c '! grep -q issues.bazzite.gg /usr/share/ublue-os/motd/template.md'

# --- No AI tools (removed by build_files/25-no-ai.sh) ----------------------------------------
check "ramalama is not installed" bash -c '! rpm -q ramalama'
check "ujust has no install-ai-tools" bash -c '! grep -qw install-ai-tools <<<"$(just --justfile /usr/share/ublue-os/justfile --summary)"'
check "Bazzite Portal offers no LM Studio" bash -c '! grep -q lm-studio /usr/share/yafti/yafti.yml'
check "video playback libraries are still there" rpm -q ffmpeg gstreamer1-plugin-libav

# --- Desktop defaults ---------------------------------------------------------------------------
favorites=$(gsettings get org.gnome.shell favorite-apps 2>/dev/null)
check "dock includes VS Code" grep -q 'com.microsoft.VSCode.desktop' <<<"$favorites"
check "dock includes Bazzite Portal" grep -q 'io.github.ublue_os.yafti_gtk.desktop' <<<"$favorites"
check "dock includes Switch to Gaming Mode" grep -q 'nebula-os-switch-to-gaming.desktop' <<<"$favorites"
check "default wallpaper is NebulaOS" bash -c 'gsettings get org.gnome.desktop.background picture-uri-dark 2>/dev/null | grep -q nebula-os'
check "Switch to Gaming Mode launcher is valid" desktop-file-validate /usr/share/applications/nebula-os-switch-to-gaming.desktop
check "NebulaOS logo is in the icon cache" grep -qa 'nebula-os-logo' /usr/share/icons/hicolor/icon-theme.cache
# Every dock app must exist after a fresh ISO install: shipped in the image, or installed
# on first boot from the app bundle. Firefox was pinned but missing (VM install, 2026-11-22).
check "every dock app is shipped or in the app bundle" bash -c '
    missing=0
    for app in $(gsettings get org.gnome.shell favorite-apps | tr -d "[],'"'"'"); do
        [[ -e /usr/share/applications/$app ]] && continue
        grep -qE "^${app%.desktop}([[:space:]]|#|\$)" /usr/share/nebula-os/flatpaks.list && continue
        echo "  not shipped and not in the app bundle: $app"; missing=1
    done
    exit $missing'
check "app bundle includes a web browser" grep -qE '^org\.mozilla\.firefox\b' /usr/share/nebula-os/flatpaks.list

# --- ujust, Bazaar and the app list ---------------------------------------------------------------
summary=$(just --justfile /usr/share/ublue-os/justfile --summary 2>/dev/null)
for recipe in nebula-info nebula-doctor nebula-hw nebula-mode nebula-install-apps nebula-fps-overlay; do
    check "ujust has $recipe" grep -qw "$recipe" <<<"$summary"
done
check "Bazaar has the Development & Work section exactly once" \
    test "$(grep -c '"Development & Work"' /usr/share/ublue-os/bazaar/content.yaml)" -eq 1
check "app list contains only valid Flatpak IDs" bash -c \
    "grep -oE '^[^#[:space:]]+' /usr/share/nebula-os/flatpaks.list | grep -vqE '^[A-Za-z0-9_-]+(\\.[A-Za-z0-9_-]+){2,}$'; test \$? -eq 1"

echo
if ((FAILED)); then
    echo "$FAILED image test(s) failed."
    exit 1
fi
echo "All image tests passed."
