#!/usr/bin/bash
# Turn on NebulaOS's own background services.
set -euo pipefail

# Installs the NebulaOS app bundle from Flathub on first boot, and any apps
# added to the list in later updates.
systemctl enable nebula-os-flatpak-setup.service

# No hidden telemetry (owner's blueprint): Fedora's rpm-ostree-countme timer sends an anonymous
# weekly "one more system" ping to Fedora's servers. On image-based systems it also fails (seen in the
# 12-hour VM run, 2026-11-23). Disable it and keep it disabled through presets; on systems updating
# from an older image the unchanged /etc link is removed by the /etc merge.
systemctl disable rpm-ostree-countme.timer 2>/dev/null || true
install -Dm0644 /dev/stdin /usr/lib/systemd/system-preset/10-nebula-os.preset <<'PRESET'
# NebulaOS: no anonymous usage counting (rpm-ostree-countme).
disable rpm-ostree-countme.timer
PRESET
