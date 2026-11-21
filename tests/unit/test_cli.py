import json
import os
import shutil
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (puts the nebula package on the import path)
from nebula import cli


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


class WriteReport(unittest.TestCase):
    def setUp(self):
        for target, name, value in ((cli.hardware, "report", {}), (cli.sysinfo, "os_info", {})):
            patcher = mock.patch.object(target, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def write(self, path):
        with redirect_stdout(StringIO()):
            cli.write_report(str(path), [], False)

    def test_new_file_is_private(self):
        path = self.tmp / "r.json"
        self.write(path)
        self.assertEqual(mode(path), 0o600)
        self.assertEqual(json.loads(path.read_text())["schema"], "nebula.doctor-report/v1")

    def test_existing_readable_file_becomes_private(self):
        path = self.tmp / "r.json"
        path.write_text("old")
        path.chmod(0o644)
        self.write(path)
        self.assertEqual(mode(path), 0o600)
        self.assertEqual(json.loads(path.read_text())["schema"], "nebula.doctor-report/v1")

    def test_symlink_is_refused(self):
        target = self.tmp / "target"
        target.write_text("keep")
        link = self.tmp / "r.json"
        link.symlink_to(target)
        with self.assertRaises(OSError):
            self.write(link)
        self.assertEqual(target.read_text(), "keep")
        self.assertTrue(link.is_symlink())

    def test_directory_is_refused(self):
        (self.tmp / "dir").mkdir()
        with self.assertRaises(OSError):
            self.write(self.tmp / "dir")
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["dir"])

    def test_failed_write_leaves_no_temp_file(self):
        with mock.patch.object(cli.os, "replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.write(self.tmp / "r.json")
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_main_reports_write_errors_without_a_traceback(self):
        err = StringIO()
        with mock.patch.object(cli.doctor, "diagnose", return_value=[]), \
                redirect_stdout(StringIO()), redirect_stderr(err):
            code = cli.main(["doctor", "--report", str(self.tmp / "missing" / "r.json")])
        self.assertEqual(code, 2)
        self.assertIn("Could not write the report", err.getvalue())


if __name__ == "__main__":
    unittest.main()
