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

## Install from the ISO (one step)

The NebulaOS installer puts NebulaOS on the computer in one go. Bazzite is already inside it (Steam, drivers, Gaming Mode, updates), so you do not install Bazzite first.

**Status:** the ISO boots with UEFI and installs successfully in a virtual machine (tested 2026-11-22). It has not been installed on real hardware yet, so try it in a virtual machine first (GNOME Boxes works; VirtualBox does not install on Bazzite or NebulaOS).

1. Download the ISO: **Actions › Build disk images ›** the newest successful run **› Artifacts › nebula-os-latest-anaconda-iso** (about 7.5 GB; you need to be signed in to GitHub, and artifacts are kept for 7 days). For the NVIDIA edition, run the workflow with the `nebula-os-nvidia` edition.
2. Write it to a USB stick of 16 GB or more (for example with Fedora Media Writer), and boot the computer from it.
3. Choose **Install NebulaOS**. In the installer:
   - **Installation Destination**: pick the disk and press **Done**. **The installer erases the disk you choose**, so back up first. Nothing is written before you press **Begin Installation**.
   - **User Creation**: enter your name, user name and password, keep **administrative privileges** ticked, and press **Done**. This is your account; there is no separate setup after the first boot.
   - **Time & Date**: pick your time zone and press **Done**.
4. When it says **Complete!**, press **Reboot System** and remove the USB stick.
5. Log in with the account you created, and choose your mode on the login screen (see [First boot](#first-boot)).
6. Turn on signature-checked updates once: `ujust nebula-enable-signed-updates`, then restart.

**Secure Boot:** Bazzite's kernel is signed with Universal Blue's key. With Secure Boot on, either turn it off before installing, or after the first boot run `ujust enroll-secure-boot-key`, restart, choose **Enroll MOK**, enter `universalblue`, and turn Secure Boot back on.

## Already running Bazzite: switch

If Bazzite is already installed, you can switch it to NebulaOS instead. Your files, settings and installed apps stay, and the previous system remains in the boot menu.

1. Verify the NebulaOS image signature. Your current system cannot check it yet, so do it yourself, and pin the exact image you verified (its digest), so the image you switch to is the one you checked:

   ```bash
   curl -fsSLO https://raw.githubusercontent.com/trevor99-afk/nebula-os/main/cosign.pub
   IMAGE=ghcr.io/trevor99-afk/nebula-os   # NVIDIA: ghcr.io/trevor99-afk/nebula-os-nvidia
   DIGEST=$(skopeo inspect --format '{{.Digest}}' "docker://$IMAGE:latest")
   cosign verify --key cosign.pub "$IMAGE@$DIGEST"
   ```

   It must print `The signatures were verified against the specified public key`. Do not continue if it doesn't.
2. Switch to exactly that image, then restart:

   ```bash
   sudo bootc switch "$IMAGE@$DIGEST"
   systemctl reboot
   ```

3. Log in, then turn on signature-checked updates and restart once more. This also moves the system from the pinned digest to the `latest` channel, so it keeps updating:

   ```bash
   ujust nebula-enable-signed-updates
   systemctl reboot
   ```

## First boot

- **Choose your mode on the login screen:** select your user, click the gear button at the bottom right, and choose **NebulaOS Gaming Mode** or **NebulaOS Work Mode**. The login screen remembers your last choice. `ujust nebula-mode gaming` or `ujust nebula-mode work` sets it from a terminal.
- **The app bundle installs in the background** over the first minutes: everyday apps first (Firefox, Text Editor, Calculator, Image Viewer, Document Viewer, Flatseal, Extension Manager), then Heroic, Bottles, OBS, Vesktop, MangoJuice, RetroArch, Dolphin and PCSX2. Until Firefox arrives, its dock icon does nothing. Check progress with `ujust nebula-info`.
- **Docker:** administrator accounts are added to the `docker` and `libvirt` groups on first boot. Log out and in once before using `docker` without `sudo`.
- **Check the system:** `nebula doctor` and `nebula hw`.

## Undoing

- Restart and pick the previous entry in the boot menu, or run `sudo bootc rollback` (or `nebula update rollback`) and restart.
- Back to stock Bazzite DX: `ujust nebula-switch-to-bazzite`.
