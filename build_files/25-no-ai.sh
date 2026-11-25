#!/usr/bin/bash
# NebulaOS ships no AI tools. Bazzite DX includes a few; they are removed here.
#
# Kept on purpose, because they are not AI tools:
#   onnxruntime  FFmpeg's libavfilter links to it. Removing it would also remove
#                ffmpeg and GStreamer's libav plugin: video playback, OBS and video
#                thumbnails would break.
#   ROCm         General GPU compute for AMD (OpenCL, HIP rendering in Blender).
set -euo pipefail

# ramalama runs AI models. Its Python dependencies stay: other tools may use them.
if rpm -q ramalama >/dev/null 2>&1; then
    dnf5 -y remove --setopt=clean_requirements_on_remove=False ramalama
fi

# `ujust install-ai-tools` (Bazzite DX) installs an AI tool suite with Homebrew,
# and Bazzite Portal offers LM Studio. Remove both entries and the Brewfile.
rm -f /usr/share/ublue-os/homebrew/bazzite-dx-ai.Brewfile
python3 -I - <<'EOF'
from pathlib import Path


def drop_just_recipe(path: Path, recipe: str) -> None:
    """Remove a just recipe, its comment lines above and the blank line after."""
    if not path.is_file():
        return
    lines = path.read_text().splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{recipe}:")), None)
    if start is None:
        return
    end = start + 1
    while end < len(lines) and lines[end].startswith((" ", "\t")):
        end += 1
    while start > 0 and lines[start - 1].startswith("#"):
        start -= 1
    if end < len(lines) and not lines[end].strip():
        end += 1
    path.write_text("".join(lines[:start] + lines[end:]))
    print(f"Removed recipe {recipe} from {path}")


def drop_yaml_list_item(path: Path, item_id: str) -> None:
    """Remove the list item `- id: "<item_id>"` (and its indented body) from a YAML file."""
    if not path.is_file():
        return
    lines = path.read_text().splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.strip() == f'- id: "{item_id}"'), None)
    if start is None:
        return
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1
    while end < len(lines):
        stripped = lines[end].lstrip()
        width = len(lines[end]) - len(stripped)
        if stripped.strip() and (width < indent or (width == indent and stripped.startswith("- "))):
            break
        end += 1
    path.write_text("".join(lines[:start] + lines[end:]))
    print(f"Removed {item_id} from {path}")


drop_just_recipe(Path("/usr/share/ublue-os/just/95-bazzite-dx.just"), "install-ai-tools")
drop_yaml_list_item(Path("/usr/share/yafti/yafti.yml"), "lm-studio-linux")
EOF

# Both files must still parse, and nothing AI-related may be left behind.
python3 -I -c 'import yaml; yaml.safe_load(open("/usr/share/yafti/yafti.yml"))'
summary=$(just --justfile /usr/share/ublue-os/justfile --summary)
if grep -qw install-ai-tools <<<"$summary" || grep -q lm-studio /usr/share/yafti/yafti.yml || rpm -q ramalama >/dev/null 2>&1; then
    echo "ERROR: AI tools are still present." >&2
    exit 1
fi
echo "AI tools removed (ramalama, ujust install-ai-tools, Bazzite Portal's LM Studio)."
