# Troubleshooting

Start with the System Doctor. It only reads and suggests fixes, it never changes anything:

```bash
nebula doctor
nebula doctor --report ~/nebula-report.json                 # to share (no logs)
nebula doctor --report ~/nebula-report.json --include-logs   # with this boot's error log (read it first)
```

## Modes

- **The full-screen chooser misbehaves or you want to bypass it.** At the GDM login screen, click the **gear menu** and select **NebulaOS Work Mode** or **NebulaOS Gaming Mode** to start a mode directly. From a working desktop, `ujust nebula-mode chooser-off` turns off the chooser for the next login and starts the last mode selected through the chooser (Work Mode if no choice was saved). To recover from a chooser or Gaming Mode that has taken over the screen, press **Ctrl+Alt+F3**, log in, and run `ujust nebula-mode work now`. This ends the local graphical session and requests Work Mode at the next sign-in. If the chooser is enabled, the next sign-in skips it once and starts Work Mode; run `ujust nebula-mode chooser-off` afterward if you want to bypass the chooser on later logins too. The TTY recovery path is unverified in a built image and on hardware.
- **Gaming Mode shows a black screen.** Some dual-GPU PCs have trouble with gamescope. Either:
  - press Ctrl+Alt+F3, log in, and run `ujust nebula-mode work now`. This closes the stuck Gaming Mode session. Then press Ctrl+Alt+F1 for the login screen and sign in again. If the chooser is enabled, the switcher starts Work Mode once without showing it; the GDM saved session can still be the chooser. Or
  - restart, and on the login screen click the gear button and choose **NebulaOS Work Mode**.
  Steam can also be used from Work Mode. `ujust nebula-mode work` makes Work Mode the direct login choice when the chooser is off. Bazzite's repeated-failure recovery path is not verified with the chooser in a built image.
- **An external monitor stays black in Gaming Mode on a hybrid laptop.** On laptops such as the Legion 5 15ACH6A, the HDMI and DisplayPort outputs belong to the dedicated GPU, while Gaming Mode runs on the GPU that drives the built-in screen. Use Work Mode for external monitors, or the BIOS dedicated-GPU (dGPU-only) mode. This is being investigated: see P1 in [BACKEND_GAMING_AUDIT.md](BACKEND_GAMING_AUDIT.md).
- **Steam's "Switch to Desktop" does nothing.** Use the Power menu to restart and pick Work Mode at the login screen. Then check `journalctl --user -b | grep -iE "session-select|switch-side"` and report it.
- **The login screen doesn't show the mode names.** Check that you are on NebulaOS (`nebula status`). The names come from the image and appear after the first restart into it.

## Apps

- **The bundled apps didn't appear.** They download after the first boot and need internet. Check with `ujust nebula-info`, read the log with `journalctl -b -u nebula-os-flatpak-setup`, or install them now with `ujust nebula-install-apps`.
- **Two copies of VS Code.** If you installed VS Code with Homebrew before switching, remove that copy: `brew uninstall --cask visual-studio-code-linux` (your settings stay).
- **`docker` says permission denied.** Log out and in once after the first boot (the group is added at boot), or run `ujust dx-group`.

## Desktop

- **The NebulaOS wallpaper or dock is missing.** A wallpaper or dock layout you set yourself takes priority. Bazzite's `ujust restore-gnome-de-settings` resets them to Bazzite's values. To get NebulaOS's defaults back, reset those keys: `gsettings reset org.gnome.shell favorite-apps` and `gsettings reset org.gnome.desktop.background picture-uri-dark`.
- **VRR (variable refresh) is off.** `nebula hw` shows whether your display supports it. Turn it on in **Settings › Displays › Refresh Rate**.

## Updates

- **Updating fails with "unauthorized" or "denied".** The image on ghcr.io must be public.
- **"Signature verification failed".** If you turned on signed updates and the signing key changed, run `sudo bootc switch ghcr.io/trevor99-afk/nebula-os:latest` once, restart, then `ujust nebula-enable-signed-updates`.
- **Go back to the previous version:** pick it in the boot menu, or `nebula update rollback` and restart. Bazzite's `ujust rollback-helper` switches to official Bazzite images, not NebulaOS.
- **Running out of disk space:** `flatpak uninstall --unused`, `rpm-ostree cleanup -m`; check `podman system df` before pruning containers.
