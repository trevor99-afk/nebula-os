# Release process

## Channels

| Channel | Tag | Built from | When |
| --- | --- | --- | --- |
| testing | `:testing` | branch `dev` | every push to `dev` |
| stable | `:latest` | branch `main` | every merge to `main`, and daily at 10:05 UTC to pick up Bazzite's updates |

Each build also gets `<channel>-<YYYYMMDD>` and `<channel>-<commit>` tags, so any recent build can be selected exactly (`sudo bootc switch ghcr.io/trevor99-afk/nebula-os:latest-20261121`).

## What CI checks before publishing

1. `checks` job: just syntax, shellcheck, config validation, unit tests, hadolint, actionlint.
2. Build each edition (`nebula-os`, `nebula-os-nvidia`), including `bootc container lint`.
3. **Image tests** (`tests/image/test-image.sh`, 40 checks) inside the built image.
4. Rechunk, push the dated and commit tags, **sign** by digest, **verify** the signature, and only then move the channel tag.

A failure at any step means nothing is published to that channel.

## Promoting testing to stable

1. Merge changes into `dev`; CI publishes `:testing`.
2. Install `:testing` on at least one machine per affected area (both modes, the changed tools) and run the checks below.
3. Open a pull request `dev` → `main`, update `CHANGELOG.md`, and merge when CI is green.

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
