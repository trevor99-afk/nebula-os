# Repository and feature audit

**Snapshot:** 2026-11-22 · base commit `2f5fbca`.

This audit reads the source and tests on branch `dev` after `194eb83`, including the review fixes committed with it; it is not a statement about any released image. No image was built for this audit. A unit test, an image content check, a CI boot to GDM, an interactive VM session, backend testing on Bazzite, and NebulaOS hardware testing are separate evidence levels.

## Classification key

- **Implemented + tested:** implementation has test evidence at the level explicitly named in the row. This does not imply higher-level validation.
- **Implemented, not fully tested:** source is present, but required integration, boot, or hardware evidence is absent.
- **Partial:** a lower-level component exists, but the user-facing feature or full behavior is incomplete.
- **Planned:** described as future work; no implementation found.
- **Missing:** the audited tree has no implementation or test for the expected capability.
- **Broken:** a reproducible failure exists in the audited tree. No currently reproducible broken end-user feature was established by this read-only audit.
- **Potentially unsafe:** an integration or operating practice has a credible safety/security concern that needs validation or a guardrail.

“Tested” below always names its actual level. Unit tests do not establish behavior in a booted image, and image tests do not exercise a login session.

## Repository structure

| Path | Purpose |
|---|---|
| `Containerfile`, `Justfile` | Build and release recipes for an OCI bootc image, disk artifacts, linting, unit tests, and image smoke checks. The Containerfile uses Bazzite DX GNOME as its default base (`Containerfile:7-10`). |
| `build_files/` | Ordered image customization steps: packages, Bazaar, services, removal of AI tools, branding, mode/session setup, signing, finalization. `build_files/build.sh` runs the steps. |
| `system_files/` | Files installed into the image: Python backend, CLI, session wrapper/chooser/switcher, Just recipes, app bundle, desktop settings and branding. |
| `tests/unit/` | Python unit tests for the backend, mode logic, chooser wrapper, update behavior, and documentation assertions. |
| `tests/image/` | In-image content/configuration smoke checks. They run without systemd or D-Bus (`tests/image/test-image.sh:1-7`). |
| `tests/vm/` | Manual QEMU VM helpers and a CI disk-image boot smoke test. |
| `.github/workflows/` | Container build/test/publish and manual disk-image/boot workflows. |
| `docs/`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` | User, maintainer, architecture, security, release, and roadmap documentation. |

The image pipeline inherits most of its operating system and gaming stack from Bazzite DX; Nebula adds identity, a mode chooser/switching layer, app bundle setup, a small CLI/backend, and image policy/configuration. This is not a separate kernel, driver, package-store, or gaming-platform implementation (`Containerfile:7-10`; `docs/ARCHITECTURE.md`).

## Feature audit

| Feature | Classification | Evidence and exact evidence level |
|---|---|---|
| Bazzite DX GNOME bootc base and inherited Steam/gamescope stack | **Implemented + tested** | Base reference is `Containerfile:7-10`; build CI runs the project’s image checks (`.github/workflows/build.yml`, `tests/image/test-image.sh`). Image checks validate presence/configuration only; they do not prove a gaming session starts. The base has been used for backend measurements on the named Legion running stock Bazzite (`docs/BACKEND_GAMING_AUDIT.md:7`), which is **Bazzite hardware testing**, not a NebulaOS image test. |
| AMD/Intel and NVIDIA image variants | **Implemented, not fully tested** | `Containerfile:7-10` and `.github/workflows/build.yml:70-125` select/build image editions, and `tests/image/test-image.sh` checks image contents. This establishes build/config coverage, not NVIDIA or Intel hardware operation. |
| Nebula branding, wallpapers, GDM identity, Logo Menu icon and MangoHud palette | **Implemented, not fully tested** | Installed by `build_files/10-branding.sh`; image assertions are in `tests/image/test-image.sh:74-105`. This is an **image-content smoke check**, not a visual GNOME login test. Plymouth remains Bazzite-branded and is **planned** (`docs/ROADMAP.md:20,75`). |
| Direct GDM Work and Gaming sessions, Gamescope session naming, Bazzite/Steam switching hooks | **Implemented, not fully tested** | `build_files/35-modes.sh`; `system_files/usr/libexec/nebula-os-switch-side`; `system_files/usr/libexec/nebula-os-steamosctl`; `system_files/usr/lib/os-session-select`. Unit coverage includes `tests/unit/test_mode_scripts.py::SteamHooks.test_switch_to_desktop_goes_to_work_mode` and `test_steamosctl_shim`; image checks validate session names and hooks. Interactive session switching in a built image and on hardware is not established. |
| Full-screen chooser, per-user saved choice and one-time switch request | **Implemented, not fully tested** | `system_files/usr/libexec/nebula-os-start`, `nebula-os-chooser`, `nebula-os-switch-side`, and `system_files/usr/lib/nebula-os/nebula/modes.py`. Unit tests include `tests/unit/test_chooser.py::SessionWrapper.test_gaming_mode_that_cannot_start_returns_to_the_chooser`, `test_broken_chooser_falls_back_to_work_mode`, `test_work_mode_gets_gnome_variables`, and `tests/unit/test_mode_scripts.py::Chooser.test_switch_keeps_the_chooser_and_skips_it_once`. The image smoke check verifies files and GDM configuration. A GNOME Boxes test recorded in `CHANGELOG.md` exercised chooser login, failed Gaming start return, and Work startup; it did not verify a successful full Gaming round trip on real hardware. CI boot stops at GDM. |
| Chooser controller navigation, evdev access, InputPlumber virtual-pad access and small-screen layout | **Potentially unsafe / unverified integration** | `system_files/usr/libexec/nebula-os-chooser:57-78` reads input devices; `docs/BACKEND_GAMING_AUDIT.md:102-104` records unresolved normal-seat ACL, virtual-pad and small-display checks. Unit tests do not emulate device ACLs, GDM, or physical screen layout. Requires a built-image login test and device testing. |
| Chooser child-session environment, logind `Desktop`, portal cleanup and user D-Bus restart order | **Potentially unsafe / unverified integration** | Wrapper handoff is in `system_files/usr/libexec/nebula-os-start`; unit coverage is stand-in based (`tests/unit/test_chooser.py::SessionWrapper.test_work_mode_gets_gnome_variables`). `docs/BACKEND_GAMING_AUDIT.md:99-101` names logind metadata, portal/D-Bus ordering, `short_session_recover`, and the base `steamosctl` path as unresolved. Requires booted-image session switching, then hardware confirmation. |
| CLI status and JSON contract | **Implemented + tested** | `system_files/usr/lib/nebula-os/nebula/cli.py:54-75` emits `nebula.status/v1`; hardware and doctor emit `nebula.hardware/v1` and `nebula.doctor/v1`. Unit evidence includes `tests/unit/test_cli.py::WriteReport.test_new_file_is_private` and `tests/unit/test_sysinfo.py::Proc.test_container_traffic_is_counted_once`; image commands are in `tests/image/test-image.sh:52-56`. JSON on `update check` and `update history` is supported; `apply` and `rollback` have no `--json` flag (`cli.py:243-263`). CLI JSON tests do not validate a GUI consumer. |
| Hardware detection and capability reporting | **Implemented + tested** | `system_files/usr/lib/nebula-os/nebula/{gpu,hardware,display,capabilities}.py`; unit evidence includes `tests/unit/test_gpu.py::Detection.test_detects_two_gpus_and_outputs`, `tests/unit/test_display.py::ParseEdid.test_basic_fields`, and `tests/unit/test_capabilities.py::CapabilityLevels.test_to_dict`. Optional graphics probes can wake a sleeping GPU (`cli.py:250-251`). Detection is not a claim of game compatibility. No NebulaOS physical-device matrix currently proves all vendors, hybrid outputs, sleep/resume, controller, or display operation. |
| System Doctor | **Implemented + tested** | `doctor.py:292-317` defines 12 read-only checks and the quick status subset. Tests are in `tests/unit/test_doctor.py`; image smoke invokes `nebula doctor --json`. Checks and their suggested commands are not automatic repairs; they are **unit/image-tested**, not validated against all real failure states on a NebulaOS machine. |
| Deployment/update check, history, apply and rollback CLI | **Implemented, not fully tested** | `system_files/usr/lib/nebula-os/nebula/updates.py` and CLI parser/dispatch in `cli.py:255-316`; unit evidence includes `tests/unit/test_updates.py::Confirmation.test_rollback_confirmed`. Changes hand off to rpm-ostree and its polkit prompt. The documented NebulaOS update/reboot/rollback journey has not been exercised in a NebulaOS VM or on hardware (`README.md`, Update and rollback; `docs/RELEASE_PROCESS.md`). Status does not yet expose every pending/default-deployment recovery state. |
| Bazzite automatic update service and deployment recovery | **Implemented, not fully tested** | The doctor checks `uupd.timer` state (`system_files/usr/lib/nebula-os/nebula/doctor.py:135-158`); update state is parsed in `updates.py`. Service operation and rollback are inherited from Bazzite/bootc and have not been exercised end-to-end on a NebulaOS image (`docs/ARCHITECTURE.md`, Updates and recovery). |
| Nebula `ujust` commands, app setup and Bazzite return recipe | **Implemented + tested at image/config level** | Recipe names and bodies are in `system_files/usr/share/ublue-os/just/60-custom.just:4-144`; `tests/image/test-image.sh:118-122` checks six installed recipe names. The first-boot service and bundle are checked for presence/configuration, but the download/install, signed-update and return-to-Bazzite flows are not end-to-end tested in this audit. |
| Nebula privileged D-Bus API and polkit allowlist | **Planned** | No Nebula system D-Bus service or Nebula polkit action exists in the audited source tree. The design is specified in `docs/ROADMAP.md:43-52`; future privileged actions must use fixed methods and per-action authorization, with the GUI remaining unprivileged. |
| Signed image publish and verification sequence | **Implemented + tested in CI** | `.github/workflows/build.yml:122-124,153-201` builds/tests before publish, signs by digest, verifies, then moves the channel tag. This workflow evidence is not an independent review of the private key or proof of a successful current release. Signed-update enforcement is a separate opt-in recipe (`system_files/usr/share/ublue-os/just/60-custom.just:119-134`). |
| Key custody, signed-update onboarding and recovery | **Potentially unsafe operational dependency** | The signing workflow and policy are in the repository, but private-key custody was not inspected. `docs/ROADMAP.md:19` records the offline backup/rotation task; `SECURITY.md:11-22,28-31` documents signing and recovery. Signed-update enforcement being opt-in means installation and trust setup need explicit, tested guidance. No key material was opened for this audit. |
| Flatpak app bundle, Bazaar row and first-boot installer | **Implemented + tested at image/config level** | `system_files/usr/share/nebula-os/flatpaks.list`, `system_files/usr/libexec/nebula-os-flatpak-setup`, and service unit; `tests/unit/test_doctor.py::Checks.test_flatpak_bundle` and `tests/image/test-image.sh:43-49,108-126` validate list/config and service/recipe presence. They do not prove every app downloads and installs successfully in a clean networked VM. |
| Nebula Control Center / System Doctor GUI | **Planned** | The technical audit explicitly lists the GUI as unavailable (`docs/NEBULAOS_TECHNICAL_AUDIT.md:83`); no GUI module or executable was found under `system_files/`. The current CLI is the backend candidate. |
| Display Lab | **Partial** | `system_files/usr/lib/nebula-os/nebula/display.py` reads EDID, connectors and GNOME/Mutter state; `tests/unit/test_display.py::ParseEdid.test_basic_fields` covers parsing. The guided UI/change/revert workflow is proposed in `docs/ROADMAP.md:59-60`; no Display Lab UI, apply path or timed rollback implementation exists. |
| Gaming Optimizer, per-game profiles, controller center, compatibility helpers and benchmark lab | **Planned** | The technical audit lists these as planned (`docs/NEBULAOS_TECHNICAL_AUDIT.md:98`); detailed proposals are in `docs/ROADMAP.md:60-65`. MangoHud is inherited and a palette preset exists; that is not an optimizer or benchmark implementation. |
| Dev Hub and creative-work profiles | **Planned** | `docs/ROADMAP.md:68-76` describes future Dev Hub and creative profiles; no Nebula Dev Hub/Creative Studio implementation was found. Bazzite DX tools and Bazaar remain inherited. |
| AI tools and AI features | **Missing by design** | `build_files/25-no-ai.sh` removes selected inherited AI tooling; `tests/image/test-image.sh:79-84` checks that selected packages/recipes are absent. Do not add AI tools to the plan’s implementation scope. |

## Test and validation levels

| Level | What the evidence currently means | What it does not mean |
|---|---|---|
| Unit | Python functions and shell wrappers tested with fixtures, temporary trees, or stand-in commands. Current suite has broad module coverage; the latest recorded run before this planning task reported 122 passing tests. | No systemd, real logind, GDM, gamescope, seat ACL, production D-Bus, or device proof. |
| Image smoke | `tests/image/test-image.sh` inspects a built container’s files, configuration, executables and selected CLI JSON. It deliberately runs without systemd or D-Bus. | No boot, sign-in, controller, actual app installation, mode transition, update, rollback, or visual verification. |
| CI VM boot | Manual disk-image workflow calls `tests/vm/ci-boot.sh`, which OCR-checks for the “choose gaming mode” GDM banner (`tests/vm/ci-boot.sh:77-95`; `.github/workflows/build-disk.yml:143-185`). | The workflow does not log in, run the chooser, switch modes, apply an update, or roll back. |
| GNOME Boxes VM | `CHANGELOG.md` records a manual chooser exercise (chooser after login, failed Gaming start returning to chooser, Work Mode start) and ISO install. Treat this as dated historical evidence, not a current run. | No successful Gaming Mode end-to-end round trip or hardware compatibility. |
| Backend on Bazzite hardware | `docs/BACKEND_GAMING_AUDIT.md` records measurements and checks on a Legion 5 running stock Bazzite. It also documents unit-tested fixes C1–C7. | Does not prove the NebulaOS image boots or that its session integration works on that laptop. |
| NebulaOS on real hardware | No successful physical-device validation is recorded. | No statement about hardware support, performance, sleep/resume, controller, external outputs, or safe recovery can be promoted based on the above levels. |

## Technical debt, security risks, testing gaps and documentation inconsistencies

### Technical debt and test gaps

- End-to-end session launch and switch logic is split between GDM session entries, `nebula-os-start`, the chooser, AccountsService state, systemd user environment, Steam hooks, and Bazzite recovery tools. Unit tests cover pieces; the full sequence lacks automated login-and-switch coverage.
- The CI disk workflow reaches GDM only. Add a disposable test account to a throwaway disk artifact before automating login; never bake a test credential into a published image.
- The reference AMD hybrid laptop, NVIDIA, Intel, external outputs, sleep/resume, physical controllers and InputPlumber pads need explicit per-device results. Build success and GPU detection alone are not those results.
- Run the NebulaOS update, reboot, failed deployment, rollback and signed-update recovery path in a VM before treating the user instructions as validated.
- `nebula status` is a monitoring summary, not a complete session/deployment recovery view. Add these fields only with tests for unavailable and unusual rpm-ostree state.
- Display capability parsing exists, but user-controlled mode changes and timed revert need a separate design and failure-safe validation.
- No confirmed broken user-facing feature was established in this source review. “Unverified” is not equivalent to “broken,” and test coverage does not prove behavior outside its level.

### Security risks and guardrails

- Never run the future Control Center as root. Keep normal GTK code in the user session. Route any genuinely privileged operation through a narrow D-Bus API with a polkit action per allow-listed operation; never expose a generic command, shell, arbitrary path, or service-control endpoint.
- Existing `nebula` update changes use rpm-ostree’s authentication path; `nebula doctor` is read-only. Do not make doctor apply suggested commands automatically.
- Session switching and chooser state must remain per-user and reject symlinked state. Existing tests include `tests/unit/test_mode_scripts.py::Chooser.test_refuses_symlinked_state`.
- Never expose private signing material in an image, repository, CI log, generated report, or plan document. Verify signed image identity and key rotation/recovery before enabling enforcement for a release.
- Treat GPU telemetry polling as power-sensitive. `docs/BACKEND_GAMING_AUDIT.md` P6 records that frequent reads can prevent an idle dGPU from suspending; any dashboard must honor autosuspend and back off.
- Do not add hidden telemetry, automatic system changes, AI tools, or undocumented network calls.

### Documentation inconsistencies to keep visible

- `docs/ROADMAP.md` marks Phase 1 as complete while its own checklist still contains uncompleted VM update/rollback, reference hardware, signed-key operations, and end-to-end login tests. Reconcile the phase status with explicit evidence before using it as a release claim.
- Some architecture and roadmap prose describes the intended chooser flow in present tense. The unit and image tests are not an interactive image test; retain the qualification and test level beside such claims.
- Documentation must distinguish the manual `tests/vm/vm.sh` install/boot helper, the CI GDM-only OCR smoke check, the recorded GNOME Boxes exercise, stock-Bazzite backend measurements, and real NebulaOS hardware evidence.
- The “stable” label and a published signed image do not by themselves establish a supported public download/release process or tested rollback journey. Public release status needs a dated exact-image checklist.

## Audit conclusion

The repository currently implements a thin NebulaOS layer over Bazzite: identity, a two-mode login/switching path, the `nebula` CLI and data modules, a small app bundle, and signed image workflow. The strongest tested claims are Python logic and image contents/configuration. The largest release gap is integration evidence: chooser and session transitions in a booted image, update/recovery, and named hardware results. Plan and implement against those evidence gaps before expanding into graphical management or tuning tools.
