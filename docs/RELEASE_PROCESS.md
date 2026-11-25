# Release process

## Channels

| Channel | Tag | Built from | When |
| --- | --- | --- | --- |
| testing | `:testing` | branch `dev` | image-affecting pushes or a manual workflow run on `dev` |
| stable | `:latest` | branch `main` | image-affecting pushes or a manual workflow run on `main`, and daily at 10:05 UTC to pick up Bazzite's updates |

Pushes that change only Markdown or files under `docs/` are ignored by the container-build workflow. Pull requests to `main` still run checks and image tests, but do not publish.

Each build also gets `<channel>-<YYYYMMDD>` and `<channel>-<YYYYMMDD>-<commit>` tags, so any recent build can be selected exactly (`sudo bootc switch ghcr.io/trevor99-afk/nebula-os:latest-20261121`).

## What CI checks before publishing

1. `checks` job: `just check` (Justfile syntax), shellcheck, config validation, unit tests, hadolint, actionlint.
2. Build each edition (`nebula-os`, `nebula-os-nvidia`), including `bootc container lint`.
3. **Image tests** (`tests/image/test-image.sh`) inside the built image.
4. Rechunk, push the dated and commit tags, **sign** by digest, **verify** the signature, and only then move the channel tag.

A failure at any step means nothing is published to that channel.

## Booting a disk image in CI

The **Build disk images** workflow boots its qcow2 on an Ubuntu GitHub runner with KVM and UEFI, then uses OCR on a GDM screenshot to check for the text “Choose Gaming Mode.” This only verifies that the login screen appeared; it does not log in or exercise either session. A boot failure uploads the screenshot and QEMU logs as a run artifact. Start it from **Actions → Build disk images → Run workflow**; the boot check runs automatically after the disk artifacts are built. It is skipped when uploading directly to S3.

## Updating the Bazzite base

Builds use the reviewed digests in `base-images.lock`, not Bazzite's moving `:stable` tag. Every day `update-base.yml` resolves the newest `:stable` digests, verifies their Universal Blue signatures and, if they changed, opens a pull request to `dev`. It also starts a validation build of that branch (build and image tests, never published), because pull requests opened by the workflow token start no checks by themselves. Review it, check the validation build, and merge to build NebulaOS on the new base; then promote to stable as usual. Scheduled workflows run from the default branch, so the daily check starts once `update-base.yml` is on `main`. The pull request needs the repository setting **Settings › Actions › General › Allow GitHub Actions to create and approve pull requests**. Without it the workflow still verifies the new digests and shows them in its log, so you can update `base-images.lock` by hand.

## Promoting testing to stable

1. Merge changes into `dev`; CI publishes `:testing`.
2. Install `:testing` on at least one machine per affected area (both modes, the changed tools) and run the checks below.
3. Open a pull request `dev` → `main`, update `CHANGELOG.md`, and merge when CI is green.

## Per-release validation checklist

Copy this record into the release pull request or release notes for the exact image being promoted. Record a failure or **Not tested** where a step cannot be completed; a Bazzite result is not evidence for NebulaOS.

```text
Release/tag:
Edition and image reference:
Image digest (sha256):
Test date:
Test target: VM or physical hardware
VM configuration or hardware model:
CI run, logs, or test report:
```

- [ ] Verify the image signature for the recorded digest.
- [ ] Boot that exact digest and record the boot result.
- [ ] Log in and record Work Mode and Gaming Mode startup results.
- [ ] Switch Work → Gaming → Work and record both results.
- [ ] Stage an update, restart, and record which deployment boots.
- [ ] Roll back, restart, and record that the previous deployment boots and the newer deployment remains available.

Use the [update and rollback procedure](#verifying-updates-and-rollback) for the commands and expected deployment behavior. Do not mark an unperformed step as passed.

## Verifying updates and rollback

Run this in a VM, and on real hardware for releases that touch boot, drivers or modes. Record the results in the pull request.

1. Start from Bazzite DX. `sudo bootc switch ghcr.io/trevor99-afk/nebula-os:testing`, then restart. Confirm `nebula status` shows NebulaOS and the login screen offers both modes.
2. `ujust nebula-enable-signed-updates`, then restart. Confirm `nebula update history` shows `[signed]`.
3. Publish a newer build. `nebula update check` should report it available. `nebula update apply`, then restart. Confirm the new version.
4. `nebula update rollback`, then restart. Confirm the previous version boots, with the newer one still in the menu.
5. `nebula doctor`: no failures.
6. Switch modes both ways: dock **Switch to Gaming Mode**, and Steam **Switch to Desktop**.

## Signing key

See [SECURITY.md](../SECURITY.md#for-maintainers-the-signing-key).
