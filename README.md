<p align="center">
  <img src="system_files/usr/share/icons/hicolor/scalable/apps/nebula-os-logo.svg" width="128" alt="NebulaOS logo">
</p>

# NebulaOS

A Linux distribution with two sides: one for **gaming**, one for **development and work**.

NebulaOS is built on [Bazzite DX](https://dev.bazzite.gg), so it keeps everything Bazzite provides (Steam, Proton, Gamescope, MangoHud, a gaming-tuned kernel, fresh graphics drivers, automatic updates and one-step rollback) and adds its own identity, apps and tools.

## The two sides

| | Gaming side | Work side |
| --- | --- | --- |
| What it is | **Steam Gaming Mode**: full-screen Steam, made for controllers, like a Steam Deck or console | **GNOME desktop** for coding and everyday work |
| Apps | Steam library, plus Heroic, Bottles, RetroArch, Dolphin and PCSX2 once added to Steam | VS Code, Docker (with Compose and Buildx), Podman, Distrobox, Homebrew, virtual machines (virt-manager), Android tools |
| App store | Steam store | **Bazaar**, with a NebulaOS "Development & Work" section |
| Switch to the other side | Steam menu › Power › **Switch to Desktop** | **Switch to Gaming Mode** in the dock |

Both sides start from the login screen and need your password. The login screen remembers the side you used last; choose the other one with the gear button next to **Sign In**, or run `ujust nebula-side gaming` (or `work`).

Also included on both sides:

- **NebulaOS identity**: its name in the boot menu, Settings › About and the terminal welcome message, plus its own logo and wallpapers.
- **App bundle** (installed from Flathub after the first boot, a few gigabytes): Heroic Games Launcher, Bottles, OBS Studio, Vesktop (Discord), MangoJuice (FPS overlay settings), RetroArch, Dolphin and PCSX2.
- **FPS overlay preset**: `ujust nebula-fps-overlay on`.
- **Signed updates**: every published build is signed with your key, and systems can refuse anything you didn't sign.

## How it works

NebulaOS is an *image-based* (atomic) OS: the whole system is one container image. The `Containerfile` starts from Bazzite DX's image and runs the scripts in `build_files/`. The result is installed as a single unit, and the previous version is kept, so a bad update is undone with one reboot.

```
Bazzite DX image ─► Containerfile + build_files/ + system_files/ ─► NebulaOS image
                                                                        │
                  GitHub Actions builds and signs it every day ─► ghcr.io ─► your PCs update from there
```

## Install it on a computer running Bazzite (or another bootc system)

```bash
sudo bootc switch ghcr.io/trevor99-afk/nebula-os:latest
systemctl reboot
# after the reboot: only accept builds signed with the project's key
ujust nebula-enable-signed-updates
systemctl reboot
```

Your files, settings and apps stay; only the operating system changes. To go back, pick the previous entry in the boot menu, or run `sudo bootc rollback` and reboot. `ujust nebula-switch-to-bazzite` returns to stock Bazzite DX.

If you installed VS Code with Homebrew before, remove that copy so you don't have two: `brew uninstall --cask visual-studio-code-linux` (your settings and extensions stay).

**Docker:** on first boot, administrator accounts are added to the `docker` and `libvirt` groups automatically. Log out and back in (or reboot) once before using `docker` without `sudo`.

## Build and test locally

You need about 30 GB of free disk space. The first build downloads Bazzite DX (about 7 GB).

```bash
cd ~/Projects/nebula-os
just build              # builds localhost/nebula-os:latest
just switch-local       # switch this computer to it (asks for your password), then reboot
```

Optionally test it in a virtual machine first: `just build-qcow2`, then `just run-vm`.

## Publishing (GitHub)

1. A public GitHub repository named `nebula-os`, with your username in `REPO_ORGANIZATION` in `image-template.env`.
2. The repository secret `SIGNING_SECRET` contains `cosign.key` (the private signing key, ignored by git). Never commit or share `cosign.key`; keep a backup somewhere safe, such as a password manager.
3. Every push to `main`, and a daily scheduled run, builds, signs and publishes `ghcr.io/<github-user>/nebula-os`. Watch it in the repository's **Actions** tab (about 20 minutes).
4. First time only: make the image public. On GitHub, open your profile › **Packages** › `nebula-os` › **Package settings** › **Change visibility** › **Public**.

### Installer ISO

On GitHub, open **Actions › Build disk images › Run workflow**, then download `nebula-os-anaconda-iso` from the run's **Artifacts**. Bazzite DX itself is normally installed by switching from Bazzite rather than from an ISO, so the simplest route for a new PC is: install [Bazzite](https://bazzite.gg), then run the `bootc switch` command above.

**Secure Boot:** Bazzite's kernel is signed with Universal Blue's key. On a PC with Secure Boot on, turn it off before installing; after the first boot run `ujust enroll-secure-boot-key`, reboot, choose **Enroll MOK**, enter `universalblue`, and turn Secure Boot back on.

## Everyday commands

NebulaOS adds these to Bazzite's `ujust` menu (run `ujust` to see everything):

| Command | What it does |
| --- | --- |
| `ujust nebula-side gaming` / `work` | Choose the side to start at the next login (add `now` to switch right away) |
| `ujust nebula-info` | Version, update source, and which bundled apps are installed |
| `ujust nebula-install-apps` | Install the app bundle now (also restores bundled apps you removed) |
| `ujust nebula-fps-overlay on` | Install the FPS overlay preset (`off` and `status` work too) |
| `ujust nebula-enable-signed-updates` | Only accept updates signed with your key |
| `ujust nebula-switch-to-bazzite` | Go back to stock Bazzite DX |

**Games from other launchers in Gaming Mode:** on the work side, right-click an app (Heroic, RetroArch, Dolphin, PCSX2) in the app grid and choose **Add to Steam**. Heroic can also add individual games to Steam from each game's settings.

**FPS overlay:** after `ujust nebula-fps-overlay on`, add `mangohud %command%` to a Steam game's Launch Options (right-click the game › Properties). Press Right Shift + F12 in game to show or hide it. In Gaming Mode, Steam's own performance overlay is in the Quick Access menu.

**Updates** download automatically in the background and apply on the next reboot. Run `ujust update` to update right away.

## Customize

| To change | Edit |
| --- | --- |
| Name, GitHub account, base image | `image-template.env` |
| Bundled apps (Flatpaks) | `system_files/usr/share/nebula-os/flatpaks.list` |
| Bazaar's Development & Work section | `build_files/bazaar-dev-work.yaml` |
| Extra system packages (RPMs) | `build_files/20-packages.sh` |
| Dock apps and wallpaper defaults | `system_files/usr/share/glib-2.0/schemas/zz1-nebula-os.gschema.override` |
| Wallpapers, logo | `system_files/usr/share/backgrounds/nebula-os/`, `system_files/usr/share/icons/hicolor/scalable/apps/` |
| Your own `ujust` commands | `system_files/usr/share/ublue-os/just/60-custom.just` |
| Any other file in the OS | Add it under `system_files/` (copied to `/` in the image) |

Put files under `/usr` (programs and data) or `/etc` (configuration). Files placed in `/var` or `/home` in the image are not updated on installed systems. After a change, commit and push: GitHub builds the new version and your computers pick it up with their next update.

### Editions

Change `BASE_IMAGE` in `image-template.env`:

| Edition | `BASE_IMAGE` |
| --- | --- |
| Two sides, AMD or Intel graphics (default) | `ghcr.io/ublue-os/bazzite-dx-gnome:stable` |
| Two sides, NVIDIA graphics | `ghcr.io/ublue-os/bazzite-dx-nvidia-gnome:stable` |
| Desktop only (no Gaming Mode, no developer tools) | `ghcr.io/ublue-os/bazzite-gnome:stable` |

## Project layout

```
Containerfile            the recipe: Bazzite DX + build_files/
image-template.env       settings: name, GitHub account, base image
Justfile                 build, test and install commands (run `just` to list them)
build_files/
  build.sh               copies system_files/ and runs the numbered steps
  10-branding.sh         name, boot menu entry, hostname, welcome message
  15-bazaar.sh           adds the Development & Work section to Bazaar
  20-packages.sh         extra RPM packages
  30-services.sh         turns on NebulaOS services
  40-signing.sh          signature policy for your images
  90-finalize.sh         rebuilds the settings and icon caches
system_files/            copied into the image as-is (side switcher, app bundle, artwork, ujust commands)
disk_config/             ISO and virtual machine disk settings
.github/workflows/       daily build and sign; ISO and VM images
cosign.pub               public signing key (cosign.key is private and git-ignored)
```

## Troubleshooting

- **Gaming Mode shows a black screen.** Some PCs with two graphics chips have trouble with Gaming Mode. Reboot, choose the GNOME session with the gear button on the login screen, and play from the desktop Steam app. `ujust nebula-side work` makes the desktop the default again.
- **"Switch to Desktop" does nothing in Gaming Mode.** Restart from Steam's Power menu and pick the GNOME session on the login screen. Then `journalctl --user -b | grep -i session-select` shows what went wrong.
- **The bundled apps didn't appear.** They download in the background after the first boot and need internet. Check with `ujust nebula-info`, read the log with `journalctl -u nebula-os-flatpak-setup`, or install them now with `ujust nebula-install-apps`.
- **Switching or updating fails with "unauthorized" or "denied".** The package on ghcr.io is still private; make it public (Publishing, step 4).
- **"Sign container image" fails on GitHub.** The `SIGNING_SECRET` secret is missing or doesn't match `cosign.pub`.
- **Bazzite's `ujust rollback-helper`** switches to official Bazzite images, not NebulaOS. To undo a NebulaOS update, use the boot menu or `sudo bootc rollback`.

## Credits

Built with Universal Blue's [image-template](https://github.com/ublue-os/image-template) on top of [Bazzite DX](https://dev.bazzite.gg). NebulaOS is not affiliated with Bazzite or Universal Blue. Licensed under Apache-2.0.
