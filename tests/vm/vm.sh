#!/usr/bin/bash
# Run NebulaOS in a test VM without root: QEMU runs inside the NebulaOS
# container image with /dev/kvm passed in, and boots with UEFI like a real PC.
#
#   tests/vm/vm.sh install INSTALL.iso [SIZE]  boot the installer ISO with a new, empty disk (default 64G)
#   tests/vm/vm.sh boot                        boot the disk installed with `install`
#   tests/vm/vm.sh start DISK.qcow2 [gl]       boot a ready-made disk image through a throwaway overlay
#                                              (gl: 3D through virgl/venus on the host GPU)
#   tests/vm/vm.sh stop                        stop the VM
#   tests/vm/vm.sh reset                       stop and delete the VM's disks (the downloaded images stay)
#   tests/vm/vm.sh shot FILE.png               screenshot; any other qmp.py action works the same way
#
# Everything the VM writes lives in $NEBULA_VM_DIR (default ~/NebulaOS-VM/run).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${NEBULA_VM_DIR:-$HOME/NebulaOS-VM/run}
QEMU_IMAGE=${NEBULA_VM_QEMU_IMAGE:-localhost/nebula-os:latest}
NAME=nebula-test-vm
MEM=${NEBULA_VM_MEM:-5G}
OVMF=/usr/share/edk2/ovmf

qmp() { python3 -I "$HERE/qmp.py" "$DIR/qmp.sock" "$@"; }
in_image() { podman run --rm --pull=never --security-opt label=disable -v "$DIR:/vm" "$@"; }

# run_qemu DISK [EXTRA_PODMAN_ARGS...] -- [EXTRA_QEMU_ARGS...]
run_qemu() {
    local disk=$1; shift
    local podman_args=() qemu_args=()
    while [[ $# -gt 0 && $1 != -- ]]; do podman_args+=("$1"); shift; done
    [[ ${1:-} == -- ]] && shift
    qemu_args=("$@")
    [[ -f "$DIR/OVMF_VARS.fd" ]] || in_image "$QEMU_IMAGE" cp "$OVMF/OVMF_VARS.fd" /vm/OVMF_VARS.fd
    rm -f "$DIR/qmp.sock"
    podman run -d --rm --name "$NAME" --pull=never --security-opt label=disable --network host \
        --device /dev/kvm -v "$DIR:/vm" "${podman_args[@]}" "$QEMU_IMAGE" \
        qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -smp 4 -m "$MEM" \
        -drive "if=pflash,format=raw,unit=0,readonly=on,file=$OVMF/OVMF_CODE.fd" \
        -drive "if=pflash,format=raw,unit=1,file=/vm/OVMF_VARS.fd" \
        -drive "file=/vm/$disk,if=virtio,cache=unsafe" \
        -device qemu-xhci -device usb-tablet -device usb-kbd \
        -netdev user,id=n0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=n0 \
        -qmp unix:/vm/qmp.sock,server=on,wait=off -serial file:/vm/serial.log "${qemu_args[@]}" >/dev/null
    for _ in $(seq 50); do [[ -S "$DIR/qmp.sock" ]] && break; sleep 0.2; done
    echo "VM started (QMP: $DIR/qmp.sock, serial log: $DIR/serial.log)"
}

case "${1:-}" in
    install)
        iso=$(realpath "${2:?installer ISO}")
        mkdir -p "$DIR"
        [[ -f "$DIR/installed.qcow2" ]] || in_image "$QEMU_IMAGE" qemu-img create -q -f qcow2 /vm/installed.qcow2 "${3:-64G}"
        run_qemu installed.qcow2 -v "$iso:/install.iso:ro" -- \
            -device virtio-vga -display none -drive "file=/install.iso,media=cdrom,readonly=on" -boot order=dc
        ;;
    boot)
        [[ -f "$DIR/installed.qcow2" ]] || { echo "Nothing installed yet: run '$0 install INSTALL.iso' first." >&2; exit 1; }
        run_qemu installed.qcow2 -- -device virtio-vga -display none
        ;;
    start)
        base=$(realpath "${2:?disk image}")
        mkdir -p "$DIR"
        [[ -f "$DIR/overlay.qcow2" ]] || in_image -v "$base:/base.qcow2:ro" "$QEMU_IMAGE" \
            qemu-img create -q -f qcow2 -b /base.qcow2 -F qcow2 /vm/overlay.qcow2
        if [[ "${3:-}" == gl ]]; then
            run_qemu overlay.qcow2 -v "$base:/base.qcow2:ro" --device /dev/dri/renderD128 -- \
                -device "virtio-vga-gl,blob=true,hostmem=2G,venus=true" -display "egl-headless,rendernode=/dev/dri/renderD128"
        else
            run_qemu overlay.qcow2 -v "$base:/base.qcow2:ro" -- -device virtio-vga -display none
        fi
        ;;
    shot)
        # QEMU writes the file inside its container, where $DIR is /vm.
        qmp shot /vm/.screenshot.png
        mv "$DIR/.screenshot.png" "${2:?FILE.png}"
        ;;
    stop) podman stop -t 5 "$NAME" >/dev/null 2>&1 || true; echo "VM stopped" ;;
    reset) "$0" stop; rm -f "$DIR"/overlay.qcow2 "$DIR"/installed.qcow2 "$DIR"/OVMF_VARS.fd; echo "VM disks deleted" ;;
    "") sed -n 2,14p "$0"; exit 2 ;;
    *) qmp "$@" ;;
esac
