# Gaming on NebulaOS

## Available today

### Choosing a mode

New accounts see a full-screen chooser after login, with Gaming Mode, Work Mode, log out, restart and power off. It highlights the last mode selected through the chooser. Use a mouse, arrow keys and Enter, or a controller's D-pad/left stick and A button. Controller access to evdev devices has not been verified on hardware; see [the gaming audit](BACKEND_GAMING_AUDIT.md#full-screen-chooser-handoff-not-verified-in-a-booted-image).

The login screen's gear menu starts Gaming Mode or Work Mode directly. To turn the chooser on for an account with a saved login mode, run `ujust nebula-mode chooser`; use `ujust nebula-mode chooser-off` to turn it off. `ujust nebula-mode gaming` and `ujust nebula-mode work` select a mode for the next login, or skip the chooser once when it is enabled. Add `now` to end the current graphical session and switch immediately.

### NebulaOS Gaming Mode

Choose **Gaming Mode** in the full-screen menu or **NebulaOS Gaming Mode** from the login screen's gear menu for Steam's full-screen mode (Steam in gamescope, from Bazzite). The Quick Access menu (… button) has per-game performance settings: frame limit, FSR, TDP where supported, and the performance overlay. Steam's **Power › Switch to Desktop** takes you to Work Mode.

If Gaming Mode exits within a minute, the chooser offers Work Mode and explains that Gaming Mode stopped quickly. A very early failure is not proof that Gaming Mode is supported by a particular GPU; NVIDIA startup and the automatic return to the chooser are unverified in a built image and on hardware.

*NebulaOS Gaming Mode (with quick settings overlay)* is Bazzite's variant with the OpenGamepadUI overlay, mainly useful on handhelds.

### In Work Mode

Steam, Lutris, Heroic, Bottles and the emulators all run on the GNOME desktop too. To launch non-Steam games from Gaming Mode, right-click the app (Heroic, RetroArch, Dolphin, PCSX2) in the app grid and choose **Add to Steam**. Heroic can also add individual games from each game's settings.

### Inherited from Bazzite

Steam with Proton, Lutris, ProtonPlus (via Bazzite Portal or `ujust get-protonplus`), Protontricks, Gamescope, MangoHud, vkBasalt, CardWire for hybrid GPUs, InputPlumber for controllers, tuned power profiles, and many fixes (`ujust --choose`: for example `fix-proton-hang`, `setup-decky`).

### Added by NebulaOS

| Feature | How |
| --- | --- |
| Game launchers, streaming, emulators | App bundle: Heroic, Bottles, OBS Studio, Vesktop, MangoJuice, RetroArch, Dolphin, PCSX2 (`ujust nebula-install-apps`) |
| FPS overlay preset | `ujust nebula-fps-overlay on`, then add `mangohud %command%` to a game's Steam launch options. Right Shift + F12 toggles it. |
| Hardware and display capabilities | `nebula hw`: GPU architecture and drivers, Vulkan, OpenGL and video acceleration (verified by probes), each display's mode, refresh range, VRR and HDR |
| Live status | `nebula status`: CPU and GPU usage and temperatures, VRAM, power profile. A sleeping laptop GPU is not woken. |
| Diagnostics | `nebula doctor` checks GPU drivers, firmware, controllers, Bluetooth and audio |

### Getting the best picture

1. Run `nebula hw` and look at your display's **VRR** and **HDR** lines.
2. If VRR shows "available, turned off", turn it on in **Settings › Displays › Refresh Rate**. VRR keeps motion smooth when the frame rate drops below the refresh rate.
3. HDR needs a display that advertises it *and* a desktop mode for it. If both show as available, turn HDR on in Settings › Displays and enable it in the game.

## Planned (not available yet)

The Nebula Gaming Optimizer, Display Lab, Visual Quality Engine, quality profiles and Benchmark Lab are planned, built on the hardware engine above. See [ROADMAP.md](ROADMAP.md#phase-3-gaming-aaa-gaming-and-visual-quality-engine). No performance gains are claimed until they are measured against the same Bazzite version on identical hardware.
