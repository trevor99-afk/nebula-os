# Hardware compatibility

NebulaOS uses the drivers of its Bazzite DX base: Mesa (RADV, ANV) for AMD and Intel, and NVIDIA's driver in the NVIDIA edition. NebulaOS never installs or switches GPU drivers itself. Pick the right edition instead ([INSTALLATION.md](INSTALLATION.md#editions)).

Run `nebula hw` to see what your machine supports. Each feature is reported at five levels (hardware, driver, available, enabled, verified), so you can tell "my monitor can do VRR" apart from "VRR is on" and "VRR was verified".

## Tested hardware

| Machine | GPU(s) | Display | Result |
| --- | --- | --- | --- |
| Lenovo Legion 5 15ACH6A (Ryzen 7 5800H, 13.5 GiB) | Radeon Vega (Cezanne, GCN 5) iGPU + Radeon RX 6600M (Navi 23, RDNA 2), CardWire hybrid mode | Built-in AUO 1920×1080, 165 Hz, 10-bit, VRR 60–165 Hz, no HDR | `nebula` backend verified on Bazzite GNOME (2026-11-21): Vulkan, OpenGL and VA-API verified working on both GPUs (radv / radeonsi, Mesa 26.2.7). AV1, H.264, HEVC and VP9 decode and H.264/HEVC encode on the RX 6600M. VRR available, off by default. HDR correctly reported as unsupported. **NebulaOS image not yet booted on it.** |

Help extend this table: attach `nebula hw --json` (it contains no serial numbers) to a GitHub issue with what worked.

## By vendor

| Vendor | Edition | Notes |
| --- | --- | --- |
| AMD Radeon (GCN 4 / RX 400 and newer) | `nebula-os` | Best supported. Vulkan via RADV, VA-API via radeonsi, GPU usage, VRAM, temperature and power monitoring. Very old GCN 1/2 cards on the legacy `radeon` driver have no Vulkan; `nebula hw` warns about this. |
| Intel Xe / Arc | `nebula-os` | Vulkan via ANV, VA-API via iHD. GPU usage is not exposed without perf permissions, so NebulaOS shows it as unavailable rather than guessing. Untested so far. |
| NVIDIA (Turing / GTX 16, RTX 20 and newer) | `nebula-os-nvidia` | Builds in CI; **untested on hardware**. Monitoring via `nvidia-smi`. Older generations (Pascal, Maxwell) are not supported by NVIDIA's open kernel modules. With Secure Boot on, enroll the Universal Blue key. |
| Hybrid laptops (two GPUs) | either | CardWire (from Bazzite) manages which GPU apps use; `nebula hw` shows its mode and which GPU drives the screen. Steam Gaming Mode can show a black screen on some dual-GPU machines, and external monitors wired to the dedicated GPU (all HDMI/DisplayPort outputs on the Legion 5 15ACH6A) probably stay black in Gaming Mode. Work Mode always works, drives every output, and runs Steam too. |

## Known limitations

- Steam Gaming Mode on dual-GPU machines: see above.
- HDR needs a display that advertises it (EDID) and a desktop mode that offers BT.2100. `nebula hw` shows both.
- The ISO installer has not been tested on hardware ([INSTALLATION.md](INSTALLATION.md#experimental-installer-iso)).
