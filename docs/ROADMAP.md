# NebulaOS roadmap

**One operating system. Two worlds.** NebulaOS builds original software only where it adds a genuinely new capability, and reuses what Bazzite and Universal Blue already do well (see the inherit-or-build table in [the audit](NEBULAOS_TECHNICAL_AUDIT.md#5-inherit-or-build-the-existing-ecosystem)).

Every phase ends with tests, documentation, and a release to the `testing` channel before `stable`. Nothing is listed as a feature until it is implemented and verified.

## Phase 1: Foundation ✅ (this release)

- [x] Full technical audit ([NEBULAOS_TECHNICAL_AUDIT.md](NEBULAOS_TECHNICAL_AUDIT.md)) and architecture documentation ([ARCHITECTURE.md](ARCHITECTURE.md))
- [x] Build reliability: CI gates (lint, unit tests, 40 image tests), safe publish order (sign, verify, then move the channel tag), stable/testing channels, base digest recorded
- [x] Security: least-privilege workflows, weekly Trivy scan and SBOM, hardened app-installer service
- [x] **Nebula Hardware Detection Engine v1** (`nebula hw`): GPUs with vendor backends (AMD, Intel, NVIDIA), Vulkan, OpenGL, VA-API, architecture, hybrid graphics (CardWire), displays with EDID, current mode, VRR and HDR, using the five-level capability model
- [x] **Nebula System Doctor v1** (`nebula doctor`): 12 read-only checks, suggested fixes, exportable report
- [x] **Unified monitoring backend v1** (`nebula status --json`) and update management (`nebula update check|history|apply|rollback`)
- [x] Mode choice at every login (NebulaOS Gaming Mode / Work Mode) and working mode switching on Bazzite DX GNOME
- [x] NVIDIA edition built in CI (`nebula-os-nvidia`)
- [ ] Run the update and rollback runbook in a VM and on the reference laptop, and record the results ([RELEASE_PROCESS.md](RELEASE_PROCESS.md#verifying-updates-and-rollback))
- [ ] Move `cosign.key` to an offline backup; add a backup signing key for rotation

## Phase 2: Nebula Control Center and System Doctor GUI

A native GTK 4 / libadwaita app (Python + PyGObject, both already in the base), dark by default, using the NebulaOS palette (Deep Space `#090B14`, Nebula Blue `#4263EB`, Cosmic Purple `#805AD5`, Cyan `#22D3EE`, Surface `#151A2B`, Text `#F1F5F9`).

- Dashboard over the `nebula` backend: CPU, GPU, RAM, storage, temperatures, network, uptime, version, updates, power profile, GPU driver, health. It refreshes live without waking sleeping GPUs.
- Management actions through the existing tools: updates (uupd / `ujust update`), deployments and rollback (rpm-ostree D-Bus, polkit), services (systemd), apps (opens Bazaar and Bazzite Portal), hybrid graphics (opens CardWire), logs and boot info.
- System Doctor page: run checks, show fixes, export a report. Fixes are never applied automatically; each one is a button that shows the command and asks for confirmation.
- Rules: the GUI never runs as root. Privileged operations go through polkit-checked D-Bus calls of the underlying tools (rpm-ostree, systemd, AccountsService). Any NebulaOS helper must have a fixed, allow-listed set of actions.

Depends on: Phase 1 backend. Risk: GTK and libadwaita API churn across GNOME versions. Mitigation: CI tests run against the real base image.

## Phase 3: Gaming (AAA gaming and visual quality engine)

Built on the Phase 1 Hardware Detection Engine and the capability model. All configuration is per user (`~/.config/nebula-os/`), never in the OS image, and every change follows **validate → preview → confirm → apply → verify → can roll back**.

1. **GPU backend architecture v2.** Extend the AMD, Intel and NVIDIA backends behind the shared interface with clocks, power limits as read-only info, and Intel busyness via perf where permitted. Unsupported features are shown as unavailable, never hidden in a way that implies support.
2. **Display Lab.** Read-only display profiles first (modes, refresh, VRR, HDR, EDID, colour depth). Then guided changes through GNOME's own display API with its built-in "keep these settings?" auto-revert. Unsupported modes are never offered.
3. **Visual Quality Engine.** A per-game Gamescope launch-option builder (resolution, FSR or NIS upscaling and sharpening, HDR, frame limit) that only offers what the capability report says works. Incompatible upscalers are never combined. Optional vkBasalt profiles, kept subtle.
4. **Quality profiles.** Ultra Quality, 4K Cinematic, HDR Experience, Balanced Quality, High Refresh and Custom, generated from the detected hardware and display. These are recommendations, never guarantees.
5. **Nebula Gaming Optimizer.** Power and performance profiles (Balanced, Performance, Maximum Performance, Battery Saver, Quiet Gaming) through the supported interfaces Bazzite already ships: the power-profiles D-Bus API (tuned-ppd), scx_loader schedulers and MangoHud frame limits. Per-game profiles, session history and controller shortcuts (Steam Input and InputPlumber stay in charge).
6. **Benchmark Lab.** MangoHud CSV logging per run, with average FPS, 1% and 0.1% lows, frame-time consistency, CPU and GPU utilisation, RAM, temperatures and power where exposed. Runs are comparable across NebulaOS versions and against the same Bazzite version on identical hardware and settings. Results are reported as measured, never adjusted.
7. **Compatibility helpers.** ProtonDB lookup (opt-in network call), launch troubleshooting from logs, shader cache *reporting* (never automatic deletion), and game library storage overview. Proton versions stay with ProtonPlus.

Depends on: Phases 1 and 2. Risk: needs real hardware for every vendor; see the testing matrix below.

## Phase 4: Development and AI

- **Nebula Dev Hub.** Distrobox-assemble templates (Python, web, full-stack, AI, Android, game development, C/C++), create, start, stop, delete, export and import, and a view of installed dependencies. It orchestrates Bazzite DX's Podman, Docker, distrobox, BoxBuddy, VS Code and Homebrew, and does not replace them.
- **Nebula AI Hub.** Discover and install AI tools as containers or Flatpaks (ramalama and Alpaca from the base; Ollama, Open WebUI, llama.cpp, JupyterLab and ComfyUI as optional containers). Show GPU resources and the matching acceleration (ROCm, CUDA on NVIDIA, Vulkan), manage model storage, and never download models automatically.

## Phase 5: Identity and creative work

- Palette applied to GNOME (accent colour, wallpaper set). GTK, icon and cursor themes only where they stay consistent with libadwaita apps.
- Login (GDM) and boot (Plymouth) branding. Plymouth needs an initramfs rebuild in the image, which must be measured for boot-time and update-size cost first.
- Creative Studio profiles (video, audio, 3D, graphics) as Bazaar rows and Bazzite Portal entries, after checking each app's GPU support (for example, DaVinci Resolve only where its requirements are met).

## Phase 6: Public release

- VM boot tests in CI (qcow2 under QEMU/KVM): the image boots, both login sessions exist, `nebula doctor` reports no failures, and update then rollback work.
- ISO installation tested in VMs before it is recommended on hardware.
- Performance measurements against the same Bazzite version: boot time, idle RAM and CPU, app start-up, image and update size, update duration. Every trade-off is documented.
- Release notes generated from the changelog, a documented stable promotion, registry tag retention, and signing key rotation.

## Testing matrix

| Hardware | Status |
| --- | --- |
| AMD hybrid laptop (Ryzen 7 5800H + Vega iGPU + RX 6600M, 1080p 165 Hz VRR panel) | Backend verified on Bazzite; NebulaOS image boot pending |
| AMD desktop GPU, 1440p/4K, HDR, VRR monitors | Needs testers |
| NVIDIA (Turing or newer) | Needs testers (edition builds in CI) |
| Intel integrated (Xe), Intel Arc | Needs testers |

Run `nebula hw --json` and attach the output to a GitHub issue to add your hardware.
