# NebulaOS technical audit

Date: 2026-11-21 · Scope: the `nebula-os` repository at commit `aaf9cf6` (branch `main`), the image built from it, and the published image `ghcr.io/trevor99-afk/nebula-os:latest`.

## How the audit was done

- Four independent read-only reviews, each with one lens: build and CI/supply chain, runtime integration with the Bazzite ecosystem, security and privacy, and product gaps against the NebulaOS master plan.
- Every finding needed evidence: a file and line, a command and its output, or a quoted upstream source. Before any fix, findings were re-checked by hand against the built image (`podman run localhost/nebula-os:latest …`) and against the machine the project is developed on (Bazzite GNOME, Lenovo Legion 5 15ACH6A, Ryzen 7 5800H with Radeon Vega iGPU and RX 6600M).
- Not verifiable in this environment, so not claimed: booting the image, Steam Gaming Mode on real hardware, switching modes in a live session, and an ISO installation. These are listed under [Unverified](#unverified-needs-a-real-boot).

## Summary

NebulaOS is a working, signed bootc image built on Bazzite DX. The base is sound: the build succeeds, the image is signed and verifiable, it is public, and it updates daily. The weak spots were around that base: CI published images without testing them, the publish order could leave an unsigned image behind, some defaults pointed at files that don't exist, and Bazzite's own mode-switching tools were broken on the DX GNOME base. Almost none of the planned original NebulaOS software existed yet.

This change fixes every verified defect below, adds the test and security gates to CI, and starts the original software with the `nebula` backend tool: system status, the Hardware Detection Engine, the System Doctor and update management.

## 1. What works

| Area | Evidence |
| --- | --- |
| Image build | Local `podman build` and GitHub Actions run 44943904428 succeed; `bootc container lint` passes 12 checks. Its 2 warnings come from the base image. |
| Signing | `cosign verify --key cosign.pub ghcr.io/trevor99-afk/nebula-os:latest` validates the signature, and the transparency log entry is checked. |
| Distribution | The image can be pulled anonymously (public package). A daily scheduled rebuild follows Bazzite's `stable`. |
| Identity | os-release, the boot menu entry, the hostname default, the terminal welcome, the wallpaper and logo are branded. `image-info.json` is deliberately untouched, because Bazzite's hardware, Steam and flatpak scripts read `image-name` from it. |
| Signature policy | `policy.json` and `registries.d` entries for the project's repository are written by `build_files/40-signing.sh`. |
| Two modes | Bazzite DX provides both Steam Gaming Mode sessions and GNOME. GDM keeps a login screen, so both modes need the user's password. |
| Bazaar | The "Development & Work" row is inserted into Bazaar's curated `content.yaml`; every app ID exists on Flathub. |
| Security baseline | SELinux is enforcing (verified on the reference machine). NebulaOS adds no telemetry, and git history contains no private key material. |

## 2. Broken (found and fixed in this change)

| # | Problem | Evidence | Fix |
| --- | --- | --- | --- |
| B1 | The dock entry for VS Code pointed at `code.desktop`, which does not exist, so VS Code never appeared in the dock. | The image only has `com.microsoft.VSCode.desktop`. | Corrected the ID. `90-finalize.sh` now fails the build if a dock entry has no `.desktop` file. |
| B2 | The NebulaOS dock override dropped Bazzite Portal and Lutris from Bazzite's defaults. | Bazzite's dash override lists `io.github.ublue_os.yafti_gtk.desktop` and `net.lutris.Lutris.desktop`. | Both are restored. |
| B3 | Bazzite's own switching tools (`return-to-gamemode`, its `os-session-select`, `ujust set-default-game-mode`/`set-default-desktop`) call `steamosctl`, which Bazzite DX removes. They failed silently. | There is no `steamosctl` in the image, and `grep` shows the callers. | Added a `steamosctl` compatibility shim, installed only if the base has none. It maps those commands onto NebulaOS's GDM-aware mode switcher. |
| B4 | `nebula-os-switch-side status` only recognised one of Bazzite's two Gaming Mode sessions. | `gamescope-session-ogui-steam` was reported as "work". | Every `gamescope-session*` session now counts as Gaming Mode. |
| B5 | Switching with `--now` from a TTY with no session ID ran `loginctl terminate-session ''`. | Code path at the end of the switcher. | It now prints instructions instead. |
| B6 | The disk-image workflow built the published image, not the pull request's code, on pull requests. It also failed while the package was private. | PR run 44943662560: `403 Forbidden`, then `image not known`. | It now runs only on demand, with a choice of edition and channel. Artifacts are kept for 7 days instead of the repository default of 90. |

## 3. Risks (fixed in this change)

| # | Risk | Fix |
| --- | --- | --- |
| R1 | CI published images that were never tested. Only `bootc container lint` ran before the push. | A `checks` job now runs shellcheck, actionlint, hadolint, config validation and the unit tests. An image test suite (`tests/image/test-image.sh`) runs on every built image before anything is pushed. |
| R2 | All tags were pushed before signing, and `cancel-in-progress` could cancel a run between push and sign. Users with signature enforcement would then get an unsigned `latest`. | Dated and commit tags are pushed first, then the image is signed, the signature is verified, and only then is the channel tag moved. Only pull request runs can be cancelled. |
| R3 | Over-broad permissions: `id-token: write` was granted but key-based signing never uses it. | Removed. The workflow default is `contents: read`, and only the build job gets `packages: write`. |
| R4 | No traceability: the floating `:stable` base left no record of which base digest went into an image. | The build records `org.opencontainers.image.base.name` and `base.digest` labels plus `/usr/share/nebula-os/build-info.json`, which `nebula status` shows. |
| R5 | Every build added 5 tags, with no release channels. | Each build now adds 3 tags: `<channel>`, `<channel>-<date>` and `<channel>-<commit>`. Branch `main` publishes the stable channel (`latest`) and `dev` publishes `testing`. |
| R6 | No vulnerability scanning or SBOM. | A weekly Trivy scan reports to the Security tab, and a CycloneDX SBOM is kept as an artifact. This is report-only, because most findings come from the Fedora and Bazzite base. |
| R7 | The app installer service ran as root without hardening, and also updated apps, which is the job of Bazzite's updater. | Added `NoNewPrivileges`, `PrivateTmp` and kernel and cgroup protection. The installer now only installs apps. |

## 4. Remaining risks (not fixed here)

| Risk | Why it stays | Mitigation |
| --- | --- | --- |
| The first `bootc switch` to NebulaOS is unverified, because the host does not trust the NebulaOS key yet. | This is inherent to switching from another image. | [INSTALLATION.md](INSTALLATION.md) now verifies the signature with `cosign verify` *before* switching. After the switch, `ujust nebula-enable-signed-updates` turns enforcement on. |
| `cosign.key` is passwordless and was stored unencrypted in the project folder. | CI needs it as a secret. | Move the local copy to a password manager or offline backup and delete it from disk. See [SECURITY.md](../SECURITY.md). A backup key (`keyPaths`) would make rotation easier. |
| The bootc-image-builder image and the base use floating tags. | Following Bazzite daily is intended. | The base digest is now recorded in every image. Pinning the builder image is a Phase 6 task. |
| ISO installation and VM boot are untested. | This needs root or a VM with installation rights. | They are documented as experimental. VM boot tests are on the roadmap (Phase 6). |
| Dual-GPU laptops can show a black screen in Steam Gaming Mode (a known gamescope limitation, improved by CardWire in Bazzite 44). | Upstream. | Work Mode is always available at the login screen. `nebula hw` reports hybrid setups. |
| `ujust restore-gnome-de-settings` (Bazzite) resets the dock and wallpaper to Bazzite's values. | It is a Bazzite recipe. | Documented in [TROUBLESHOOTING.md](TROUBLESHOOTING.md). |

## 5. Inherit or build? The existing ecosystem

The rule for NebulaOS: **reuse what Bazzite and Universal Blue already do well, and build original software only for genuinely new capabilities.**

| Component (provider) | What it does | NebulaOS decision |
| --- | --- | --- |
| Bazaar (Bazzite) | Flatpak app store with curated rows | **Inherit.** No NebulaOS store. Add curated rows (Development & Work) and link to it from NebulaOS tools. |
| Bazzite Portal / yafti (Bazzite) | Setup wizard and tailored software installation | **Inherit.** Kept in the dock; future profiles (Creative, Dev, AI) should be offered through it or through Bazaar rows. |
| ujust recipe catalogue (Universal Blue) | Gaming and system fixes, ProtonPlus, Decky, frame generation, device info, logs | **Inherit.** NebulaOS tools call these recipes instead of duplicating them. |
| uupd (Universal Blue) | Unified updates for the OS, Flatpaks, Homebrew and distrobox | **Inherit.** `nebula update` only reports status and wraps rpm-ostree for explicit actions. There is no second update daemon. |
| Steam and gamescope sessions (Bazzite) | Gaming Mode | **Inherit.** NebulaOS only names the sessions and hooks `/usr/lib/os-session-select`. |
| ProtonPlus, Protontricks, Bottles, Lutris, Heroic | Proton and Wine management, launchers | **Inherit.** The future Gaming Optimizer reads their state and does not manage runners. |
| CardWire (Bazzite) | Hybrid-GPU manager | **Inherit.** `nebula hw` reports its mode; no NebulaOS GPU switcher. |
| InputPlumber (Bazzite) | Controller and handheld input | **Inherit.** Diagnose only. |
| MangoHud and vkBasalt (Bazzite) | Overlay and post-processing | **Inherit.** NebulaOS writes configs and profiles (`nebula-fps-overlay`), never another overlay. |
| tuned / tuned-ppd, scx_loader (Bazzite) | Power profiles and CPU schedulers | **Inherit.** The future Gaming Optimizer switches profiles through their D-Bus APIs. |
| Distrobox, Podman, Docker, BoxBuddy, Podman Desktop, virt-manager (Bazzite DX) | Containers, dev environments, VMs | **Inherit.** The future Dev Hub orchestrates them with templates. |
| ramalama, Alpaca, ROCm userland (Bazzite DX) | Local AI | **Inherit.** The future AI Hub orchestrates them. |
| **Status, monitoring, hardware detection, System Doctor** | Not available as one tool | **Original:** the `nebula` backend (this change). |
| **Control Center, Gaming Optimizer, Display Lab, Dev Hub, AI Hub** | Not available | **Original:** planned, see [ROADMAP.md](ROADMAP.md). |

## 6. Requirements status

| Area | State after this change |
| --- | --- |
| Audit, architecture docs | Done (this document, [ARCHITECTURE.md](ARCHITECTURE.md)) |
| Immutable, atomic, rollback, signed | Inherited from bootc and rpm-ostree; signing is NebulaOS's. Rollback is documented; a VM verification runbook is in [RELEASE_PROCESS.md](RELEASE_PROCESS.md). |
| Hardware detection and capability report | **Done:** `nebula hw` (Hardware Detection Engine v1) |
| System Doctor | **Done (CLI v1):** `nebula doctor`, 12 read-only checks with suggested fixes and an exportable report |
| Unified monitoring data | **Done (CLI v1):** `nebula status` and `--json` for future front ends |
| Updates: check, history, apply, rollback with confirmation | **Done (CLI v1):** `nebula update …`. uupd stays the updater. |
| Stable and testing channels | **Done:** `main` publishes `latest`, `dev` publishes `testing` |
| CI: lint, tests, image tests, signing verification, security scan | **Done.** VM boot tests are still missing. |
| NVIDIA edition | **Builds in CI** (`nebula-os-nvidia`). Untested on NVIDIA hardware. |
| Control Center GUI, Gaming Optimizer, Display Lab, Visual Quality Engine, Benchmark, Dev Hub, AI Hub, Creative profiles, GTK, icon and cursor themes, boot branding | **Planned:** [ROADMAP.md](ROADMAP.md) |
| Own app store | **Dropped** as a duplicate of Bazaar |
| Performance comparison with Bazzite | **Planned.** Needs real hardware runs. |

## 7. Follow-up review of the Phase 1 code

Two more read-only reviews ran against commit `acd13d9`: one of the `nebula` backend, and one of mode switching and the CI publish path. CI also built both editions for the first time. Every finding was reproduced by hand before it was fixed, and every fix has a test that fails on `acd13d9`.

| # | Problem | Evidence | Fix |
| --- | --- | --- | --- |
| F1 | The NVIDIA edition did not build. | CI run 44949472907: `No such key "experimental-features" in schema "org.gnome.mutter" as specified in override file ".../zz0-20-bazzite-nvidia-silverblue-global.gschema.override" and --strict was specified`. The file comes from the Bazzite NVIDIA base. | The NebulaOS override is checked strictly on its own, and the full compile is not strict, like Bazzite's own. Reproduced with the same override in the AMD/Intel image. A typo in the NebulaOS override still fails the build. |
| F2 | `nebula doctor --report` kept an existing file's permissions (for example 0644) and followed symlinks. | `os.open(path, ..., 0o600)` sets the mode of new files only. | The report goes to a new private file that is then moved into place. A symlink or non-file path is refused. |
| F3 | `nebula hw` crashed (`IndexError`) on an EDID whose CTA-861 data block runs past the data block area. | A synthetic EDID, and a fuzz test with 3,000 random extension blocks. | Parsing stops at such a block, as the Linux kernel's EDID parser does. |
| F4 | HDR evidence read "eotf_pq, eotf_hlg" instead of "PQ, HLG". | Unit test. | The labels are used. |
| F5 | Connected Bluetooth devices (`hci0:HANDLE` entries in `/sys/class/bluetooth`) were listed as adapters. | Fake sysfs tree. | Only `hciN` entries count as adapters. |
| F6 | Unexpected `rpm-ostree status --json` output crashed `nebula status` and `nebula update`. | `[]`, `null` and `{"deployments": null}` raised exceptions. | Such output counts as "no deployment information". |
| F7 | The mode status printed "work", and reported success, when AccountsService could not be reached. | A stubbed `busctl` that fails. | It now fails with a message. `ujust nebula-mode` shows "unknown", and the `steamosctl` shim passes the failure on. Two image tests cover this. |

## Unverified (needs a real boot)

These are implemented but have not been exercised on a booted NebulaOS system:

1. The login screen shows the renamed sessions and the mode message (the files are tested inside the image).
2. "Switch to Gaming Mode" (dock) and Steam's "Switch to Desktop" move between modes through AccountsService and GDM.
3. The `steamosctl` shim makes Bazzite's own buttons and recipes work.
4. The app bundle service with the new hardening installs apps on first boot.
5. `nebula-enable-signed-updates` followed by a signed upgrade.
6. The ISO installer.

The reference machine runs stock Bazzite, so `nebula status`, `nebula hw`, `nebula doctor` and `nebula update check` were run there and their output checked by hand. That covers the backend, but not the image.
