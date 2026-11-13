"""Exit 1 unless the release tag (v-prefixed) equals diffsay.__version__. Reads the file; no import."""
import ast
import pathlib
import sys


def package_version(root: pathlib.Path) -> str:
    tree = ast.parse((root / "src/diffsay/__init__.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "__version__":
            return node.value.value
    raise SystemExit("no __version__ in src/diffsay/__init__.py")


if __name__ == "__main__":
    tag = sys.argv[1].removeprefix("v")
    version = package_version(pathlib.Path(__file__).resolve().parents[1])
    if tag != version:
        print(f"::error::tag v{tag} does not match __version__ {version}")
        sys.exit(1)
    print(f"tag matches version {version}")
