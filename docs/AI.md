# Local AI on NebulaOS

Local AI is optional: nothing is downloaded unless you ask for it. Models are often several gigabytes each.

## Available today (inherited from Bazzite DX)

- **ramalama** (`ramalama --help`) runs AI models in containers and picks GPU acceleration for your hardware. Running a model downloads it first.
- **ROCm** user-space libraries for AMD GPUs (in the AMD/Intel edition). The NVIDIA edition uses NVIDIA's driver. CUDA is only available on NVIDIA GPUs.
- **Containers** (Podman, Docker, Distrobox) for tools such as Ollama, Open WebUI, JupyterLab or ComfyUI.
- **Bazaar** and **Bazzite Portal** offer AI apps (for example Alpaca) as Flatpaks.
- `ujust install-ai-tools` (Bazzite DX) installs extra command-line AI tools with Homebrew.

Check what your GPU offers with `nebula hw`: vendor, architecture, Vulkan, and VRAM in `nebula status`.

## Planned

**Nebula AI Hub:** discover and install AI tools, manage local models and their storage, show GPU resources and the matching acceleration (ROCm, CUDA, Vulkan), and monitor AI workloads. Models are never downloaded automatically. See [ROADMAP.md](ROADMAP.md#phase-4-development-and-ai).
