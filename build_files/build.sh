#!/usr/bin/bash
# Entry point for the image build (called from the Containerfile).
#
# 1. Copies everything in system_files/ into the image (system_files/usr/... -> /usr/...).
# 2. Runs the numbered scripts in this folder in order: 10-branding.sh, 15-bazaar.sh, ...
#    To add a step, drop in a new NN-something.sh file.
set -euo pipefail

echo "::group:: Copy system_files"
# List files that replace something the base image already ships, so a Bazzite
# change that collides with NebulaOS shows up in the build log.
(cd /ctx/system_files && find . -type f -o -type l) | while read -r f; do
    if [[ -e "/${f#./}" || -L "/${f#./}" ]]; then
        echo "NOTE: replacing base image file /${f#./}"
    fi
done
cp -avf /ctx/system_files/. /
echo "::endgroup::"

for script in /ctx/[0-9][0-9]-*.sh; do
    echo "::group:: Run ${script##*/}"
    bash "$script"
    echo "::endgroup::"
done
