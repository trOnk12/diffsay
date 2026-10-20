import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diffsay import cli  # noqa: E402


class InitTest(unittest.TestCase):
    def test_copies_the_recorder_and_prints_gradle_lines_with_the_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            (app / "src/test/kotlin").mkdir(parents=True)
            (app / "build.gradle.kts").write_text('android {\n    namespace = "com.acme.shop"\n}\n')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(0, cli.main(["init", str(app)]))
            for name in ("SlotRecorder.kt", "DiffsayPreviewTester.kt"):
                self.assertIn("package dev.diffsay", (app / "src/test/kotlin/dev/diffsay" / name).read_text())
            self.assertIn('packages = listOf("com.acme.shop")', out.getvalue())
            self.assertIn('testerQualifiedClassName = "dev.diffsay.DiffsayPreviewTester"', out.getvalue())

    def test_refuses_a_directory_that_is_not_a_module(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, cli.main(["init", tmp]))


if __name__ == "__main__":
    unittest.main()
