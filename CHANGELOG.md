# Changelog

All notable changes to NebulaOS. Channels: `testing` (branch `dev`) and stable `latest` (branch `main`).

## Unreleased

### Fixed
- `nebula status`, `nebula hw` and `nebula doctor` woke a laptop's sleeping dedicated GPU every time (measured: 0.7 to 1.3 s per run on a Legion 5). GPU names now come from the PCI ID database instead of `lspci`, which reads every device's configuration space.
- `ujust nebula-mode work now` from a text console (Ctrl+Alt+F3) closed the console instead of a stuck Gaming Mode session. It now closes the graphical session.
- On AMD APUs, the integrated GPU's "power" was the power of the whole processor. It is now reported as `package_power_w`.
- A GPU drawing 0 W was reported as unknown. Two identical GPUs shared one Vulkan result. On Ryzen CPUs with a temperature offset, the CPU temperature read high (Tctl instead of Tdie). The total network rate counted container and VM traffic several times.
- The installer ISO and VM image builds failed: the builder could not see Fedora's repositories (dnf5 keeps them in `/usr/share/dnf5/repos.d`), and Ubuntu's AppArmor blocked its sandbox.

### Added
- [Backend and Gaming Mode audit](docs/BACKEND_GAMING_AUDIT.md), with the Legion 5 15ACH6A as the primary target.

### Removed
- All AI tools: ramalama, `ujust install-ai-tools` and LM Studio in Bazzite Portal (inherited from Bazzite DX), the local AI guide and the planned AI Hub. ROCm (general GPU compute) and onnxruntime (needed by FFmpeg for video playback) stay.

## 0.2.0: Foundation (2026-11-21)

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
- CI: lint (shellcheck, hadolint, actionlint), config validation, 77 unit tests, 43 image tests before publishing, signature verification, weekly Trivy scan and SBOM.
- `build-info.json`, plus base image name and digest labels in every image.
- Documentation: technical audit, architecture, roadmap, installation, hardware compatibility, troubleshooting, release process, gaming, development, AI, security and contributing guides.

### Fixed
- VS Code was missing from the dock (wrong launcher ID). Bazzite Portal and Lutris are back in the dock.
- Bazzite's mode-switching tools failed silently on the DX base (missing `steamosctl`).
- The mode status ignored Bazzite's "Plus" Gaming Mode session.
- The publish order could leave an unsigned `latest` image if a run was cancelled.
- The disk-image workflow built the published image instead of the pull request.
- The NVIDIA edition did not build: the strict GNOME settings check also checked Bazzite's NVIDIA override, which names a key its GNOME no longer has. Only the NebulaOS override is checked strictly now.
- `nebula doctor --report` kept the permissions of an existing file, so a report could stay readable by other users, and it wrote through symlinks. The report is now always a new file that only you can read; symlinks are refused.
- `nebula hw` crashed on an EDID with a corrupt CTA-861 data block, and its HDR evidence showed key names instead of PQ and HLG.
- The System Doctor listed connected Bluetooth devices as adapters.
- `nebula status` and `nebula update` could crash on unexpected `rpm-ostree` output.
- The mode status answered "work" when the saved mode could not be read. It now reports an error, and `ujust nebula-mode` shows "unknown".
- Published images lost all their labels when they were rechunked, so `rpm-ostree status` and Bazzite's update tools showed no version. The labels are now copied, and the build fails if the version label is missing. Labels inherited from Bazzite (its commit and source) are no longer passed on.
- The NVIDIA edition's links (Settings › About, bug reports) pointed to a repository that does not exist.

### Changed
- The app-bundle installer only installs (updates stay with Bazzite's updater) and runs with systemd hardening.
- Fewer tags per build: `<channel>`, `<channel>-<date>`, `<channel>-<commit>`.
- Disk images are built on demand for a chosen edition and channel, and kept for 7 days.

### Removed
- GOverlay. Fedora's package conflicts with Bazzite's MangoHud; MangoJuice in the app bundle replaces it.

## 0.1.0 (2026-11-21)

- First NebulaOS image on Bazzite DX GNOME: two sides (Steam Gaming Mode and GNOME Work Mode), branding, app bundle, Bazaar *Development & Work* row, FPS overlay preset, signed images built daily on GitHub.
