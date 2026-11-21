#!/usr/bin/bash
# Extra RPM packages baked into the image.
#
# Bazzite already ships Steam, Lutris, Gamescope, MangoHud, vkBasalt, nvtop,
# vulkan-tools and much more, so only add what is missing here.
# Desktop apps are usually better as Flatpaks: add those to
# system_files/usr/share/nebula-os/flatpaks.list instead.
set -euo pipefail

# Bazzite DX already includes the developer tools (VS Code, Docker, Podman,
# virt-manager, Android tools...), so the list starts empty. Add package names
# here, one per line.
# Note: Fedora's goverlay can't be added: it pulls in Fedora's mangohud, which
# conflicts with Bazzite's terra-mangohud. MangoJuice (Flatpak) replaces it.
PACKAGES=(
)

if ((${#PACKAGES[@]})); then
    dnf5 -y install --setopt=install_weak_deps=False "${PACKAGES[@]}"
fi

# Example: install from a COPR repository, then disable the repository again so
# it does not stay enabled on installed systems:
#
#   dnf5 -y copr enable ilyaz/LACT
#   dnf5 -y install lact
#   dnf5 -y copr disable ilyaz/LACT
#   systemctl enable lactd.service
