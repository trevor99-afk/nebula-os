# Implementation milestones

These milestones are a proposal for later owner review. They do not authorize or record implementation. Each milestone should land separately with tests, documentation and a release to `testing` before promotion to `stable`. Keep the Bazzite DX base, existing CLI and JSON contracts, and the no-AI policy.

## Phase 1 — Foundation and reliability

### 1.1 Establish the evidence baseline

- **Objective:** Make every current claim traceable to a precise source, test level, image version and date.
- **Scope:** Reconcile the feature audit and hardware matrix; publish precise meanings for unit, image smoke, CI GDM boot, manual VM, backend-on-Bazzite and NebulaOS hardware evidence. Record known unverified chooser and recovery paths.
- **Likely files:** `docs/plan/01-AUDIT.md`, `docs/HARDWARE_COMPATIBILITY.md`, `docs/BACKEND_GAMING_AUDIT.md`, `docs/RELEASE_PROCESS.md`, `CHANGELOG.md`.
- **Dependencies:** Owner review of the plan; current exact source/image identifiers.
- **Implementation details:** Use per-device rows for boot, GNOME login, Gaming start, mode switching, controller, outputs, sleep/resume and updates. Keep “not tested” distinct from “failed.” Include image digest and test date for each positive result.
- **Security considerations:** Do not publish private key material, account credentials, unredacted logs, or reports containing user/device/network identifiers without review.
- **Tests/evidence:** Markdown link/content checks; compare command and path names to source; attach existing unit/image/VM/hardware evidence without relabeling its level.
- **Acceptance criteria:** Every public compatibility claim names its test level and target; unsupported rows are marked explicitly; no claim says a unit test proves hardware compatibility.
- **Rollback strategy:** Revert the documentation change as a unit; preserve the previous dated evidence in version history.

### 1.2 Add an interactive chooser VM journey

- **Objective:** Test the chooser and session handoffs beyond the current CI GDM banner check.
- **Scope:** Extend a throwaway qcow2 test artifact with a disposable non-privileged user, boot it under QEMU/UEFI, log in, detect the chooser, exercise Work and Gaming launch/return where QEMU supports it, and capture diagnostics. Keep the fast existing CI smoke path.
- **Likely files:** `.github/workflows/build-disk.yml`, `tests/vm/ci-boot.sh`, `tests/vm/vm.sh`, `tests/vm/` helper scripts, `docs/DEVELOPMENT.md`, `docs/RELEASE_PROCESS.md`.
- **Dependencies:** A stable QEMU/KVM runner; tested account provisioning isolated to a disposable disk copy; a reliable graphical automation mechanism; 1.1 evidence vocabulary.
- **Implementation details:** Create the account only after building/downloading the image and only in a throwaway overlay/copy; generate the password or login secret at runtime; never publish it, write it to the source tree or cache it with artifacts. Use QMP or another supported mechanism. Add timeouts and upload only scrubbed failure diagnostics. The current CI boot test reaches GDM and does not log in.
- **Security considerations:** A test credential must never enter the image, published qcow2, workflow log, repository or reusable artifact. Limit workflow permissions and retention. Do not expose the VM’s display or QMP socket to an untrusted network.
- **Tests/evidence:** ShellCheck changed shell scripts; run existing image smoke checks, Python unit/config suites, `shellcheck tests/vm/ci-boot.sh` and the full manual VM flow before enabling it in CI. Record where gamescope behavior cannot be emulated and keep hardware tests separate.
- **Acceptance criteria:** CI still detects GDM; an isolated test run signs in as a non-root user, reaches the chooser, exercises both reachable session paths and returns to GDM without an unbounded restart loop; no credential is visible in logs/artifacts; failure output is actionable.
- **Rollback strategy:** Keep the current GDM-only workflow job unchanged as a fallback; gate the interactive subtest behind a workflow input until reliable; revert the added VM helper/workflow without changing the image.

### 1.3 Validate the reference hardware and controller/display path

- **Objective:** Establish a reproducible physical-device baseline on the declared AMD hybrid Legion before changing gaming defaults.
- **Scope:** Exact image boot/install, login, Work and Gaming start and return, internal/external output, GPU selection, controller/virtual-pad input, suspend/resume and idle dGPU behavior.
- **Likely files:** `docs/HARDWARE_COMPATIBILITY.md`, `docs/BACKEND_GAMING_AUDIT.md`, `docs/RELEASE_PROCESS.md`, issue/report templates; code only if a reproduced defect is found.
- **Dependencies:** Access to the device and safe recovery media; 1.1 test matrix; preferably 1.2 VM path for pre-hardware regressions.
- **Implementation details:** Record BIOS/display mode, exact image digest, kernel/base identity, connection topology, test commands and outcomes. Test physical event-device access as a normal user and InputPlumber virtual pads if present. Test external ports individually; do not infer from EDID or GPU enumeration.
- **Security considerations:** Keep test accounts and logs private; redact serial numbers, usernames, network names and tokens. No broad udev permission change without a least-privilege review.
- **Tests/evidence:** Named device test report; rerun all required unit/config/image tests if code changes. Successful boot, successful Gaming session and successful external display are separate recorded results.
- **Acceptance criteria:** A dated matrix exists for each required path, including failures/unavailable tests and recovery outcomes; no support claim exceeds measured evidence; chooser integration risks are closed or documented with a safe workaround.
- **Rollback strategy:** Keep a known-good Bazzite deployment and bootable recovery path; revert only the Nebula-specific change that caused a regression; restore default graphics/session configuration before further testing.

### 1.4 Validate update, signature and rollback recovery

- **Objective:** Prove the update lifecycle for an exact NebulaOS image, including signed-update enforcement and a return to a known deployment.
- **Scope:** Remote check, stage update, reboot, verify new deployment, simulate or select recovery, rollback, reboot, and confirm previous deployment. Validate both opted-in signed enforcement and the documented recovery if the image/key identity is unavailable.
- **Likely files:** `tests/unit/test_updates.py`, `tests/image/test-image.sh`, `tests/vm/`, `.github/workflows/`, `docs/INSTALLATION.md`, `docs/RELEASE_PROCESS.md`, `docs/SECURITY.md`.
- **Dependencies:** Published test images signed by the configured CI identity, VM snapshots, recovery checklist, 1.1 and preferably 1.2.
- **Implementation details:** Run against a disposable VM first. Record source/target digest, signature verification result, deployment state before/after, required reboot and rollback outcome. Add unit cases for new state parsing before changing CLI fields. Never test with production key material copied to a VM.
- **Security considerations:** Never print/copy private keys. Verify the expected public identity and registry before enabling enforcement. Protect CI signing secret, pin workflow actions, avoid leaking registry credentials, and require human confirmation for destructive recovery steps.
- **Tests/evidence:** Existing `tests/unit/test_updates.py`; image policy assertions; VM journey; then reference-device confirmation when safe. Preserve JSON schemas and exit codes.
- **Acceptance criteria:** A fresh test image can check, stage, reboot, and report the expected deployment; the recovery path returns to a bootable prior image; signed enforcement rejects an untrusted image and accepts the expected signed image; exact evidence is published.
- **Rollback strategy:** Use the VM boot menu or `rpm-ostree rollback`/bootc-supported recovery documented for that image. Keep an un-enforced test deployment available until enforcement recovery is proven; revert only test workflow/docs changes if the journey is unreliable.

### 1.5 Close the CLI/status evidence gap

- **Objective:** Make status useful for recovery without breaking existing command or JSON consumers.
- **Scope:** Evaluate current session, booted and pending deployment, reboot-required state and concise recovery advice; add only fields with reliable data sources.
- **Likely files:** `system_files/usr/lib/nebula-os/nebula/cli.py`, `updates.py`, `modes.py`, `doctor.py`, `tests/unit/test_cli.py`, `test_updates.py`, `test_mode_scripts.py`, `tests/image/test-image.sh`, `docs/ARCHITECTURE.md`, `README.md`.
- **Dependencies:** 1.4 observations; approved JSON contract/version strategy; source availability across Bazzite versions.
- **Implementation details:** Treat missing commands, malformed JSON and unknown session values as unknown rather than guessing. Add fields compatibly to `nebula.status/v1` only if current consumers tolerate additions; otherwise introduce a documented schema version with migration notes. Do not make `nebula status` probe a sleeping GPU.
- **Security considerations:** Keep it read-only; do not execute recovery suggestions automatically; do not report secrets or full environment values.
- **Tests/evidence:** Unit fixtures for booted/staged/rollback-pending, no rpm-ostree, malformed data and unknown mode; CLI JSON contract tests; image JSON check; VM confirmation against real rpm-ostree output.
- **Acceptance criteria:** Existing commands, flags, exit codes and current required fields remain; new values are evidence-based and null/unknown when unavailable; tests prove no mutation and no extra GPU wakeup.
- **Rollback strategy:** Remove or disable new fields if output misreports deployment state; keep old schema fields and command behavior; revert the status-only change independently.

## Phase 2 — Control Center

### 2.1 Freeze the shared read-only backend contract

- **Objective:** Let a user-session UI consume the same tested values as `nebula` without forking system inspection logic.
- **Scope:** Define a small internal Python API or structured CLI adapter for status, hardware, doctor and deployment reads; document refresh and unknown-value behavior. Do not add privileged actions in this milestone.
- **Likely files:** `system_files/usr/lib/nebula-os/nebula/`, `system_files/usr/bin/nebula`, `tests/unit/test_cli.py`, `test_sysinfo.py`, `test_gpu.py`, `test_display.py`, `test_doctor.py`, `test_updates.py`, `docs/plan/02-ARCHITECTURE.md`, `docs/ARCHITECTURE.md`.
- **Dependencies:** Phase 1.5 contract decision and evidence; confirmed GTK4/PyGObject versions in the actual base image.
- **Implementation details:** Prefer importing read-only data functions from the Python package rather than scraping translated terminal text. Keep JSON output for automation and compatibility. Bound refresh frequency; avoid GPU probes in a live dashboard and back off when dGPU metrics are unavailable or the device is suspended.
- **Security considerations:** Read as the logged-in user; filter logs and device identifiers before export; no shell interpolation or arbitrary file reads.
- **Tests/evidence:** Unit tests against fake sysfs/proc/systemd data; JSON contract tests; actual-base-image import/UI smoke check. Measure that polling does not hold a sleeping GPU awake.
- **Acceptance criteria:** CLI output remains compatible; UI/backend handles `None`, missing devices and command errors; all data reads are unprivileged and no faster than the approved polling budget.
- **Rollback strategy:** Keep the CLI as the sole interface; remove the adapter or dashboard polling without changing core commands.

### 2.2 Build the read-only Control Center shell

- **Objective:** Deliver a useful native overview and System Doctor GUI without expanding privilege.
- **Scope:** Python GTK4/libadwaita user-session application with Overview, Hardware/Capabilities and Doctor pages; display update state and safe links to Bazaar, Bazzite Portal and documented commands. No fixes applied automatically.
- **Likely files:** New `system_files/usr/lib/nebula-os/` UI package, desktop entry and icon under `system_files/usr/share/applications/` and `system_files/usr/share/icons/`, package/build setup in `build_files/20-packages.sh` only if the base lacks a required runtime, `tests/unit/`, `tests/image/test-image.sh`, docs.
- **Dependencies:** 2.1; actual base package/runtime availability; UX/accessibility review.
- **Implementation details:** Use the system palette and libadwaita conventions; accessible focus order, keyboard navigation and scalable layout; one-shot metrics and measured refresh. Show capability evidence and distinguish installed/available/enabled/verified. Doctor buttons may copy/show a suggested command but cannot silently run it.
- **Security considerations:** The app must run as the current user and must never be launched as root. Do not introduce a background daemon just to serve read-only values. Log export is opt-in and reviewable.
- **Tests/evidence:** Python unit tests for page models/data handling; image checks for executable/desktop file; screenshot/launch smoke in a VM and accessibility check; compare figures against `nebula --json` output.
- **Acceptance criteria:** Clean install launches the GUI; all read-only pages handle unavailable values; no root permission, daemon, hidden network request or automatic repair is added; keyboard navigation works at desktop and small-window sizes.
- **Rollback strategy:** Remove the app/desktop entry or disable its launcher; retain CLI and Doctor as fallback; no schema or image-base changes required to keep the OS usable.

### 2.3 Add only explicit privileged actions

- **Objective:** Provide narrowly scoped administrative actions without granting the UI or a generic helper root execution.
- **Scope:** Threat-model and implement only approved actions such as update apply/rollback or a specifically justified system action. Session selection that can use AccountsService as the current user should remain unprivileged.
- **Likely files:** New D-Bus service/interface and systemd unit under `system_files/usr/share/dbus-1/` and `system_files/usr/lib/systemd/system/`; polkit action/policy under `system_files/usr/share/polkit-1/actions/`; allow-list implementation and tests; image tests; security/architecture docs.
- **Dependencies:** 2.1 and 2.2; named actions and owner-approved threat model; actual Bazzite polkit/D-Bus packaging and policy verified in the image.
- **Implementation details:** Define fixed D-Bus methods with typed, validated arguments. Each method maps to one operation and performs its own authorization check; no generic command, `exec`, arbitrary path, unit name or environment input. Reuse underlying rpm-ostree/systemd APIs. Decide whether existing rpm-ostree polkit flows are sufficient before introducing a second service. Return structured result/error codes to the user UI.
- **Security considerations:** GUI stays unprivileged. Enforce polkit for each action, least-privilege subject/action, input validation and safe error handling. A caller cannot bypass policy by calling the service directly. Review SELinux labels, D-Bus activation and policy defaults. No `pkexec` root GUI.
- **Tests/evidence:** Unit tests for allowlist/argument rejection; D-Bus integration tests as normal and unauthorized users; polkit denial test; image checks for policy and service; VM test of approved action plus cancellation/rollback. Security review before enabling by default.
- **Acceptance criteria:** Unlisted operations are impossible; unauthorized callers receive denial; cancellation changes nothing; authorized actions are auditable and return a safe result; no GUI process has effective UID 0.
- **Rollback strategy:** Disable the D-Bus service and UI action; keep user CLI and rpm-ostree’s existing authorization path; preserve the last bootable deployment. Remove overly broad policy immediately if any allowlist test fails.

### 2.4 Validate Control Center on the supported base and VM

- **Objective:** Prove the UI and authorization behavior against the exact image stack rather than mocks alone.
- **Scope:** Build image, launch app as a standard user, compare dashboard data to CLI, exercise Doctor exports and each approved privileged action, test monitor/small-window behavior and session recovery.
- **Likely files:** `.github/workflows/build.yml`, `.github/workflows/build-disk.yml`, `tests/image/`, `tests/vm/`, `docs/DEVELOPMENT.md`, `docs/RELEASE_PROCESS.md`, device matrix.
- **Dependencies:** 2.1–2.3 complete; VM login journey; test action policy.
- **Implementation details:** Keep read-only image smoke checks for fast CI. Add VM GUI flow separately and use test-only account provisioning in a throwaway artifact. Capture screenshots and diagnostics without credentials or unrestricted logs.
- **Security considerations:** No test user in the image; no remote display/QMP exposure; only minimal workflow permissions; no logs with credentials or signing data.
- **Tests/evidence:** Unit/config/image suites; actual-base VM launch and UI automation; D-Bus/polkit tests; manual GNOME Boxes confirmation. Hardware-specific display and controller behavior stays a separate matrix entry.
- **Acceptance criteria:** UI opens and remains usable after mode changes; data agrees with CLI; privileged actions allow/deny correctly; no automatic changes; diagnostics preserve privacy; all feature claims name the tested image and VM level.
- **Rollback strategy:** Keep a CLI-only mode and hide/disable the GUI launcher if runtime or authorization is unstable; revert the UI/DBus package independently from the base image; use bootc/rpm-ostree previous deployment for image-level recovery.

## Later work, gated by evidence

Display Lab, Gaming Optimizer, per-game profiles, controller center, benchmark lab, Dev Hub, creative profiles and Plymouth branding follow after Phase 1 and the read-only Control Center are stable. Each needs its own threat/failure analysis, per-device test plan, user confirmation and rollback. No tuning or display change should be scheduled merely because another distribution implements a similar feature.
