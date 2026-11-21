#!/usr/bin/bash
# Lets installed systems check that updates were really built and signed by you.
#
# The public key is cosign.pub from the repository root. GitHub Actions signs
# every published image with the matching private key (the SIGNING_SECRET
# repository secret). Systems only enforce the signature after running
# `ujust nebula-enable-signed-updates`.
set -euo pipefail

: "${IMAGE_NAME:?}" "${IMAGE_REGISTRY:?}"

REPO="${IMAGE_REGISTRY}/${IMAGE_NAME}"
KEY=/etc/pki/containers/nebula-os.pub
POLICY=/etc/containers/policy.json

install -Dm0644 /ctx/cosign.pub "$KEY"

# Accept images from our repository only if they carry a valid signature.
jq --arg repo "$REPO" --arg key "$KEY" \
    '.transports.docker[$repo] = [{
        "type": "sigstoreSigned",
        "keyPath": $key,
        "signedIdentity": {"type": "matchRepository"}
    }]' "$POLICY" >/tmp/policy.json
install -m0644 /tmp/policy.json "$POLICY"

# Tell podman/rpm-ostree to look for signatures stored next to the image on the registry.
install -d /etc/containers/registries.d
cat >/etc/containers/registries.d/nebula-os.yaml <<EOF
docker:
  ${REPO}:
    use-sigstore-attachments: true
EOF

echo "--- Signature policy for ${REPO}:"
jq --arg repo "$REPO" '.transports.docker[$repo]' "$POLICY"
