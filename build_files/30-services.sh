#!/usr/bin/bash
# Turn on NebulaOS's own background services.
set -euo pipefail

# Installs the NebulaOS app bundle from Flathub on first boot, and any apps
# added to the list in later updates.
systemctl enable nebula-os-flatpak-setup.service
