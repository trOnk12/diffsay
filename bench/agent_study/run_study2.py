import json, os, subprocess, time
from pathlib import Path
ROOT = Path(os.environ.get("STUDY2_DIR", "study2"))
BASE = ("You are reviewing a pull request to this Android app (Jetpack Compose); the code is in app/src. "
        "PR.md describes the change the PR intends. Its screenshot tests failed: in screenshots/, <name>.png is the "
        "golden (expected) image and <name>_actual.png is what the app renders now. The branch may also contain "
        "other, unintended changes; there is no version control history and you can't build or run the app. "
        "Decide whether every screenshot change is explained by the intended change. ")
TOOL = ("A tool is installed for exactly this: run `diffsay scan screenshots --source app` "
        "(it reads the composition dumps, *.slots.json, saved beside the screenshots). ")
ASK = ('When you are done, reply with only a JSON object: {"hidden": null} if the intended change explains every '
       'screenshot change, or {"hidden": {"file": "<file name>", "line": <line number>, "new_value": "<the changed '
       'value as written in the code now>"}} for the unintended change.')
tasks = [t["id"] for t in json.load(open(str(Path(__file__).resolve().parents[1] / "agent_study_2_tasks.json")))["tasks"]]
out = ROOT / "results.jsonl"
done = {(r["arm"], r["task"]) for r in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
for task in sorted(tasks):
    for arm in ("A", "B"):
        if (arm, task) in done: continue
        start = time.time()
        p = subprocess.run(["timeout", "1800", "claude", "-p", BASE + (TOOL if arm == "B" else "") + ASK,
                            "--output-format", "json", "--allowedTools",
                            "Read,Grep,Glob" + (",Bash(diffsay scan:*)" if arm == "B" else ""), "--max-turns", "60"],
                           cwd=ROOT / arm / task, capture_output=True, text=True)
        try: res = json.loads(p.stdout)
        except ValueError: res = {"result": p.stdout[-2000:]}
        row = {"arm": arm, "task": task, "seconds": round(time.time() - start, 1), "cost_usd": res.get("total_cost_usd"),
               "turns": res.get("num_turns"), "usage": res.get("usage"), "answer": res.get("result"), "rc": p.returncode}
        with out.open("a") as f: f.write(json.dumps(row) + "\n")
        print(arm, task, row["seconds"], row["cost_usd"], row["turns"], str(row["answer"])[-160:].replace("\n", " "), flush=True)
