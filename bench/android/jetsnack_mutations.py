"""Random literal mutations of Google's Jetsnack UI code, scored against real Roborazzi failures.

    python jetsnack_mutations.py select <jetsnack-dir> <out.json>   # seed 42, 40 sites; commit before running
    python jetsnack_mutations.py run <jetsnack-dir> <sites.json> <out-dir> [ids...]
    python jetsnack_mutations.py score <jetsnack-dir> <sites.json> <out-dir>

Sites are sampled uniformly from every visual literal in app/src/main/java/**/ui/**/*.kt, so the
author doesn't choose what gets edited.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

SEED = 42
SAMPLE = 40

PATTERNS = [
    ("dp", re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\.dp\b")),
    ("sp", re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\.sp\b")),
    ("color", re.compile(r"Color\(0x([0-9A-Fa-f]{8})\)")),
    ("weight", re.compile(r"FontWeight\.(Thin|ExtraLight|Light|Normal|Medium|SemiBold|Bold|ExtraBold|Black)\b")),
    ("alpha", re.compile(r"alpha\s*=\s*(0?\.\d+|1(?:\.0)?)f\b")),
    ("maxLines", re.compile(r"maxLines\s*=\s*(\d+)\b")),
]
WEIGHTS = {"Thin": 100, "ExtraLight": 200, "Light": 300, "Normal": 400, "Medium": 500, "SemiBold": 600,
           "Bold": 700, "ExtraBold": 800, "Black": 900}


def mutate(kind: str, value: str) -> tuple[str, list[str]]:
    """New literal and the strings a correct explanation should contain."""
    if kind == "dp":
        new = float(value) + 6
        text = f"{new:g}"
        return f"{text}.dp", [f"{new:.1f}.dp", f"{text}.dp"]
    if kind == "sp":
        new = float(value) + 3
        return f"{new:g}.sp", [f"{new:g}sp", f"{new:.1f}.sp"]
    if kind == "color":
        argb = int(value, 16)
        rgb = (argb & 0xFFFFFF) ^ 0x5A5A5A
        return f"Color(0x{(argb & 0xFF000000) | rgb:08X})", [f"#{rgb:06x}"]
    if kind == "weight":
        new = "Light" if WEIGHTS[value] >= 500 else "Bold"
        return f"FontWeight.{new}", [f"weight={WEIGHTS[new]}", f"FontWeight.{new}", new]
    if kind == "alpha":
        old = float(value)
        new = round(old - 0.3 if old > 0.5 else old + 0.3, 2)
        return f"alpha = {new}f", [f"alpha={new}", str(new)]
    if kind == "maxLines":
        new = int(value) + 1 if int(value) < 3 else int(value) - 1
        return f"maxLines = {new}", [f"maxLines", str(new)]
    raise ValueError(kind)


def select(root: Path, out: Path, seed: int = SEED, exclude: Path | None = None) -> None:
    sources = sorted((root / "app/src/main/java").rglob("ui/**/*.kt"))
    sites = []
    for path in sources:
        lines = path.read_text().splitlines()
        for number, line in enumerate(lines, 1):
            if line.strip().startswith(("//", "*", "import", "@Preview")):
                continue
            for kind, pattern in PATTERNS:
                for m in pattern.finditer(line):
                    sites.append({"file": str(path.relative_to(root)), "line": number, "kind": kind,
                                  "match": m.group(0), "value": m.group(1), "col": m.start()})
    if exclude:
        taken = {(s["file"], s["line"], s["col"]) for s in json.loads(exclude.read_text())["sites"]}
        sites = [s for s in sites if (s["file"], s["line"], s["col"]) not in taken]
    rng = random.Random(seed)
    chosen = sorted(rng.sample(sites, min(SAMPLE, len(sites))), key=lambda s: (s["file"], s["line"], s["col"]))
    for i, site in enumerate(chosen, 1):
        replacement, expect = mutate(site["kind"], site["value"])
        if site["kind"] in ("dp", "sp"):
            replacement = site["match"].replace(site["value"] + ".", replacement.rsplit(".", 1)[0] + ".", 1)
        elif site["kind"] == "alpha":
            replacement = re.sub(r"(0?\.\d+|1(?:\.0)?)f", replacement.split("= ")[1], site["match"])
        elif site["kind"] == "maxLines":
            replacement = re.sub(r"\d+", replacement.split("= ")[1], site["match"])
        site.update(id=f"J{i:02d}", replacement=replacement, expect=expect)
    out.write_text(json.dumps({"seed": seed, "population": len(sites), "sites": chosen}, indent=1))
    print(f"{len(sites)} literal sites; sampled {len(chosen)} -> {out}")


def gradle(root: Path, task: str, log: Path) -> int:
    env = {**os.environ, "ANDROID_HOME": "/opt/android-sdk", "JAVA_HOME": "/usr/lib/jvm/java-21-openjdk-amd64"}
    return subprocess.run(["timeout", "1500", "bash", "./gradlew", task, "--console=plain", "-q"], cwd=root,
                          stdout=log.open("w"), stderr=subprocess.STDOUT, env=env).returncode


def run(root: Path, sites_path: Path, out: Path, only: set[str]) -> None:
    sites = json.loads(sites_path.read_text())["sites"]
    out.mkdir(parents=True, exist_ok=True)
    shots = root / "app/src/test/screenshots"
    results = root / "app/build/test-results/roborazzi"
    for site in sites:
        if only and site["id"] not in only:
            continue
        path = root / site["file"]
        original = path.read_text()
        lines = original.splitlines(keepends=True)
        line = lines[site["line"] - 1]
        assert site["match"] in line, site
        lines[site["line"] - 1] = line[:site["col"]] + line[site["col"]:].replace(site["match"], site["replacement"], 1)
        path.write_text("".join(lines))
        try:
            for f in shots.glob("*_actual.slots.json"):
                f.unlink()
            shutil.rmtree(results, ignore_errors=True)
            rc = gradle(root, ":app:compareRoborazziDebug", out / f"{site['id']}.log")
            dest = out / site["id"]
            shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir()
            changed = []
            for result in results.rglob("*.json"):
                data = json.loads(result.read_text())
                for item in data if isinstance(data, list) else [data]:
                    if isinstance(item, dict) and item.get("type") == "changed":
                        golden, actual = Path(item["golden_file_path"]), Path(item["actual_file_path"])
                        stem = golden.stem
                        shutil.copy(golden, dest / golden.name)
                        shutil.copy(actual, dest / f"{stem}_actual.png")
                        for slots in (shots / f"{stem}.slots.json", shots / f"{stem}_actual.slots.json",
                                      shots / f"{stem}.uitree.json", shots / f"{stem}_actual.uitree.json"):
                            if slots.exists():
                                shutil.copy(slots, dest / slots.name)
                        changed.append(stem)
            (dest / "meta.json").write_text(json.dumps({**site, "changed": changed, "gradle_rc": rc}))
            print(site["id"], rc, len(changed), flush=True)
        finally:
            path.write_text(original)


def score(root: Path, sites_path: Path, out: Path, noise_dir: Path | None = None) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from diffsay import compose_slots
    from diffsay import cli as diffsay
    user = compose_slots.project_files(str(root / "app"))
    sites = json.loads(sites_path.read_text())["sites"]
    rows = []
    for site in sites:
        meta_path = out / site["id"] / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        if not meta["changed"]:
            rows.append((meta, None, []))
            continue
        # Edited source tree, as a developer's checkout would be.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(root / "app/src", Path(tmp) / "src")
            path = Path(tmp) / Path(site["file"]).relative_to("app")
            lines = path.read_text().splitlines(keepends=True)
            ln = lines[site["line"] - 1]
            lines[site["line"] - 1] = ln[:site["col"]] + ln[site["col"]:].replace(site["match"], site["replacement"], 1)
            path.write_text("".join(lines))
            causes = []
            for stem in meta["changed"]:
                d = out / site["id"]
                a = diffsay.load(str(d / f"{stem}.png"))
                b = diffsay.load(str(d / f"{stem}_actual.png"))
                before, after = d / f"{stem}.slots.json", d / f"{stem}_actual.slots.json"
                ignore = None
                if noise_dir and (noise_dir / f"{stem}.slots.json").exists():
                    ignore = set(compose_slots.noise(compose_slots.load(str(noise_dir / f"{stem}.slots.json")),
                                                     compose_slots.load(str(noise_dir / f"{stem}_actual.slots.json"))))
                if before.exists() and after.exists():
                    found = compose_slots.diff(compose_slots.load(str(before)), compose_slots.load(str(after)),
                                               [c.bbox for c in diffsay.compare(a, b)], user, ignore)
                    causes += compose_slots.explain(found, user, limit=3) + compose_slots.source_hits(found, tmp)
        rows.append((meta, causes, causes))
    name = lambda f: Path(f).name
    tested = [r for r in rows if r[1] is not None]
    located = explained = named = 0
    for meta, causes, _ in rows:
        if causes is None:
            print(f"{meta['id']} NO-DIFF  {name(meta['file'])}:{meta['line']} {meta['match']} -> {meta['replacement']}")
            continue
        def at(c):
            return [int(n) for f, n in re.findall(r"([\w.]+\.kt):(-?\d+)", c) if f == name(meta["file"])]
        loc = any(meta["line"] - 8 <= n <= meta["line"] + 1 for c in causes for n in at(c))
        nam = any(k.lower() in c.lower() for k in meta["expect"] for c in causes) or any(
            k.replace(".dp", "").replace(".0", "") in re.sub(r"\.0\b", "", c) and ".dp" in c for k in meta["expect"] if ".dp" in k for c in causes)
        exp = loc and nam
        located += loc
        explained += exp
        named += nam
        mark = "EXPLAINED" if exp else "LOCATED" if loc else "MISSED"
        print(f"{meta['id']} {mark:9} {name(meta['file'])}:{meta['line']} {meta['match']} -> {meta['replacement']}  ({len(meta['changed'])} tests)")
        for c in causes[:4]:
            print(f"      {c[:150]}")
    print(f"\n{len(rows)} mutations run; {len(rows) - len(tested)} changed no preview; of {len(tested)} visible: "
          f"explained {explained}, located {located}, value named {named}, missed {len(tested) - located}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "select":
        select(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else SEED,
               Path(sys.argv[5]) if len(sys.argv) > 5 else None)
    elif cmd == "run":
        run(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), set(sys.argv[5:]))
    elif cmd == "score":
        score(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]) if len(sys.argv) > 5 else None)
