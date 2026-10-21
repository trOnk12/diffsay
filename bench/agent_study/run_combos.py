"""Applies each study-2 task's edits to JetNews, runs Roborazzi compare, keeps the failures."""
import json, os, shutil, subprocess
from pathlib import Path
root = Path(os.environ.get("JETNEWS", "JetNews"))
shots, results = root / "app/src/test/screenshots", root / "app/build/test-results/roborazzi"
tasks = json.load(open(str(Path(__file__).resolve().parents[1] / "agent_study_2_tasks.json")))["tasks"]
env = {**os.environ, "ANDROID_HOME": "/opt/android-sdk", "JAVA_HOME": "/usr/lib/jvm/java-21-openjdk-amd64"}
for t in tasks:
    edits = [e for e in (t["intended"], t["hidden"]) if e]
    originals = {}
    for e in edits:
        p = root / e["file"]
        originals.setdefault(p, p.read_text())
        L = p.read_text().splitlines(keepends=True); l = L[e["line"] - 1]
        L[e["line"] - 1] = l[:e["col"]] + l[e["col"]:].replace(e["match"], e["replacement"], 1)
        p.write_text("".join(L))
    try:
        for f in shots.glob("*_actual.slots.json"): f.unlink()
        shutil.rmtree(results, ignore_errors=True)
        rc = subprocess.run(["timeout", "1500", "bash", "./gradlew", ":app:compareRoborazziDebug", "--console=plain", "-q"],
                            cwd=root, env=env, capture_output=True).returncode
        dest = Path(os.environ.get("STUDY2_RUNS", "study2_runs")) / t["id"]; shutil.rmtree(dest, ignore_errors=True); dest.mkdir(parents=True)
        changed = []
        for r in results.rglob("*.json"):
            d = json.loads(r.read_text())
            for i in d if isinstance(d, list) else [d]:
                if isinstance(i, dict) and i.get("type") == "changed":
                    g, a = Path(i["golden_file_path"]), Path(i["actual_file_path"])
                    shutil.copy(g, dest / g.name); shutil.copy(a, dest / f"{g.stem}_actual.png")
                    for s in (shots / f"{g.stem}.slots.json", shots / f"{g.stem}_actual.slots.json"):
                        if s.exists(): shutil.copy(s, dest / s.name)
                    changed.append(g.stem)
        (dest / "meta.json").write_text(json.dumps({**t, "changed": changed, "rc": rc}))
        print(t["id"], rc, len(changed), flush=True)
    finally:
        for p, text in originals.items(): p.write_text(text)
print("DONE")
