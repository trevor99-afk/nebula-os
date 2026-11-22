#!/usr/bin/env bash
# Boot a built qcow2 under UEFI/KVM and require GDM's NebulaOS banner to appear.
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 ARTIFACT_DIR RESULTS_DIR" >&2
    exit 2
fi

artifact_dir=$(realpath "$1")
results_dir=$(realpath -m "$2")
mkdir -p "$results_dir"

disk=$(find "$artifact_dir" -type f -name '*.qcow2' -print -quit)
if [[ -z "$disk" ]]; then
    echo "No qcow2 disk image found in $artifact_dir" >&2
    exit 1
fi
[[ -r /dev/kvm && -w /dev/kvm ]] || { echo "/dev/kvm is missing or not readable and writable: $(ls -l /dev/kvm 2>&1)" >&2; exit 1; }

ovmf_code=
ovmf_vars_template=
for directory in /usr/share/OVMF /usr/share/edk2/ovmf; do
    for suffix in _4M ''; do
        code="$directory/OVMF_CODE${suffix}.fd"
        vars="$directory/OVMF_VARS${suffix}.fd"
        if [[ -r "$code" && -r "$vars" ]]; then
            ovmf_code=$code
            ovmf_vars_template=$vars
            break 2
        fi
    done
done
if [[ -z "$ovmf_code" ]]; then
    echo "Could not find a matching OVMF_CODE/OVMF_VARS pair" >&2
    exit 1
fi

cp "$ovmf_vars_template" "$results_dir/OVMF_VARS.fd"
qmp_socket="$results_dir/qmp.sock"
rm -f "$qmp_socket"

# shellcheck disable=SC2329  # called by the EXIT trap
cleanup() {
    if [[ -n ${qemu_pid:-} ]] && kill -0 "$qemu_pid" 2>/dev/null; then
        kill "$qemu_pid" 2>/dev/null || true
        wait "$qemu_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT

qemu-system-x86_64 \
    -enable-kvm -machine q35 -cpu host -smp 4 -m 5G \
    -drive "if=pflash,format=raw,unit=0,readonly=on,file=$ovmf_code" \
    -drive "if=pflash,format=raw,unit=1,file=$results_dir/OVMF_VARS.fd" \
    -drive "file=$disk,if=virtio,format=qcow2,snapshot=on" \
    -device virtio-vga -device qemu-xhci -device usb-kbd -device usb-tablet \
    -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
    -display vnc=127.0.0.1:1 \
    -qmp "unix:$qmp_socket,server=on,wait=off" \
    -serial "file:$results_dir/serial.log" \
    >"$results_dir/qemu.log" 2>&1 &
qemu_pid=$!

for _ in $(seq 1 100); do
    if [[ -S "$qmp_socket" ]]; then
        break
    fi
    if ! kill -0 "$qemu_pid" 2>/dev/null; then
        cat "$results_dir/qemu.log" >&2
        exit 1
    fi
    sleep 0.2
done
[[ -S "$qmp_socket" ]] || { echo "QEMU QMP socket did not start" >&2; exit 1; }

deadline=$((SECONDS + 600))
while (( SECONDS < deadline )); do
    if ! kill -0 "$qemu_pid" 2>/dev/null; then
        echo "QEMU exited before GDM appeared" >&2
        cat "$results_dir/qemu.log" >&2
        exit 1
    fi
    if python3 tests/vm/qmp.py "$qmp_socket" shot "$results_dir/login-screen.png" 2>/dev/null; then
        if tesseract "$results_dir/login-screen.png" stdout 2>/dev/null \
            | tr '[:upper:]' '[:lower:]' \
            | grep -q 'choose your mode'; then
            echo "NebulaOS GDM login banner detected."
            exit 0
        fi
    fi
    sleep 10
done

echo "Timed out waiting for the NebulaOS GDM login banner" >&2
if [[ -S "$qmp_socket" ]]; then
    python3 tests/vm/qmp.py "$qmp_socket" shot "$results_dir/login-screen.png" || true
fi
exit 1
