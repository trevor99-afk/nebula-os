#!/usr/bin/bash
# Bazaar app store: add a "Development & Work" section for the work side.
#
# Bazaar ships with Bazzite and reads its curated rows from content.yaml.
# The section is inserted as the first row; the list itself lives in
# build_files/bazaar-dev-work.yaml (Flathub app IDs).
set -euo pipefail

CONTENT=/usr/share/ublue-os/bazaar/content.yaml
SECTION=/ctx/bazaar-dev-work.yaml

if [[ ! -f "$CONTENT" ]] || ! grep -qx 'rows:' "$CONTENT"; then
    echo "Note: Bazaar's content.yaml is missing or changed format; skipping the Development & Work section."
    exit 0
fi
if grep -q '"Development & Work"' "$CONTENT"; then
    echo "Development & Work section already present."
    exit 0
fi

awk -v section="$SECTION" '
    { print }
    $0 == "rows:" && !done {
        while ((getline line < section) > 0) print line
        done = 1
    }
' "$CONTENT" >/tmp/content.yaml
install -m0644 /tmp/content.yaml "$CONTENT"

if python3 -c 'import yaml' 2>/dev/null; then
    python3 -c 'import sys, yaml; rows = yaml.safe_load(open(sys.argv[1]))["rows"]; print("Bazaar rows:", len(rows), "- first:", rows[0]["section"]["title"]["en"])' "$CONTENT"
fi
