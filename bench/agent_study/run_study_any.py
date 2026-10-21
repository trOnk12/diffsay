"""Runs the pre-registered agent study: each task once per arm with `claude -p`."""
import json, subprocess, sys, time
from pathlib import Path
ROOT = Path(sys.argv[1])
BASE = ("Screenshot tests of this Android app (Jetpack Compose) failed after somebody changed code in app/src. "
        "The failed screenshots are in screenshots/: <name>.png is the golden (expected) image and "
        "<name>_actual.png is what the app renders now. Find the code change that caused the failures. "
        "You can't build or run the app, and there is no version control history. ")
TOOL = ("A tool is installed for exactly this: run `diffsay scan screenshots --source app` "
        "(it reads the composition dumps, *.slots.json, saved beside the screenshots). ")
ASK = ('When you are done, reply with only a JSON object: {"file": "<file name>", "line": <line number>, '
       '"new_value": "<the changed value as it is written in the code now>"}')
tasks = json.load(open(sys.argv[2]))["tasks"]
out = ROOT / "results.jsonl"
done = {(r["arm"], r["task"]) for r in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
for task in tasks:
    for arm in ("A", "B"):
        if (arm, task) in done:
            continue
        prompt = BASE + (TOOL if arm == "B" else "") + ASK
        tools = "Read,Grep,Glob" + (",Bash(diffsay scan:*)" if arm == "B" else "")
        start = time.time()
        p = subprocess.run(["timeout", "1200", "claude", "-p", prompt, "--output-format", "json",
                            "--allowedTools", tools, "--max-turns", "40"],
                           cwd=ROOT / arm / task, capture_output=True, text=True)
        try:
            res = json.loads(p.stdout)
        except ValueError:
            res = {"result": p.stdout[-2000:], "error": p.stderr[-2000:]}
        row = {"arm": arm, "task": task, "seconds": round(time.time() - start, 1),
               "cost_usd": res.get("total_cost_usd"), "turns": res.get("num_turns"),
               "usage": res.get("usage"), "answer": res.get("result"), "rc": p.returncode}
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(arm, task, row["seconds"], row["cost_usd"], row["turns"], str(row["answer"])[-150:], flush=True)
