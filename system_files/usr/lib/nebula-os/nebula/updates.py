"""Updates, deployments and rollback (rpm-ostree / bootc).

Read-only functions use `rpm-ostree status --json` and `skopeo inspect`.
apply() and rollback() change the system, so they always ask for confirmation
first and then hand over to rpm-ostree, which asks for authentication itself.
"""

from __future__ import annotations

import json
import time
from typing import Callable, Dict, List, Optional

from .util import Runner, run, run_interactive


def parse_image_ref(ref: str) -> Dict[str, Optional[str]]:
    """Split an ostree container reference into verification, transport, image."""
    verification = "unknown"
    rest = ref or ""
    for prefix, kind in (("ostree-image-signed:", "signed"), ("ostree-unverified-registry:", "unverified"),
                         ("ostree-unverified-image:", "unverified"), ("ostree-remote-image:", "signed")):
        if rest.startswith(prefix):
            verification = kind
            rest = rest[len(prefix):]
            if prefix == "ostree-unverified-registry:":
                rest = "docker://" + rest
            elif prefix == "ostree-remote-image:":
                rest = rest.split(":", 1)[1] if ":" in rest else rest
            break
    transport = image = None
    if rest.startswith("docker://"):
        transport, image = "registry", rest[len("docker://"):]
    elif rest.startswith("registry:"):
        transport, image = "registry", rest[len("registry:"):]
    elif rest.startswith("containers-storage:"):
        transport, image = "containers-storage", rest[len("containers-storage:"):]
    elif rest:
        image = rest
    return {"verification": verification, "transport": transport, "image": image}


def deployments(runner: Runner = run) -> Optional[Dict[str, object]]:
    res = runner(["rpm-ostree", "status", "--json"], timeout=30)
    if not res.ok:
        return None
    try:
        data = json.loads(res.stdout)
    except ValueError:
        return None
    result: List[Dict[str, object]] = []
    for dep in data.get("deployments", []):
        ref = dep.get("container-image-reference") or ""
        parsed = parse_image_ref(ref)
        result.append({
            "id": dep.get("id"),
            "booted": bool(dep.get("booted")),
            "staged": bool(dep.get("staged")),
            "pinned": bool(dep.get("pinned")),
            "version": dep.get("version"),
            "timestamp": dep.get("timestamp"),
            "image_ref": ref,
            "image": parsed["image"],
            "transport": parsed["transport"],
            "verification": parsed["verification"],
            "digest": dep.get("container-image-reference-digest"),
        })
    cached = data.get("cached-update")
    cached_summary = None
    if isinstance(cached, dict):
        cached_summary = {"version": cached.get("version"), "digest": cached.get("container-image-reference-digest")}
    return {"deployments": result, "cached_update": cached_summary}


def _pick(deps: List[Dict[str, object]], **match: bool) -> Optional[Dict[str, object]]:
    return next((d for d in deps if all(d.get(k) == v for k, v in match.items())), None)


def summary(info: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Local update state (no network)."""
    if not info:
        return {"state": "unknown", "message": "rpm-ostree status is not available here."}
    deps = info["deployments"]  # type: ignore[index]
    booted = _pick(deps, booted=True)
    staged = _pick(deps, staged=True)
    rollback = next((d for d in deps if not d["booted"] and not d["staged"]), None)
    if staged:
        state, message = "staged", f"Update {staged.get('version')} is ready. Restart to apply it."
    elif info.get("cached_update"):
        state, message = "available", "An update is available."
    else:
        state, message = "not-checked", "No update downloaded. Run `nebula update check` to ask the server."
    return {
        "state": state,
        "message": message,
        "booted": booted,
        "staged": staged,
        "rollback_target": rollback,
    }


def check_remote(info: Optional[Dict[str, object]], runner: Runner = run) -> Dict[str, object]:
    """Compare the booted image digest with the registry. Contacts the registry."""
    if not info:
        return {"state": "unknown", "message": "rpm-ostree status is not available here."}
    deps = info["deployments"]  # type: ignore[index]
    booted = _pick(deps, booted=True)
    if not booted or booted.get("transport") != "registry":
        return {"state": "unsupported", "message": "The running system was not installed from a registry image "
                "(for example a local test build), so there is nothing to compare against."}
    image = str(booted["image"])
    res = runner(["skopeo", "inspect", "--no-tags", "--format", "{{.Digest}}", f"docker://{image}"], timeout=90)
    if not res.ok:
        return {"state": "error", "image": image, "message": (res.stderr or "skopeo failed").strip()[:300]}
    remote = res.stdout.strip()
    staged = _pick(deps, staged=True)
    if remote == booted.get("digest"):
        state, message = "up-to-date", "You are running the newest image."
    elif staged and remote == staged.get("digest"):
        state, message = "staged", "The newest image is already downloaded. Restart to apply it."
    else:
        state, message = "available", "A newer image is available. Run `nebula update apply` (or `ujust update`)."
    return {"state": state, "message": message, "image": image, "booted_digest": booted.get("digest"), "remote_digest": remote}


def _ask(question: str, assume_yes: bool, ask: Callable[[str], str]) -> bool:
    if assume_yes:
        return True
    try:
        return ask(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def apply(assume_yes: bool = False, ask: Callable[[str], str] = input,
          execute: Callable[[List[str]], int] = run_interactive) -> int:
    print("This downloads the newest NebulaOS image and prepares it for the next restart.\n"
          "Your current system stays in the boot menu, so you can go back at any time.")
    if not _ask("Download and stage the update now?", assume_yes, ask):
        print("Cancelled. Nothing was changed.")
        return 1
    code = execute(["rpm-ostree", "upgrade"])
    if code == 0:
        print("Done. Restart to start the updated system.")
    return code


def rollback(info: Optional[Dict[str, object]], assume_yes: bool = False, ask: Callable[[str], str] = input,
             execute: Callable[[List[str]], int] = run_interactive) -> int:
    state = summary(info)
    target = state.get("rollback_target")
    booted = state.get("booted")
    if not target:
        print("There is no previous deployment to go back to.")
        return 1
    print(f"Current:   {booted.get('version') if booted else '?'}  {booted.get('image') if booted else ''}")
    print(f"Go back to: {target.get('version')}  {target.get('image')}  ({_when(target.get('timestamp'))})")
    print("After the restart the previous system starts; the current one stays available in the boot menu.")
    if not _ask("Make the previous deployment the default for the next restart?", assume_yes, ask):
        print("Cancelled. Nothing was changed.")
        return 1
    code = execute(["rpm-ostree", "rollback"])
    if code == 0:
        print("Done. Restart to boot the previous deployment.")
    return code


def _when(timestamp: object) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(timestamp)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown date"
