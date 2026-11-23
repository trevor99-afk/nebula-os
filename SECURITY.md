# Security

## Reporting a vulnerability

Please report security problems privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue for security problems. Problems in the Bazzite base belong to [Bazzite](https://github.com/ublue-os/bazzite/security) and Universal Blue.

Only the latest image on each channel (`latest` = stable, `testing`) receives fixes.

## How NebulaOS images are protected

- **Signed images.** Every published image is signed with cosign (key-based) right after it is pushed. CI verifies the signature before moving the channel tag users follow, so an unsigned image never becomes `latest` or `testing`.
- **Signature enforcement.** The image ships a container policy that only accepts NebulaOS images signed with `/etc/pki/containers/nebula-os.pub` (its global default is `reject`). Installs from the ISO follow the signed reference from the start, and the installer **stops with an error** rather than installing without signature checks. Systems switched from Bazzite turn it on once with `ujust nebula-enable-signed-updates`.
- **Verify before you switch.** The very first switch from another system cannot be checked by that system, so verify the image yourself first:

  ```bash
  curl -fsSLO https://raw.githubusercontent.com/trevor99-afk/nebula-os/main/cosign.pub
  cosign verify --key cosign.pub ghcr.io/trevor99-afk/nebula-os:latest
  ```

- **Base security.** SELinux enforcing, Secure Boot with the Universal Blue key, firewalld, and Flatpak sandboxing are all inherited from Bazzite. NebulaOS does not weaken any of them.
- **Least privilege.** NebulaOS tools run as your user. The only system-changing commands (`nebula update apply` and `rollback`) ask for confirmation and then use rpm-ostree's own polkit authentication. Workflows have read-only permissions by default.
- **Supply chain.** GitHub Actions are pinned by commit SHA and linter images by digest. Dependabot proposes updates. A weekly Trivy scan reports known vulnerabilities to the Security tab, and an SBOM is published with each scan.
- **Pinned, verified base.** NebulaOS builds only from the Bazzite digests listed in `base-images.lock`, after verifying each one's Universal Blue signature (`keys/ublue-os.pub`), so a changed or tampered upstream image is never built and signed as NebulaOS. A daily workflow (`update-base.yml`) checks for newer Bazzite `:stable` images, verifies them and opens a pull request for review. The disk-image builder (it runs privileged) and `chunkah` are pinned by digest; disk images ship a `PROVENANCE.txt` naming the builder and the signature-verified source image.

### Known, accepted risks (inherited defaults kept on purpose)

- **The `docker` group is root-equivalent.** Bazzite DX adds administrator accounts to `docker` and `libvirt` so Docker and virtual machines work without `sudo`. Anyone who controls such an account can gain root. Prefer rootless Podman or Distrobox; remove an account from the groups with `sudo gpasswd -d USER docker` if it does not need them.
- **The firewall's desktop zone allows high ports (1025-65535).** It is Fedora Workstation's default, and Steam Remote Play, LAN games, GSConnect/KDE Connect and local development servers rely on it. Use `firewall-cmd --set-default-zone=public` for a stricter setup.
- **Some Flathub apps have broad file access** (`filesystems=host`), set by the apps' own manifests. Flatseal (in the app bundle) narrows any app's permissions.

## Privacy

NebulaOS collects no telemetry. Its tools contact the network only when you ask them to (update check) or to install the app bundle from Flathub. `nebula doctor --report` writes a local file, and includes logs only with `--include-logs`.

## For maintainers: the signing key

- `cosign.key` must never be committed (it is in `.gitignore` and `.containerignore`). CI reads it from the `SIGNING_SECRET` repository secret.
- Keep one offline copy (for example, in a password manager) and delete other copies from disk. If the key is lost or leaked: generate a new pair, update the secret and `cosign.pub`, and publish. Systems with enforcement on must then run `sudo bootc switch ghcr.io/<owner>/nebula-os:latest` once, followed by `ujust nebula-enable-signed-updates`.
