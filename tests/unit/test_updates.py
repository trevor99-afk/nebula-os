import json
import unittest

import helpers
from helpers import FakeRunner, fail, ok
from nebula import updates

BOOTED = "sha256:aaa"
NEWER = "sha256:bbb"


def status_json(staged=False, cached=False):
    deps = []
    if staged:
        deps.append({"booted": False, "staged": True, "pinned": False, "version": "2", "timestamp": 2000,
                     "container-image-reference": "ostree-image-signed:docker://ghcr.io/x/nebula-os:latest",
                     "container-image-reference-digest": NEWER})
    deps.append({"booted": True, "staged": False, "pinned": False, "version": "1", "timestamp": 1000,
                 "container-image-reference": "ostree-image-signed:docker://ghcr.io/x/nebula-os:latest",
                 "container-image-reference-digest": BOOTED})
    deps.append({"booted": False, "staged": False, "pinned": False, "version": "0", "timestamp": 500,
                 "container-image-reference": "ostree-unverified-registry:ghcr.io/ublue-os/bazzite-dx-gnome:stable",
                 "container-image-reference-digest": "sha256:old"})
    return json.dumps({"deployments": deps, "cached-update": {"version": "2"} if cached else None})


class ImageRef(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(updates.parse_image_ref("ostree-image-signed:docker://ghcr.io/a/b:latest"),
                         {"verification": "signed", "transport": "registry", "image": "ghcr.io/a/b:latest"})
        self.assertEqual(updates.parse_image_ref("ostree-unverified-registry:ghcr.io/a/b:latest"),
                         {"verification": "unverified", "transport": "registry", "image": "ghcr.io/a/b:latest"})
        self.assertEqual(updates.parse_image_ref("ostree-unverified-image:containers-storage:localhost/x:latest"),
                         {"verification": "unverified", "transport": "containers-storage", "image": "localhost/x:latest"})


class Status(unittest.TestCase):
    def info(self, **kw):
        return updates.deployments(FakeRunner({("rpm-ostree", "status"): ok(status_json(**kw))}))

    def test_parse(self):
        info = self.info()
        self.assertEqual(len(info["deployments"]), 2)
        self.assertEqual(info["deployments"][1]["verification"], "unverified")

    def test_summary_states(self):
        self.assertEqual(updates.summary(self.info())["state"], "not-checked")
        self.assertEqual(updates.summary(self.info(cached=True))["state"], "available")
        staged = updates.summary(self.info(staged=True))
        self.assertEqual(staged["state"], "staged")
        self.assertEqual(staged["rollback_target"]["version"], "0")
        self.assertEqual(updates.summary(None)["state"], "unknown")

    def test_remote_check(self):
        info = self.info()
        same = updates.check_remote(info, FakeRunner({("skopeo",): ok(BOOTED + "\n")}))
        self.assertEqual(same["state"], "up-to-date")
        newer = updates.check_remote(info, FakeRunner({("skopeo",): ok(NEWER + "\n")}))
        self.assertEqual(newer["state"], "available")
        err = updates.check_remote(info, FakeRunner({("skopeo",): fail(stderr="unauthorized")}))
        self.assertEqual(err["state"], "error")

    def test_remote_check_local_image(self):
        info = {"deployments": [{"booted": True, "staged": False, "transport": "containers-storage", "image": "localhost/x"}],
                "cached_update": None}
        self.assertEqual(updates.check_remote(info, FakeRunner())["state"], "unsupported")


class Confirmation(unittest.TestCase):
    def test_apply_cancelled_does_nothing(self):
        executed = []
        code = updates.apply(ask=lambda q: "n", execute=lambda cmd: executed.append(cmd) or 0)
        self.assertEqual(code, 1)
        self.assertEqual(executed, [])

    def test_apply_confirmed(self):
        executed = []
        code = updates.apply(ask=lambda q: "y", execute=lambda cmd: executed.append(cmd) or 0)
        self.assertEqual(code, 0)
        self.assertEqual(executed, [["rpm-ostree", "upgrade"]])

    def test_rollback_requires_target(self):
        info = {"deployments": [{"booted": True, "staged": False, "version": "1"}], "cached_update": None}
        executed = []
        self.assertEqual(updates.rollback(info, ask=lambda q: "y", execute=lambda c: executed.append(c) or 0), 1)
        self.assertEqual(executed, [])

    def test_rollback_confirmed(self):
        info = updates.deployments(FakeRunner({("rpm-ostree", "status"): ok(status_json())}))
        executed = []
        self.assertEqual(updates.rollback(info, ask=lambda q: "yes", execute=lambda c: executed.append(c) or 0), 0)
        self.assertEqual(executed, [["rpm-ostree", "rollback"]])

    def test_eof_means_no(self):
        def eof(_):
            raise EOFError
        executed = []
        self.assertEqual(updates.apply(ask=eof, execute=lambda c: executed.append(c) or 0), 1)
        self.assertEqual(executed, [])


if __name__ == "__main__":
    unittest.main()
