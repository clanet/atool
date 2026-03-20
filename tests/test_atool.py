import importlib.util
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
ATOOL_PATH = REPO_ROOT / "atool"


def load_atool_module():
    loader = SourceFileLoader("atool_module", str(ATOOL_PATH))
    spec = importlib.util.spec_from_loader("atool_module", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AtoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atool = load_atool_module()

    def test_read_file_returns_requested_line_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

            with mock.patch.object(self.atool, "_read_text_file", side_effect=AssertionError("read_file should stream")):
                result = self.atool.read_file(str(path), start_line=2, max_lines=2)

            self.assertEqual(result["content"], "two\nthree\n")
            self.assertEqual(result["start_line"], 2)
            self.assertEqual(result["end_line"], 3)
            self.assertEqual(result["total_lines"], 4)
            self.assertTrue(result["truncated"])

    def test_search_text_recurses_directory_and_limits_matches_in_stable_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "b.txt").write_text("Alpha\nbeta\n", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "a.txt").write_text("gamma\nALPHA\nalpha\n", encoding="utf-8")

            with mock.patch.object(self.atool, "_read_text_file", side_effect=AssertionError("search_text should stream")):
                result = self.atool.search_text(str(root), "alpha", max_matches=2)

            self.assertEqual(result["count"], 2)
            self.assertTrue(result["truncated"])
            self.assertEqual(
                [(Path(m["path"]).name, m["line"]) for m in result["matches"]],
                [("b.txt", 1), ("a.txt", 2)],
            )

    def test_list_dir_hides_hidden_entries_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "visible.txt").write_text("x\n", encoding="utf-8")
            (root / ".hidden.txt").write_text("y\n", encoding="utf-8")

            hidden_default = self.atool.list_dir(str(root))
            hidden_shown = self.atool.list_dir(str(root), show_hidden=True)

            self.assertEqual([entry["name"] for entry in hidden_default["entries"]], ["visible.txt"])
            self.assertEqual(
                sorted(entry["name"] for entry in hidden_shown["entries"]),
                [".hidden.txt", "visible.txt"],
            )

    def test_execute_command_respects_cwd_and_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd_result = self.atool.execute_command(
                f"{sys.executable} -c \"import os; print(os.getcwd())\"",
                cwd=tmpdir,
                shell=False,
            )
            self.assertEqual(cwd_result["returncode"], 0)
            self.assertEqual(cwd_result["stdout"].strip(), tmpdir)

            timeout_result = self.atool.execute_command(
                f"{sys.executable} -c \"import time; time.sleep(2)\"",
                timeout_sec=1,
                shell=False,
            )
            self.assertEqual(timeout_result["returncode"], -1)
            self.assertIn("timed out (1s)", timeout_result["stderr"])

    def test_execute_command_replaces_non_utf8_output(self):
        result = self.atool.execute_command(
            f"{sys.executable} -c \"import sys; sys.stdout.buffer.write(bytes([255]))\"",
            shell=False,
        )

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "\ufffd")
        self.assertEqual(result["stderr"], "")

    def test_execute_command_timeout_kills_child_process_group(self):
        if self.atool.IS_WINDOWS:
            self.skipTest("process-group timeout cleanup test is POSIX-specific")

        marker = f"atool_orphan_marker_{os.getpid()}_{time.time_ns()}"
        cmd = f"sh -c '{sys.executable} -c \"import time; time.sleep(30)\" {marker} & wait'"
        result = self.atool.execute_command(cmd, shell=True, timeout_sec=1)
        self.assertEqual(result["returncode"], -1)
        self.assertIn("timed out (1s)", result["stderr"])

        time.sleep(0.2)
        probe = subprocess.run(
            ["pgrep", "-f", marker],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertNotEqual(probe.returncode, 0, f"timed-out child process still running: {probe.stdout!r}")
        finally:
            for pid_text in probe.stdout.split():
                try:
                    os.kill(int(pid_text), signal.SIGKILL)
                except OSError:
                    pass

    def test_write_file_over_existing_file_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.txt"
            path.write_text("old\n", encoding="utf-8")
            os.chmod(path, 0o640)

            result = self.atool.write_file(str(path), "new\n")

            self.assertTrue(result["success"])
            self.assertTrue(result["changed"])
            self.assertFalse(result["created"])
            self.assertTrue(result["backup_path"])
            self.assertEqual(path.read_text(encoding="utf-8"), "new\n")
            self.assertEqual(Path(result["backup_path"]).read_text(encoding="utf-8"), "old\n")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o640)

    def test_patch_file_creates_backup_before_modifying_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.txt"
            path.write_text("alpha\nbeta\n", encoding="utf-8")

            result = self.atool.patch_file(str(path), [
                {"action": "replace", "target_text": "beta\n", "new_text": "beta2\n"}
            ])

            self.assertTrue(result["success"])
            self.assertTrue(result["changed"])
            self.assertTrue(result["backup_path"])
            self.assertEqual(path.read_text(encoding="utf-8"), "alpha\nbeta2\n")
            self.assertEqual(Path(result["backup_path"]).read_text(encoding="utf-8"), "alpha\nbeta\n")

    def test_yes_flag_skips_medium_but_not_high_confirmation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_path = Path(tmpdir) / "file.txt"
            existing_path.write_text("content\n", encoding="utf-8")
            new_path = Path(tmpdir) / "new-file.txt"

            medium_args = {
                "path": str(new_path),
                "content": "new\n",
                "sensitivity": "medium",
            }
            high_args = dict(medium_args, path=str(existing_path), sensitivity="high")

            with mock.patch("builtins.input") as fake_input:
                self.assertTrue(self.atool.confirm_action("write_file", medium_args, auto_yes=True))
                fake_input.assert_not_called()

            with mock.patch("builtins.input", return_value="n") as fake_input:
                self.assertFalse(self.atool.confirm_action("write_file", high_args, auto_yes=True))
                fake_input.assert_called_once()


if __name__ == "__main__":
    unittest.main()
