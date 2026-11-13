import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
GUARD = Path(__file__).resolve().parents[1] / "scripts/check_tag_version.py"


def run(tag: str) -> int:
    return subprocess.run([sys.executable, str(GUARD), tag], capture_output=True).returncode


class TagGuardTest(unittest.TestCase):
    def test_tag_equal_to_package_version_passes(self):
        from diffsay import __version__
        self.assertEqual(0, run(f"v{__version__}"))

    def test_tag_ahead_of_package_version_fails(self):
        self.assertEqual(1, run("v99.0.0"))


class ReleaseWorkflowTest(unittest.TestCase):
    def setUp(self):
        import yaml
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text()
        self.wf = yaml.safe_load(text)
        self.on = self.wf.get("on", self.wf.get(True))  # YAML 1.1 reads a bare `on` key as True

    def test_moving_the_action_major_tag_does_not_trigger_a_release(self):
        from fnmatch import fnmatch
        patterns = self.on["push"]["tags"]
        self.assertFalse(any(fnmatch("v0", p) for p in patterns))
        self.assertTrue(any(fnmatch("v0.3.0", p) for p in patterns))

    def test_tests_run_before_the_package_is_built(self):
        runs = [s.get("run", "") for s in self.wf["jobs"]["build"]["steps"]]
        test_at = next(i for i, r in enumerate(runs) if "unittest discover" in r)
        build_at = next(i for i, r in enumerate(runs) if "python -m build" in r)
        self.assertLess(test_at, build_at)


if __name__ == "__main__":
    unittest.main()
