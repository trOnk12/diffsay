"""Write one failed screenshot (golden + _actual) into OUT_DIR: python tests/make_fixture.py OUT_DIR"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_diffsay import screen  # noqa: E402


def write(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(screen().astype(np.uint8)).save(out / "LoginTest.png")
    Image.fromarray(screen(radius=24).astype(np.uint8)).save(out / "LoginTest_actual.png")


if __name__ == "__main__":
    write(Path(sys.argv[1]))
