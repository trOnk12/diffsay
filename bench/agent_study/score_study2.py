import json, re, sys
from statistics import median
rows = [json.loads(l) for l in open(sys.argv[1])]
tasks = {t["id"]: t for t in json.load(open(sys.argv[2]))["tasks"]}
norm = lambda s: re.sub(r"[\s_]", "", str(s)).lower().replace("0xff", "").replace("color(", "").rstrip(")")
def parse(ans):
    for m in reversed(re.findall(r"\{.*\}", ans or "", re.S)):
        try: return json.loads(m)
        except ValueError: continue
    return None
by = {}
for r in rows:
    t, a = tasks[r["task"]], parse(r["answer"])
    h = t["hidden"]
    if a is None: ok = False
    elif h is None: ok = a.get("hidden") is None
    else:
        g = a.get("hidden") or {}
        value = re.sub(r"^alpha = ", "", h["replacement"])
        ok = (str(g.get("file", "")).split("/")[-1] == h["file"].split("/")[-1] and abs(int(g.get("line") or -99) - h["line"]) <= 3
              and norm(value) in norm(g.get("new_value", "")))
    by.setdefault(r["arm"], []).append((r["task"], ok, r["cost_usd"] or 0, r["turns"] or 0, r["seconds"]))
for arm, xs in sorted(by.items()):
    print(f"arm {arm}: correct {sum(x[1] for x in xs)}/{len(xs)}  total ${sum(x[2] for x in xs):.2f}  median ${median(x[2] for x in xs):.2f}"
          f"  median turns {median(x[3] for x in xs)}  median {median(x[4] for x in xs):.0f}s  wrong {[x[0] for x in xs if not x[1]]}")
