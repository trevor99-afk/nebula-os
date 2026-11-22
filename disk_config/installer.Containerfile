# Source image for the installer ISO only (see .github/workflows/build-disk.yml).
#
# bootc-image-builder builds the installer (Anaconda) from the package repositories
# it finds in the image's /etc/yum.repos.d. Fedora 45 keeps its own repositories in
# dnf5's /usr/share/dnf5/repos.d, which the builder does not read, so it found no
# packages at all (run 45018113629). This copies them to /etc/yum.repos.d. The
# installed system deletes the copies again (iso.toml) and then updates from the
# published, signed image.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN cp /usr/share/dnf5/repos.d/fedora.repo /usr/share/dnf5/repos.d/fedora-updates.repo /etc/yum.repos.d/
