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


if __name__ == "__main__":
    unittest.main()
