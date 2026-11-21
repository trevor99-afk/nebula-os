#!/usr/bin/bash
# Entry point for the image build (called from the Containerfile).
#
# 1. Copies everything in system_files/ into the image (system_files/usr/... -> /usr/...).
# 2. Runs the numbered scripts in this folder in order: 10-branding.sh, 20-packages.sh, ...
#    To add a step, drop in a new NN-something.sh file.
set -euo pipefail

echo "::group:: Copy system_files"
cp -avf /ctx/system_files/. /
echo "::endgroup::"

for script in /ctx/[0-9][0-9]-*.sh; do
    echo "::group:: Run ${script##*/}"
    bash "$script"
    echo "::endgroup::"
done
