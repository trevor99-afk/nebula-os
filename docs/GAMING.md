# Gaming on NebulaOS

## Available today

### NebulaOS Gaming Mode

Choose **NebulaOS Gaming Mode** on the login screen for Steam's full-screen, controller-friendly Gaming Mode (Steam in gamescope, from Bazzite). The Quick Access menu (… button) has per-game performance settings: frame limit, FSR, TDP where supported, and the performance overlay. Steam's **Power › Switch to Desktop** takes you to Work Mode.

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
