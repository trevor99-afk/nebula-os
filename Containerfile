# NebulaOS: a gaming-focused Linux distribution built on top of Bazzite.
#
# Build it with:  just build
# Every setting (name, base image, GitHub account) lives in image-template.env;
# the Justfile passes those values in as the build arguments below.

# The Bazzite edition to build on. Must be declared before the first FROM.
# Bazzite DX (GNOME) brings both sides: Steam Gaming Mode and a GNOME desktop
# with developer tools.
ARG BASE_IMAGE="ghcr.io/ublue-os/bazzite-dx-gnome:stable"

# Build scripts and files live in this throwaway stage. They are mounted while
# building and never end up in the final image.
FROM scratch AS ctx
COPY build_files /
COPY system_files /system_files
COPY cosign.pub /cosign.pub

FROM ${BASE_IMAGE}

# Re-declare to make the global value visible inside this stage.
ARG BASE_IMAGE
ARG IMAGE_NAME="nebula-os"
ARG IMAGE_PRETTY_NAME="NebulaOS"
ARG IMAGE_REGISTRY="ghcr.io/your-github-username"
# Project repository (both editions are built from it): os-release links point here.
ARG REPO_URL="https://github.com/your-github-username/nebula-os"
ARG IMAGE_TAG="latest"
# Traceability (shown by `nebula status`); the Justfile fills these in.
ARG IMAGE_VERSION=""
ARG GIT_SHA=""
ARG BASE_DIGEST=""
# The base image's name as recorded in the image (CI builds from a pinned digest of it).
ARG BASE_IMAGE_NAME=""

### MODIFICATIONS
## All changes happen in build_files/build.sh and the numbered scripts next to it.
RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/build.sh

### LINTING
## Verify final image and contents are correct.
RUN bootc container lint
