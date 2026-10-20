"""Scores cause-in-code attribution on real Roborazzi runs of source mutations.

Each mutation directory holds the golden and actual screenshots, both slot dumps, and meta.json
(file, edited line, old/new source, expected keywords). A mutation is:
  located   - a top-3 cause names the edited file at a call starting at most 6 lines above the edit
  explained - located, and a top-3 cause line contains one of the expected keywords

    python compose_eval.py <bench-dir> <module-dir-with-src>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diffsay import compose_slots  # noqa: E402
from diffsay import cli as diffsay  # noqa: E402


def main() -> None:
    bench, module = Path(sys.argv[1]), sys.argv[2]
    user = compose_slots.project_files(module)
    rows = []
    for meta_path in sorted(bench.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text())
        d = meta_path.parent
        stem = f"dev.sample.ScreensScreenshotTest.{meta['screen']}"
        golden, actual = d / f"{stem}.png", d / f"{stem}_actual.png"
        if not actual.exists():
            rows.append((meta, "no failure (pixels identical)", [], False, False, ""))
            continue
        a, b = diffsay.load(str(golden)), diffsay.load(str(actual))
        pixel = diffsay.compare(a, b)
        changes = compose_slots.diff(compose_slots.load(str(d / f"{stem}.slots.json")),
                                     compose_slots.load(str(d / f"{stem}_actual.slots.json")),
                                     [c.bbox for c in pixel], user)
        # Score against the edited source tree, as a developer's checkout would be.
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(Path(module) / "src", Path(tmp) / "src")
            edited = next(Path(tmp, "src").rglob(meta["file"]))
            edited.write_text(edited.read_text().replace(meta["old"], meta["new"]))
            causes = compose_slots.explain(changes, user, limit=3) + compose_slots.source_hits(changes, tmp)
        line = meta["edited_line"]
        span = meta["new"].count("\n") + 1
        def lines_of(c):
            return [int(n) for f, n in re.findall(r"([\w.]+\.kt):(-?\d+)", c) if f == meta["file"]]
        located = any(line - 6 <= n <= line + span for c in causes for n in lines_of(c))
        explained = located and any(k.lower() in c.lower() for k in meta["expect"] for c in causes)
        rows.append((meta, pixel[0].summary if pixel else "no change", causes, located, explained,
                     diffsay.report(pixel)))
    for meta, px, causes, located, explained, _ in rows:
        mark = "EXPLAINED" if explained else "LOCATED" if located else "MISSED"
        print(f"{meta['id']} {mark:9} edit {meta['file']}:{meta['edited_line']}  {meta['new'].strip()[:60]!r}")
        for c in causes:
            print(f"      {c[:150]}")
        if not causes:
            print(f"      (no composition cause) pixels: {px[:100]}")
    n = len(rows)
    print(f"\n{n} mutations: explained {sum(r[4] for r in rows)}, located {sum(r[3] for r in rows)}, "
          f"missed {sum(not r[3] for r in rows)}")
    words = [len(" ".join(r[2]).split()) for r in rows if r[2]]
    if words:
        print(f"cause text: median {sorted(words)[len(words) // 2]} words (~{sorted(words)[len(words) // 2] * 4 // 3} tokens)")


if __name__ == "__main__":
    main()
