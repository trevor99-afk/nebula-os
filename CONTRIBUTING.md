# Contributing to NebulaOS

Thanks for helping. NebulaOS is built on Bazzite DX: before adding anything, check whether Bazzite, Bazzite DX or Universal Blue already does it (see the [audit](docs/NEBULAOS_TECHNICAL_AUDIT.md#5-inherit-or-build-the-existing-ecosystem)). Integrate existing tools; build original software only for new capabilities.

## Branches and channels

- `dev`: development. Pushes that change image inputs build and publish the **testing** channel (`:testing`); a manual workflow run on `dev` does too. Docs-only pushes are ignored.
- `main`: stable. Changes arrive only through pull requests from `dev` that pass CI. Image-affecting pushes and manual workflow runs on `main`, plus the daily rebuild, publish `:latest`; docs-only pushes are ignored.

## Working on the project

You need a bootc system (Bazzite works), `just` and `podman`.

```bash
just test          # unit tests for the nebula tools (no root, no network)
just validate      # config files: TOML, Flatpak app IDs, systemd units
just lint          # shellcheck (uses a container if shellcheck is not installed)
just build         # build localhost/nebula-os:latest (NEBULA_PULL=never to skip pulling the base)
just test-image    # run the image tests inside the built image
tests/vm/vm.sh install ~/Downloads/install.iso   # install the ISO in a test VM (KVM, no root)
tests/vm/vm.sh boot                              # boot the installed VM; `tests/vm/vm.sh shot FILE.png` takes a screenshot
```

The container build workflow runs `just check`, `just lint`, `just validate` and `just test`, then builds each edition and runs `just test-image` before publishing. It also runs hadolint and actionlint. The `tests/vm/vm.sh` install and boot commands above are manual; the separate, manually dispatched disk-image workflow boots a qcow2 only as far as the GDM login screen.

To try the backend on your running system without building an image:

```bash
python3 -I -c "import sys; sys.path.insert(0, 'system_files/usr/lib/nebula-os'); from nebula.cli import main; sys.exit(main(sys.argv[1:]))" status
```

## Engineering rules

1. **Real data only.** Never show invented or estimated values. If something cannot be read, report it as unknown.
2. **Capabilities have levels.** Report hardware, driver, available, enabled and verified separately (see `nebula/capabilities.py`). Never claim a feature works because a driver is installed.
3. **No root GUIs.** Front ends run as the user. Privileged work goes through polkit-checked D-Bus calls or a helper with a fixed allow-list of actions.
4. **Confirm before changing the system.** Show what will happen, ask, apply, verify, and keep a way back. Never apply destructive fixes automatically, never delete game files or shader caches, never format disks.
5. **Safe subprocesses.** Use argument lists, never a shell, with timeouts (`nebula.util.run`). Validate all input.
6. **Don't wake sleeping hardware** for monitoring.
7. **Respect the atomic system.** Put files in `/usr` (or `/etc` for configuration). Store user settings in `~/.config/nebula-os/`, never in the image. No hard-coded user paths.
8. **No duplicate of Bazzite features** without a measured benefit.
9. **Tests with every change.** Add unit tests (with fake `/sys`, `/proc` and command output) and image tests for anything that ends up in the image.
10. **Honest docs.** Document only what is implemented, and mark anything untested on real hardware as unverified.

## Reporting hardware

Run `nebula hw --json > hw.json` and attach it to an issue describing what works and what doesn't. The report contains no serial numbers.
