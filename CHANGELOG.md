# Changelog

All notable changes to NebulaOS. Channels: `testing` (branch `dev`) and stable `latest` (branch `main`).

## 0.2.0: Foundation (testing)

### Added
- **`nebula` tool** (`/usr/bin/nebula`, Python standard library only):
  - `nebula status`: live overview (CPU, memory, storage, network, GPU usage and temperature, power profile, updates, health); `--json` for front ends.
  - `nebula hw`: Nebula Hardware Detection Engine v1. Reports GPUs with AMD, Intel and NVIDIA backends, architecture, Vulkan, OpenGL and VA-API probes, hybrid graphics (CardWire), displays (EDID, current mode, VRR, HDR) and the gaming stack. Each capability is reported at five levels: hardware, driver, available, enabled and verified.
  - `nebula doctor`: System Doctor v1 with 12 read-only checks (SELinux, services, disk, GPU drivers, firmware, updates, network, audio, Bluetooth, controllers, apps, boot), suggested fixes, and `--report` export.
  - `nebula update check|history|apply|rollback`: registry update check, deployments, and apply or rollback with confirmation.
- **Mode choice at every login:** sessions are named *NebulaOS Gaming Mode* and *NebulaOS Work Mode*, and the login screen explains how to pick one. `ujust nebula-mode gaming|work` (alias `nebula-side`) sets the default.
- `steamosctl` compatibility, so Steam's *Switch to Desktop*, `return-to-gamemode` and Bazzite's `ujust set-default-*` recipes work on Bazzite DX GNOME.
- `ujust nebula-doctor` and `ujust nebula-hw`.
- **NVIDIA edition** `nebula-os-nvidia` (based on `bazzite-dx-nvidia-gnome`), built in CI. Not yet tested on NVIDIA hardware.
- **Testing channel:** the `dev` branch publishes `:testing`.
- CI: lint (shellcheck, hadolint, actionlint), config validation, 66 unit tests, 40 image tests before publishing, signature verification, weekly Trivy scan and SBOM.
- `build-info.json`, plus base image name and digest labels in every image.
- Documentation: technical audit, architecture, roadmap, installation, hardware compatibility, troubleshooting, release process, gaming, development, AI, security and contributing guides.

### Fixed
- VS Code was missing from the dock (wrong launcher ID). Bazzite Portal and Lutris are back in the dock.
- Bazzite's mode-switching tools failed silently on the DX base (missing `steamosctl`).
- The mode status ignored Bazzite's "Plus" Gaming Mode session.
- The publish order could leave an unsigned `latest` image if a run was cancelled.
- The disk-image workflow built the published image instead of the pull request.

### Changed
- The app-bundle installer only installs (updates stay with Bazzite's updater) and runs with systemd hardening.
- Fewer tags per build: `<channel>`, `<channel>-<date>`, `<channel>-<commit>`.
- Disk images are built on demand for a chosen edition and channel, and kept for 7 days.

### Removed
- GOverlay. Fedora's package conflicts with Bazzite's MangoHud; MangoJuice in the app bundle replaces it.

## 0.1.0 (2026-11-21)

- First NebulaOS image on Bazzite DX GNOME: two sides (Steam Gaming Mode and GNOME Work Mode), branding, app bundle, Bazaar *Development & Work* row, FPS overlay preset, signed images built daily on GitHub.
