import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASH = shutil.which("bash")  # a bare "bash" on Windows resolves to WSL's, not the one on PATH
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fixture import write  # noqa: E402

FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$GH_LOG"
if [ -n "$GH_FAIL" ]; then exit 1; fi
case "$*" in api\ --method*) ;; api\ *) printf '%s' "$GH_EXISTING";; esac
"""


def bash(script: str, env: dict, cwd: str) -> subprocess.CompletedProcess:
    path = os.pathsep.join([env.pop("EXTRA_PATH", ""), str(Path(sys.executable).parent), os.environ["PATH"]])
    return subprocess.run([BASH, (ROOT / "scripts/action" / script).as_posix()], cwd=cwd, capture_output=True,
                          text=True, env={**os.environ, **env, "PATH": path})


def outputs(path: Path) -> dict:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


class RunScriptTest(unittest.TestCase):
    def scan(self, tmp: Path, base_ref: str = "", fixture: bool = True):
        fx = tmp / "fx"
        if fixture:
            write(fx)
        else:
            fx.mkdir()
        env = {"MODULE_DIR": str(fx), "SOURCE": str(fx), "BASE_REF": base_ref, "RUNNER_TEMP": str(tmp),
               "GITHUB_OUTPUT": str(tmp / "out"), "GITHUB_STEP_SUMMARY": str(tmp / "summary")}
        return bash("run.sh", env, str(tmp))

    def test_changed_screenshot_sets_outputs_and_summary(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            r = self.scan(tmp)
            self.assertEqual(0, r.returncode, r.stderr)
            out = outputs(tmp / "out")
            self.assertEqual("true", out["changed"])
            self.assertTrue(Path(out["causes-file"]).read_text().startswith("### "))
            self.assertIn("### ", (tmp / "summary").read_text())

    def test_no_failures_reports_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            r = self.scan(tmp, fixture=False)
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertEqual("false", outputs(tmp / "out")["changed"])

    def test_missing_base_ref_warns_and_still_scans(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            r = self.scan(tmp, base_ref="main")  # tmp is not a git repo
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertIn("::warning::diffsay: base ref unavailable", r.stdout)
            self.assertEqual("true", outputs(tmp / "out")["changed"])

    def test_scan_crash_fails_the_step_instead_of_reporting_a_change(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            fx = tmp / "fx"
            fx.mkdir()
            (fx / "LoginTest.png").write_bytes(b"not a png")
            (fx / "LoginTest_actual.png").write_bytes(b"not a png either")
            env = {"MODULE_DIR": str(fx), "SOURCE": str(fx), "BASE_REF": "", "RUNNER_TEMP": str(tmp),
                   "GITHUB_OUTPUT": str(tmp / "out"), "GITHUB_STEP_SUMMARY": str(tmp / "summary")}
            r = bash("run.sh", env, str(tmp))
            self.assertNotEqual(0, r.returncode)
            self.assertIn("::error::", r.stdout)

    def test_missing_module_dir_fails_instead_of_reporting_no_changes(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            env = {"MODULE_DIR": str(tmp / "typo"), "SOURCE": "", "BASE_REF": "", "RUNNER_TEMP": str(tmp),
                   "GITHUB_OUTPUT": str(tmp / "out"), "GITHUB_STEP_SUMMARY": str(tmp / "summary")}
            r = bash("run.sh", env, str(tmp))
            self.assertNotEqual(0, r.returncode)
            self.assertIn("::error::diffsay: module-dir", r.stdout)

    def test_base_ref_already_present_is_used_without_fetching(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            git = ["git", "-C", str(tmp), "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run(git[:3] + ["init", "-q"], check=True)
            subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "base"], check=True)
            subprocess.run(git[:3] + ["update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
            r = self.scan(tmp, base_ref="main")  # no remote configured: any fetch would fail
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertNotIn("base ref unavailable", r.stdout)
            self.assertFalse((tmp / ".git/shallow").exists())


class CommentScriptTest(unittest.TestCase):
    def comment(self, tmp: Path, changed: str, existing: str = "", fail: bool = False):
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH, newline="\n")
        (bin_dir / "gh").chmod(0o755)
        causes = tmp / "causes.md"
        causes.write_text("### 1 screenshot test(s) changed\n")
        env = {"EXTRA_PATH": str(bin_dir), "GH_LOG": str(tmp / "gh.log"), "GH_EXISTING": existing,
               "GH_FAIL": "1" if fail else "", "REPO": "o/r", "PR": "7", "CHANGED": changed,
               "CAUSES_FILE": str(causes), "GH_TOKEN": "x"}
        r = bash("comment.sh", env, str(tmp))
        log = (tmp / "gh.log").read_text() if (tmp / "gh.log").exists() else ""
        return r, log

    def test_first_change_creates_one_comment(self):
        with tempfile.TemporaryDirectory() as t:
            r, log = self.comment(Path(t), "true")
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertIn("pr comment 7", log)

    def test_later_push_edits_the_existing_comment(self):
        with tempfile.TemporaryDirectory() as t:
            r, log = self.comment(Path(t), "true", existing="123")
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertIn("repos/o/r/issues/comments/123", log)
            self.assertNotIn("pr comment", log)

    def test_clean_push_rewrites_a_stale_comment(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            r, log = self.comment(tmp, "false", existing="123")
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertIn("repos/o/r/issues/comments/123", log)
            self.assertIn("No screenshot changes", (tmp / "body.md").read_text())

    def test_clean_push_without_a_comment_posts_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            r, log = self.comment(Path(t), "false")
            self.assertEqual(0, r.returncode, r.stderr)
            self.assertNotIn("pr comment", log)
            self.assertNotIn("--method", log)

    def test_gh_failure_warns_and_keeps_the_job_green(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = self.comment(Path(t), "true", fail=True)
            self.assertEqual(0, r.returncode)
            self.assertIn("::warning::diffsay: could not comment", r.stdout)


if __name__ == "__main__":
    unittest.main()
