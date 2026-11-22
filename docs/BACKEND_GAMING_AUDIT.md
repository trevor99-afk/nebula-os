# NebulaOS backend and Gaming Mode audit

Date: 2026-11-22 · Scope: commit `80c72b2` (v0.2.0): the `nebula` backend (`system_files/usr/lib/nebula-os/nebula/`), mode switching (`nebula-os-switch-side`, `nebula-os-steamosctl`, `/usr/lib/os-session-select`, `build_files/35-modes.sh`), and the Bazzite Gaming Mode components they rely on (`gamescope-session-plus`, `steamos-session-select`, GDM, AccountsService).

Primary hardware target: Lenovo Legion 5 15ACH6A (Ryzen 7 5800H, Radeon Vega iGPU, Radeon RX 6600M 8 GB, 16 GB RAM, 1920x1080 at 165 Hz). Every hardware measurement below was taken on that machine, which runs stock Bazzite GNOME. Checks of the image were made inside `localhost/nebula-os:latest`.

## How it was done

- I read the code line by line, and compared it with the kernel's sysfs and hwmon interfaces and with Bazzite's own session scripts in the image.
- I measured on the target machine. Wake-ups of the dGPU were read from `/sys/bus/pci/devices/0000:03:00.0/power/runtime_active_time`. Sensor values were compared with `sensors` and with raw sysfs reads.
- Mode switching was exercised with stand-in (stub) commands for `busctl`, `loginctl` and `pgrep`. The full switch inside a real session (GDM, gamescope, Steam) needs a running NebulaOS system, which this audit did not have. It is listed under [Not verified](#not-verified).

**Confirmed** means reproduced by a measurement or a test that fails on the old code. **Potential** means found by reading, or depends on hardware or situations not available here.

## Target hardware facts that matter

| GPU | PCI | Outputs | Notes |
| --- | --- | --- | --- |
| RX 6600M (Navi 23), `card1` | 0000:03:00.0 | HDMI-A-1, DP-1, DP-2, eDP-1 | `boot_vga=0`, runtime PM with 5000 ms autosuspend, asleep (D3cold) when idle |
| Vega (Cezanne), `card2` | 0000:07:00.0 | eDP-2 (the internal panel in hybrid mode) | `boot_vga=1`, has the APU-only `vddnb` hwmon sensor |

Every external port (HDMI and DisplayPort) is wired to the dGPU. In hybrid mode, the internal panel runs on the iGPU.

## Confirmed bugs

| # | Severity | Where | Problem | Root cause | Evidence |
| --- | --- | --- | --- | --- | --- |
| C1 | High | `nebula/gpu.py:314-327` (`lspci_names`), called from `detect_gpus` at `gpu.py:336` | `nebula status`, `nebula hw --no-probe` and `nebula doctor` wake the sleeping dGPU every time. The module docstring promises the opposite. A monitor that polls them keeps the dGPU on and drains the battery. | `lspci -mm -D` reads the PCI configuration space of every device. For a device in D3cold, the kernel resumes it first (`pci_config_pm_runtime_get`). | dGPU awake for 1335 ms (`status`), 758 ms (`hw --no-probe`) and 882 ms (`doctor`). `lspci -mm -D` alone: 679 ms, and `cat .../config`: 666 ms. With `lspci_names` stubbed, all three commands: 0 ms. |
| C2 | High | `system_files/usr/libexec/nebula-os-switch-side:47-56` | Recovery from a text console does not work. If Gaming Mode hangs (black screen, Steam not running), `ujust nebula-mode work now` on Ctrl+Alt+F3 logs out of the console, and the hung graphical session keeps running. | Outside GNOME and without Steam, the script terminates `$XDG_SESSION_ID`, which is the console's own session, not the graphical one. | Stubs, run with `XDG_SESSION_ID=c7 XDG_SESSION_TYPE=tty`: the script runs `loginctl terminate-session c7`. |
| C3 | Medium | `nebula/gpu.py:190-193` (`AmdBackend.metrics`) | On an AMD APU, the iGPU's reported "GPU power" is the power of the whole processor package (CPU plus GPU). An idle Vega iGPU showed 21 W. | amdgpu's `power1` sensor on APUs is PPT (package power), not GPU power. | Target machine: `card2` `power1_label=PPT` and `power1_input=19000000` while the GPU was idle. The APU-only `in1_label=vddnb` is present on `card2` only. |
| C4 | Low | `nebula/gpu.py:192` | A valid power reading of 0 W is reported as unknown. | `read_int(power1_average) or read_int(power1_input)` treats 0 as missing. | Unit test. |
| C5 | Low | `nebula/gpu.py:466-471` (`enrich`) | With two identical GPUs, both are matched to the first Vulkan device, so the second one gets the first one's Vulkan results. | Matching uses only vendor and device ID, and a matched device is not taken out of the list. | Unit test with two identical GPUs. |
| C6 | Low | `nebula/sysinfo.py:283-285` | On CPUs with a temperature offset (Ryzen 1000/2000 "X" models, Threadripper), the reported CPU temperature is Tctl, up to 27 °C above the real die temperature. Not affected: the 5800H. | `Tctl` is preferred over `Tdie`. k10temp only exposes `Tdie` when an offset applies, and then `Tdie` is the real temperature. | Unit test with a k10temp tree that has both labels. |
| C7 | Low | `nebula/sysinfo.py:266-277` (`net_rates`) | The total network rate counts container and VM traffic several times (veth, bridge, then the physical interface). | All non-loopback interfaces are added up. | Unit test with `docker0`/veth counters. |

## Potential problems (not reproduced here)

| # | Area | Problem | Why it is likely | Proposed handling |
| --- | --- | --- | --- | --- |
| P1 | Gaming Mode, external displays (target hardware) | In hybrid mode, an external display on HDMI or DisplayPort probably stays black in Gaming Mode. | gamescope drives one GPU. Without `VULKAN_ADAPTER` (Bazzite's `device-quirks` sets it for three other models only), it uses the `boot_vga` GPU, which is the iGPU. All external ports belong to the dGPU. Work Mode (Mutter) drives outputs on both GPUs. | Test on the laptop first. If confirmed, start Gaming Mode on the dGPU when a display is connected to it (`VULKAN_ADAPTER`/`--prefer-vk-device` set from `/etc/gamescope-session-plus/sessions.d/steam`). Until then, the BIOS dGPU-only mode or Work Mode are the workarounds. Not implemented: it needs the hardware. |
| P2 | Gaming Mode, black screen on hybrid laptops | Steam and games are started on the dGPU (`cardwire launch`) while gamescope composites on the iGPU. Buffers cross GPUs, which is a known source of black screens. | `gamescope-session-plus` starts the client through `cardwire`. | Measure on the laptop. The recovery path is reboot and choose Work Mode (there is no automatic login), and the text-console path once C2 is fixed. |
| P3 | Gaming Mode, failed starts | Bazzite's automatic fallback to Work Mode only starts on the 6th failed Gaming Mode start in one boot, and each failure means a new login. | `short_session_count_before_reset=5` in `gamescope-session-plus`. The fallback calls `steamosctl switch-to-desktop-mode`, so NebulaOS's shim, so `nebula-os-switch-side work --now`. | Keep Bazzite's mechanism and test it in the VM. The login screen always offers Work Mode. |
| P4 | Gaming Mode, quick switches | Leaving Gaming Mode within 60 s of starting it counts as a failed start (P3). Five quick switches in one boot make the next Gaming Mode start fall back to Work Mode. | Same tracker: `SECONDS < 60` when Steam exits. | Document it. It is Bazzite's behaviour, and harmless. |
| P5 | Mode switching, Steam frozen | `steam -shutdown` does nothing if Steam hangs, so "Switch to Desktop" from a hung Steam cannot work. | `nebula-os-switch-side:50-51`. | The text-console path (C2 fix) ends the graphical session directly. |
| P6 | Control Center design | Reading any amdgpu metric (`gpu_busy_percent`, hwmon temperature or power) more often than the 5 s autosuspend delay keeps an idle dGPU awake indefinitely. | Measured: no reads, back to sleep after about 7 s. One read per second for 20 s, never slept. Reads while asleep return EBUSY without waking it (handled). | Any polling front end must read an active dGPU no faster than its `autosuspend_delay_ms`, or back off once it is idle. Not a bug in today's one-shot commands. |
| P7 | Updates | After `nebula update rollback`, `nebula status` does not say that the next boot starts the older deployment. | `updates.summary` has no "rollback pending" state. | Add a state when the default deployment is not the booted one. |
| P8 | Subprocess timeouts | A timed-out command whose child processes keep the output pipes open can make `subprocess.run` wait after the kill. | Python's `communicate()` after `kill()`. None of today's commands spawn such children. | Watch for it if commands that start daemons are added. |

## What holds up

- **Sleeping GPU:** hwmon, EDID, connector status, `vendor`/`device`/`boot_vga` and `runtime_status` reads do not wake the dGPU. Measured at 0 ms each.
- **Readings on the target machine:**
  - CPU model, cores and threads (8/16), memory (14.5 GB visible with 2 GB UMA) and storage (btrfs counted once) are correct.
  - CPU temperature matches `sensors` (Tctl).
  - The iGPU's VRAM is the UMA carve-out (2 GiB).
- **GDM:** the gear menu lists exactly three sessions (Gaming Mode, Gaming Mode with the overlay, Work Mode), and there is no automatic login, so the mode can always be chosen at the login screen.
- **AccountsService:** `change-own-user-data` is allowed for any session (`allow_any=yes`), so saving the mode never asks for a password, even from a text console.
- **Steam's "Switch to Desktop":** Steam calls `steamos-session-select`, which calls `/usr/lib/os-session-select`, which calls `nebula-os-switch-side work --now`.
- **Automatic recovery:** Bazzite's recovery (`short_session_recover`) calls `steamosctl switch-to-desktop-mode`, which reaches the same path through the shim.
- **The `gamescope-session-plus@.service` unit** has no `Restart=`, so a crashing Gaming Mode returns to the login screen instead of looping.

## Not verified

These need a booted NebulaOS system. The VM test (`tests/vm/`) covers the first three, and the laptop is needed for the rest:

1. Work Mode to Gaming Mode through the dock launcher, and Gaming Mode to Work Mode through Steam.
2. Logging out and back in keeps the last chosen mode.
3. Bazzite's automatic fallback after repeated failed starts lands in Work Mode.
4. P1 and P2 on the Legion 5, in hybrid mode with an external display.

## Validation commands

```bash
just test            # unit tests, including the regression tests for C1 and C3-C7
just test-image      # image tests, including the mode-status checks
# On the target laptop: the dGPU must stay asleep while nebula runs
D=/sys/bus/pci/devices/0000:03:00.0/power
a=$(cat $D/runtime_active_time); nebula status --json >/dev/null; b=$(cat $D/runtime_active_time); echo "woke for $((b-a)) ms"
```
