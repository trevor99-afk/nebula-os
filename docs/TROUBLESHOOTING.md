# Troubleshooting

Start with the System Doctor. It only reads and suggests fixes, it never changes anything:

```bash
nebula doctor
nebula doctor --report ~/nebula-report.json                 # to share (no logs)
nebula doctor --report ~/nebula-report.json --include-logs   # with this boot's error log (read it first)
```

## Modes

- **Gaming Mode shows a black screen.** Some dual-GPU PCs have trouble with gamescope. Restart; on the login screen, click the gear button and choose **NebulaOS Work Mode**. Steam works there too. `ujust nebula-mode work` makes Work Mode the default.
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
