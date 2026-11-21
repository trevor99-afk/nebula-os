# Installing NebulaOS

## Requirements

- An x86_64 PC with UEFI, at least 8 GB RAM (16 GB recommended for gaming) and 64 GB of disk space.
- Graphics: AMD (Radeon RX 400 series or newer), Intel (Xe or newer for gaming) or NVIDIA (GTX 16 / RTX 20 series or newer, NVIDIA edition). See [HARDWARE_COMPATIBILITY.md](HARDWARE_COMPATIBILITY.md).
- Internet access during the first boot (the app bundle downloads from Flathub).

## Editions

| Your graphics | Image |
| --- | --- |
| AMD or Intel | `ghcr.io/trevor99-afk/nebula-os:latest` |
| NVIDIA | `ghcr.io/trevor99-afk/nebula-os-nvidia:latest` |

Use `:testing` instead of `:latest` for the testing channel (newer, less tested).

## Recommended: switch from Bazzite

NebulaOS is built on Bazzite DX, so the most reliable install is: install [Bazzite](https://bazzite.gg) with its own installer (it handles disks, Secure Boot and users), then switch the installed system to NebulaOS.

1. Install Bazzite and finish its first-boot setup.
2. Verify the NebulaOS image signature. Your current system cannot check it yet, so do it yourself:

   ```bash
   curl -fsSLO https://raw.githubusercontent.com/trevor99-afk/nebula-os/main/cosign.pub
   cosign verify --key cosign.pub ghcr.io/trevor99-afk/nebula-os:latest
   ```

   It must print `The signatures were verified against the specified public key`. Do not continue if it doesn't.
3. Switch, then restart:

   ```bash
   sudo bootc switch ghcr.io/trevor99-afk/nebula-os:latest
   systemctl reboot
   ```

4. Log in, then turn on signature-checked updates and restart once more:

   ```bash
   ujust nebula-enable-signed-updates
   systemctl reboot
   ```

Your files, settings and installed apps stay. The previous system remains in the boot menu.

## First boot

- **Choose your mode on the login screen:** select your user, click the gear button at the bottom right, and choose **NebulaOS Gaming Mode** or **NebulaOS Work Mode**. The login screen remembers your last choice. `ujust nebula-mode gaming` or `ujust nebula-mode work` sets it from a terminal.
- **The app bundle installs in the background** (Heroic, Bottles, OBS, Vesktop, MangoJuice, RetroArch, Dolphin, PCSX2). Check with `ujust nebula-info`.
- **Docker:** administrator accounts are added to the `docker` and `libvirt` groups on first boot. Log out and in once before using `docker` without `sudo`.
- **Check the system:** `nebula doctor` and `nebula hw`.

## Experimental: installer ISO

The ISO is built on demand (**Actions › Build disk images**) and has **not been tested on real hardware yet**. Test it in a virtual machine first. The installer erases the disk you choose, so back up first.

**Secure Boot:** Bazzite's kernel is signed with Universal Blue's key. With Secure Boot on, either turn it off before installing, or after the first boot run `ujust enroll-secure-boot-key`, restart, choose **Enroll MOK**, enter `universalblue`, and turn Secure Boot back on.

## Undoing

- Restart and pick the previous entry in the boot menu, or run `sudo bootc rollback` (or `nebula update rollback`) and restart.
- Back to stock Bazzite DX: `ujust nebula-switch-to-bazzite`.
