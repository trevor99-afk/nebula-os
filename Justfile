set dotenv-filename := "image-template.env"
set dotenv-load

export image_name := env_var("IMAGE_NAME")
export image_pretty_name := env_var("IMAGE_PRETTY_NAME")
export repo_organization := env_var("REPO_ORGANIZATION")
export repo_name := env_var("REPO_NAME")
export base_image := env_var("BASE_IMAGE")
export image_desc := env_var("IMAGE_DESC")
export image_keywords := env_var("IMAGE_KEYWORDS")
export image_logo_url := env_var("IMAGE_LOGO_URL")
export default_tag := env_var("DEFAULT_TAG")
export bib_image := env_var("BIB_IMAGE")

alias build-vm := build-qcow2
alias rebuild-vm := rebuild-qcow2
alias run-vm := run-vm-qcow2

[private]
default:
    @just --list

# Check Just Syntax
[group('Just')]
check:
    #!/usr/bin/env bash
    find . -type f -name "*.just" | while read -r file; do
    	echo "Checking syntax: $file"
    	just --unstable --fmt --check -f $file
    done
    echo "Checking syntax: Justfile"
    just --unstable --fmt --check -f Justfile

# Fix Just Syntax
[group('Just')]
fix:
    #!/usr/bin/env bash
    find . -type f -name "*.just" | while read -r file; do
    	echo "Checking syntax: $file"
    	just --unstable --fmt -f $file
    done
    echo "Checking syntax: Justfile"
    just --unstable --fmt -f Justfile || { exit 1; }

# Clean Repo
[group('Utility')]
clean:
    #!/usr/bin/env bash
    set -eoux pipefail
    touch _build
    find *_build* -exec rm -rf {} \;
    rm -f previous.manifest.json
    rm -f changelog.md
    rm -f output.env
    rm -rf output/

# Sudo Clean Repo
[group('Utility')]
[private]
sudo-clean:
    just sudoif just clean

# sudoif bash function
[group('Utility')]
[private]
sudoif command *args:
    #!/usr/bin/env bash
    function sudoif(){
        if [[ "${UID}" -eq 0 ]]; then
            "$@"
        elif [[ "$(command -v sudo)" && -n "${SSH_ASKPASS:-}" ]] && [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
            sudo --askpass "$@" || exit 1
        elif [[ "$(command -v sudo)" ]]; then
            sudo "$@" || exit 1
        else
            exit 1
        fi
    }
    sudoif {{ command }} {{ args }}

# This Justfile recipe builds a container image using Podman.
#
# Arguments:
#   $target_image - The tag you want to apply to the image (default: $image_name).
#   $tag - The tag for the image (default: $default_tag).
#
# The NebulaOS settings from image-template.env (name, base image, GitHub
# account) are passed to the Containerfile as build arguments.
#
# Example usage:
#   just build myimage mytag
#
# This will build an image 'myimage:mytag'
#

# Build the image using the specified parameters
build $target_image=image_name $tag=default_tag:
    #!/usr/bin/env bash

    set -euox pipefail

    # The name baked into the image (update address and signature policy).
    name="${target_image##*/}"
    name="${name,,}"

    # Pull the base first so its exact digest can be recorded in the image.
    # NEBULA_PULL=never builds from the local copy (offline or quick test builds).
    if [[ "${NEBULA_PULL:-newer}" != "never" ]]; then
        podman pull "${base_image}" || echo "Could not pull ${base_image}; using the local copy."
    fi
    BASE_DIGEST=$(podman image inspect --format '{{ '{{.Digest}}' }}' "${base_image}" 2>/dev/null || true)

    GIT_SHA=""
    if git rev-parse -q --verify HEAD &>/dev/null; then
        GIT_SHA=$(git rev-parse --short HEAD)
        [[ -z "$(git status -s)" ]] || GIT_SHA="${GIT_SHA}-dirty"
    fi
    IMAGE_VERSION="${tag}.$(date -u +%Y%m%d)${GIT_SHA:+-${GIT_SHA}}"

    BUILD_ARGS=()
    BUILD_ARGS+=("--build-arg" "BASE_IMAGE=${base_image}")
    BUILD_ARGS+=("--build-arg" "BASE_DIGEST=${BASE_DIGEST}")
    BUILD_ARGS+=("--build-arg" "IMAGE_NAME=${name}")
    BUILD_ARGS+=("--build-arg" "IMAGE_PRETTY_NAME=${image_pretty_name}")
    BUILD_ARGS+=("--build-arg" "IMAGE_REGISTRY=ghcr.io/${repo_organization,,}")
    BUILD_ARGS+=("--build-arg" "IMAGE_TAG=${tag}")
    BUILD_ARGS+=("--build-arg" "IMAGE_VERSION=${IMAGE_VERSION}")
    BUILD_ARGS+=("--build-arg" "GIT_SHA=${GIT_SHA}")

    # The project repository: both editions are built from it.
    REPO_URL="https://github.com/${repo_organization}/${repo_name}"
    BUILD_ARGS+=("--build-arg" "REPO_URL=${REPO_URL}")
    REVISION=""
    README_URL="${REPO_URL}#readme"
    if [[ -n "${GIT_SHA}" ]]; then
        REVISION=$(git rev-parse HEAD)
        if [[ "${GIT_SHA}" == *-dirty ]]; then
            REVISION="${REVISION}-dirty"
        else
            README_URL="https://raw.githubusercontent.com/${repo_organization}/${repo_name}/${REVISION}/README.md"
        fi
    fi

    # Every OCI and ArtifactHub label is set here, so none is inherited from the base image
    # (its revision and source describe Bazzite). `just ostree-rechunk` copies them to the
    # published image. GitHub links the package to the repository through
    # org.opencontainers.image.source, which must be the plain repository URL.
    # ArtifactHub metadata is optional: it does nothing unless you list the image there.
    LABELS=()
    LABELS+=("--label" "org.opencontainers.image.title=${name}")
    LABELS+=("--label" "org.opencontainers.image.description={{ image_desc }}")
    LABELS+=("--label" "org.opencontainers.image.version=${IMAGE_VERSION}")
    LABELS+=("--label" "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)")
    LABELS+=("--label" "org.opencontainers.image.revision=${REVISION}")
    LABELS+=("--label" "org.opencontainers.image.source=${REPO_URL}")
    LABELS+=("--label" "org.opencontainers.image.url=${REPO_URL}")
    LABELS+=("--label" "org.opencontainers.image.documentation=${README_URL}")
    LABELS+=("--label" "org.opencontainers.image.vendor={{ repo_organization }}")
    LABELS+=("--label" "org.opencontainers.image.licenses=Apache-2.0")
    LABELS+=("--label" "org.opencontainers.image.base.name=${base_image}")
    LABELS+=("--label" "org.opencontainers.image.base.digest=${BASE_DIGEST}")
    LABELS+=("--label" "io.artifacthub.package.readme-url=${README_URL}")
    LABELS+=("--label" "io.artifacthub.package.keywords={{ image_keywords }}")
    LABELS+=("--label" "io.artifacthub.package.license=Apache-2.0")
    LABELS+=("--label" "io.artifacthub.package.logo-url={{ image_logo_url }}")
    LABELS+=("--label" "io.artifacthub.package.deprecated=false")
    LABELS+=("--label" "io.artifacthub.package.prerelease=$([[ "${tag}" == latest ]] && echo false || echo true)")

    # This actually builds the image!
    PODMAN_BUILD_ARGS=("${BUILD_ARGS[@]}" "${LABELS[@]}" --pull=never --tag "${target_image}:${tag}" --file Containerfile)

    podman build "${PODMAN_BUILD_ARGS[@]}" .

# Split the image for smaller updates (New)!
rechunk $target_image=image_name $tag=default_tag:
    #!/usr/bin/env bash

    set -xeuo pipefail

    # TODO: pin chunkah image to hash once mature enough
    # You may run into space issues on github runners as we are making a
    # complete copy of the image, which likely has no shared layers, unless your
    # base image is also using chunkah
    CHUNKAH_CONFIG_FILE="$(mktemp)"

    # You may omit the current directory here if you are confident that you
    # won't run out of space on /tmp for your image
    CHUNKAH_OUTPUT_DIR="$(mktemp -d ./"${target_image}"_chunkah_XXXXXX)"

    trap 'rm -f "${CHUNKAH_CONFIG_FILE}"; rm -rf "${CHUNKAH_OUTPUT_DIR}"' EXIT
    podman inspect "${target_image}:${tag}" > "${CHUNKAH_CONFIG_FILE}"

    podman run --rm \
      --mount=type=image,src="${target_image}:${tag}",target=/chunkah \
      -v "${CHUNKAH_CONFIG_FILE}:/chunkah-config.json:ro,Z" \
      -v "${CHUNKAH_OUTPUT_DIR}:/run/out:Z" \
      quay.io/coreos/chunkah:latest \
      build \
      --verbose \
      --compressed \
      --max-layers 128 \
      --prune /sysroot/ \
      --label ostree.commit- --label ostree.final-diffid- \
      --config /chunkah-config.json \
      --output oci:/run/out/chunked

    CHUNKED_IMAGE="$(podman pull "oci:${CHUNKAH_OUTPUT_DIR}/chunked")"
    podman tag "${CHUNKED_IMAGE}" "${target_image}:${tag}"

# Split the image for smaller updates (Classical)!
ostree-rechunk $target_image=image_name $tag=default_tag:
    #!/usr/bin/env bash

    set -xeuo pipefail

    # Use the already-built local image to avoid pulling from a remote registry
    RPM_OSTREE_CHUNKER_IMAGE="localhost/${target_image}:${tag}"

    GRAPHROOT="$(podman info --format '{{ '{{.Store.GraphRoot}}' }}')"

    # The chunked image is made from the file tree, so labels are not carried over on their
    # own. Copy the build's labels (version, source, base image: see `just build`) and the
    # kernel version. The rechunker sets containers.bootc and the ostree commit labels itself.
    LABELS_JSON=$(podman image inspect "${RPM_OSTREE_CHUNKER_IMAGE}" | jq '.[0].Labels')
    VERSION=$(jq -r '.["org.opencontainers.image.version"] // ""' <<<"${LABELS_JSON}")
    LABEL_ARGS=()
    while IFS= read -r -d '' label; do
        LABEL_ARGS+=("--label" "${label}")
    done < <(jq -j 'to_entries[]
        | select((.key | test("^(org\\.opencontainers\\.image|io\\.artifacthub\\.package)\\.")) or .key == "ostree.linux" or .key == "ostree.bootable")
        | "\(.key)=\(.value)\u0000"' <<<"${LABELS_JSON}")

    podman run --rm --pull=never --privileged \
      --mount=type=image,src="${target_image}:${tag}",target=/rpm-ostree \
      --mount=type=bind,src=${GRAPHROOT},target=/run/host-container-storage,rw \
      --mount=type=tmpfs,target=/run/rpm-ostree-storage \
      --entrypoint /usr/bin/rpm-ostree \
      "${RPM_OSTREE_CHUNKER_IMAGE}" \
      compose build-chunked-oci \
      --max-layers 127 \
      --format-version=2 \
      --bootc \
      "${LABEL_ARGS[@]}" \
      --rootfs /rpm-ostree \
      --output "containers-storage:[overlay@/run/host-container-storage+/run/rpm-ostree-storage]localhost/${target_image}:${tag}"

    # rpm-ostree status shows this label as the system version: never publish without it.
    after=$(podman image inspect "${RPM_OSTREE_CHUNKER_IMAGE}" | jq -r '.[0].Labels["org.opencontainers.image.version"] // ""')
    if [[ -z "${VERSION}" || "${after}" != "${VERSION}" ]]; then
        echo "ERROR: the rechunked image has version label '${after}', expected '${VERSION}'." >&2
        exit 1
    fi

# Generate Default Tag
[group('Utility')]
generate-default-tag $tag=default_tag:
    #!/usr/bin/env bash
    set -eoux pipefail

    echo "${tag}"

# Generate Tags
[group('Utility')]
generate-build-tags $target_image=image_name $tag=default_tag:
    #!/usr/bin/env bash
    set -eoux pipefail

    # The channel tag (e.g. latest or testing) is always LAST: CI pushes the
    # other tags, signs the image, and only then moves the channel tag.
    DATE=$(date +%Y%m%d)
    BUILD_TAGS=("${tag}-${DATE}")
    if git rev-parse -q --verify HEAD &>/dev/null && [[ -z "$(git status -s)" ]]; then
        BUILD_TAGS+=("${tag}-$(git rev-parse --short HEAD)")
    fi
    BUILD_TAGS+=("${tag}")

    echo "${BUILD_TAGS[@]}"

# Tag Images
[group('Utility')]
tag-images $target_image=image_name $tag=default_tag tags="":
    #!/usr/bin/env bash
    set -eoux pipefail

    # Get Image, and untag
    IMAGE=$(podman inspect ${target_image}:${tag} | jq -r .[].Id)
    podman untag ${IMAGE}

    # Tag Image
    for tag in {{ tags }}; do
        podman tag $IMAGE "${target_image}:${tag}"
    done

    # Show Images
    podman images

# Image Name
[group('Utility')]
[private]
image_name $target_image=image_name:
    #!/usr/bin/env bash
    set -eoux pipefail

    echo "${image_name}"

# Command: _rootful_load_image
# Description: This script checks if the current user is root or running under sudo. If not, it attempts to resolve the image tag using podman inspect.
#              If the image is found, it loads it into rootful podman. If the image is not found, it pulls it from the repository.
#
# Parameters:
#   $target_image - The name of the target image to be loaded or pulled.
#   $tag - The tag of the target image to be loaded or pulled. Default is 'default_tag'.
#
# Example usage:
#   _rootful_load_image my_image latest
#
# Steps:
# 1. Check if the script is already running as root or under sudo.
# 2. Check if target image is in the non-root podman container storage)
# 3. If the image is found, load it into rootful podman using podman scp.
# 4. If the image is not found, pull it from the remote repository into reootful podman.

_rootful_load_image $target_image=image_name $tag=default_tag:
    #!/usr/bin/env bash
    set -eoux pipefail

    # Check if already running as root or under sudo
    if [[ -n "${SUDO_USER:-}" || "${UID}" -eq "0" ]]; then
        echo "Already root or running under sudo, no need to load image from user podman."
        exit 0
    fi

    # Try to resolve the image tag using podman inspect
    set +e
    resolved_tag=$(podman inspect -t image "${target_image}:${tag}" | jq -r '.[].RepoTags.[0]')
    return_code=$?
    set -e

    USER_IMG_ID=$(podman images --filter reference="${target_image}:${tag}" --format "'{{ '{{.ID}}' }}'")

    if [[ $return_code -eq 0 ]]; then
        # If the image is found, load it into rootful podman
        ID=$(just sudoif podman images --filter reference="${target_image}:${tag}" --format "'{{ '{{.ID}}' }}'")
        if [[ "$ID" != "$USER_IMG_ID" ]]; then
            # If the image ID is not found or different from user, copy the image from user podman to root podman
            COPYTMP=$(mktemp -p "${PWD}" -d -t _build_podman_scp.XXXXXXXXXX)
            just sudoif TMPDIR=${COPYTMP} podman image scp ${UID}@localhost::"${target_image}:${tag}" root@localhost::"${target_image}:${tag}"
            rm -rf "${COPYTMP}"
        fi
    else
        # If the image is not found, pull it from the repository
        just sudoif podman pull "${target_image}:${tag}"
    fi

# Build a bootc bootable image using Bootc Image Builder (BIB)
# Converts a container image to a bootable image
# Parameters:
#   target_image: The name of the image to build (ex. localhost/fedora)
#   tag: The tag of the image to build (ex. latest)
#   type: The type of image to build (ex. qcow2, raw, iso)
#   config: The configuration file to use for the build (default: disk_config/disk.toml)

# Example: just _rebuild-bib localhost/fedora latest qcow2 disk_config/disk.toml
_build-bib $target_image $tag $type $config: (_rootful_load_image target_image tag)
    #!/usr/bin/env bash
    set -euo pipefail

    if [[ "${type}" == "iso" && "${repo_organization}" == "your-github-username" ]]; then
        echo "WARNING: REPO_ORGANIZATION in image-template.env is still the placeholder."
        echo "         Systems installed from this ISO will look for updates at"
        echo "         ghcr.io/your-github-username/${image_name}, which does not exist."
    fi

    args="--type ${type} "
    args+="--use-librepo=True "
    args+="--rootfs=btrfs"

    BUILDTMP=$(mktemp -p "${PWD}" -d -t _build-bib.XXXXXXXXXX)

    sudo podman run \
      --rm \
      -it \
      --privileged \
      --pull=newer \
      --net=host \
      --security-opt label=type:unconfined_t \
      -v $(pwd)/${config}:/config.toml:ro \
      -v $BUILDTMP:/output \
      -v /var/lib/containers/storage:/var/lib/containers/storage \
      "${bib_image}" \
      ${args} \
      "${target_image}:${tag}"

    mkdir -p output
    sudo mv -f $BUILDTMP/* output/
    sudo rmdir $BUILDTMP
    sudo chown -R $USER:$USER output/

# Podman builds the image from the Containerfile and creates a bootable image
# Parameters:
#   target_image: The name of the image to build (ex. localhost/fedora)
#   tag: The tag of the image to build (ex. latest)
#   type: The type of image to build (ex. qcow2, raw, iso)
#   config: The configuration file to use for the build (deafult: disk_config/disk.toml)

# Example: just _rebuild-bib localhost/fedora latest qcow2 disk_config/disk.toml
_rebuild-bib $target_image $tag $type $config: (build target_image tag) && (_build-bib target_image tag type config)

# Build a QCOW2 virtual machine image
[group('Build Virtual Machine Image')]
build-qcow2 $target_image=("localhost/" + image_name) $tag=default_tag: && (_build-bib target_image tag "qcow2" "disk_config/disk.toml")

# Build a RAW virtual machine image
[group('Build Virtual Machine Image')]
build-raw $target_image=("localhost/" + image_name) $tag=default_tag: && (_build-bib target_image tag "raw" "disk_config/disk.toml")

# Build an ISO virtual machine image
[group('Build Virtual Machine Image')]
build-iso $target_image=("localhost/" + image_name) $tag=default_tag: && (_build-bib target_image tag "iso" "disk_config/iso.toml")

# Rebuild a QCOW2 virtual machine image
[group('Build Virtual Machine Image')]
rebuild-qcow2 $target_image=("localhost/" + image_name) $tag=default_tag: && (_rebuild-bib target_image tag "qcow2" "disk_config/disk.toml")

# Rebuild a RAW virtual machine image
[group('Build Virtual Machine Image')]
rebuild-raw $target_image=("localhost/" + image_name) $tag=default_tag: && (_rebuild-bib target_image tag "raw" "disk_config/disk.toml")

# Rebuild an ISO virtual machine image
[group('Build Virtual Machine Image')]
rebuild-iso $target_image=("localhost/" + image_name) $tag=default_tag: && (_rebuild-bib target_image tag "iso" "disk_config/iso.toml")

# Run a virtual machine with the specified image type and configuration
_run-vm $target_image $tag $type $config:
    #!/usr/bin/env bash
    set -eoux pipefail

    # Determine the image file based on the type
    image_file="output/${type}/disk.${type}"
    if [[ $type == iso ]]; then
        image_file="output/bootiso/install.iso"
    fi

    # Build the image if it does not exist
    if [[ ! -f "${image_file}" ]]; then
        just "build-${type}" "$target_image" "$tag"
    fi

    # Determine an available port to use
    port=8006
    while grep -q :${port} <<< $(ss -tunalp); do
        port=$(( port + 1 ))
    done
    echo "Using Port: ${port}"
    echo "Connect to http://localhost:${port}"

    # Set up the arguments for running the VM
    run_args=()
    run_args+=(--rm --privileged)
    run_args+=(--pull=newer)
    run_args+=(--publish "127.0.0.1:${port}:8006")
    run_args+=(--env "CPU_CORES=4")
    run_args+=(--env "RAM_SIZE=8G")
    run_args+=(--env "DISK_SIZE=64G")
    run_args+=(--env "TPM=Y")
    run_args+=(--env "GPU=Y")
    run_args+=(--device=/dev/kvm)
    run_args+=(--volume "${PWD}/${image_file}":"/boot.${type}")
    run_args+=(docker.io/qemux/qemu)

    # Run the VM and open the browser to connect
    (sleep 30 && xdg-open http://localhost:"$port") &
    podman run "${run_args[@]}"

# Run a virtual machine from a QCOW2 image
[group('Run Virtual Machine')]
run-vm-qcow2 $target_image=("localhost/" + image_name) $tag=default_tag: && (_run-vm target_image tag "qcow2" "disk_config/disk.toml")

# Run a virtual machine from a RAW image
[group('Run Virtual Machine')]
run-vm-raw $target_image=("localhost/" + image_name) $tag=default_tag: && (_run-vm target_image tag "raw" "disk_config/disk.toml")

# Run a virtual machine from an ISO
[group('Run Virtual Machine')]
run-vm-iso $target_image=("localhost/" + image_name) $tag=default_tag: && (_run-vm target_image tag "iso" "disk_config/iso.toml")

# Run a virtual machine using systemd-vmspawn
[group('Run Virtual Machine')]
spawn-vm rebuild="0" type="qcow2" ram="6G":
    #!/usr/bin/env bash

    set -euo pipefail

    [ "{{ rebuild }}" -eq 1 ] && echo "Rebuilding the ISO" && just build-vm {{ rebuild }} {{ type }}

    systemd-vmspawn \
      -M "bootc-image" \
      --console=gui \
      --cpus=2 \
      --ram=$(echo {{ ram }}| numfmt --from=iec) \
      --network-user-mode \
      --vsock=false --pass-ssh-key=false \
      -i ./output/**/*.{{ type }}

# Switch this computer to the image you built locally (takes effect after a reboot)
[group('Install')]
switch-local $target_image=image_name $tag=default_tag: (_rootful_load_image target_image tag)
    #!/usr/bin/env bash
    set -euo pipefail
    sudo bootc switch --transport containers-storage "localhost/${target_image}:${tag}"
    echo "Done. Reboot to start ${image_pretty_name}."
    echo "Changed your mind? Run 'sudo bootc rollback' and reboot."

# Switch this computer to your published image on ghcr.io (takes effect after a reboot)
[group('Install')]
switch-published:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${repo_organization}" == "your-github-username" ]]; then
        echo "Set REPO_ORGANIZATION in image-template.env to your GitHub username first." >&2
        exit 1
    fi
    sudo bootc switch "ghcr.io/${repo_organization,,}/${image_name,,}:${default_tag}"
    echo "Done. Reboot to start ${image_pretty_name}, then run: ujust nebula-enable-signed-updates"

# Run the unit tests for the nebula tools
[group('Test')]
test:
    python3 -I -m unittest discover -s tests/unit -p 'test_*.py'

# Check config files (TOML, app IDs, units) without building
[group('Test')]
validate:
    python3 -I tests/validate_configs.py

# Run the smoke tests inside a built image (CI runs this before publishing)
[group('Test')]
test-image $target_image=image_name $tag=default_tag:
    #!/usr/bin/env bash
    set -euo pipefail
    name="${target_image##*/}"
    expected="ghcr.io/${repo_organization,,}/${name,,}:${tag}"
    podman run --rm --pull=never --security-opt label=disable \
        -v "${PWD}/tests/image:/tests:ro" "${target_image}:${tag}" bash /tests/test-image.sh "${expected}" "https://github.com/${repo_organization}/${repo_name}"

# Runs shellcheck on all shell scripts (in a container if shellcheck is not installed)
lint:
    #!/usr/bin/env bash
    set -euo pipefail
    mapfile -t scripts < <(find build_files tests -name '*.sh'; find system_files/usr/libexec -type f; echo system_files/usr/lib/os-session-select)
    if command -v shellcheck &> /dev/null; then
        shellcheck "${scripts[@]}"
    else
        podman run --rm --security-opt label=disable -v "${PWD}:/mnt:ro" -w /mnt \
            docker.io/koalaman/shellcheck:stable "${scripts[@]}"
    fi

# Runs shfmt on all Bash scripts
format:
    #!/usr/bin/env bash
    set -eoux pipefail
    # Check if shfmt is installed
    if ! command -v shfmt &> /dev/null; then
        echo "shfmt could not be found. Please install it."
        exit 1
    fi
    # Run shfmt on all Bash scripts
    find . -iname "*.sh" -type f -exec shfmt --write "{}" ';'
