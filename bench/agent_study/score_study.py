import json, re, sys
from statistics import median
rows = [json.loads(l) for l in open(sys.argv[1])]
truth = json.loads(open(sys.argv[2]).read())  # id -> {file, line, value}
def parse(ans):
    m = re.findall(r"\{[^{}]*\}", ans or "")
    try:
        return json.loads(m[-1]) if m else {}
    except ValueError:
        return {}
norm = lambda s: re.sub(r"[\s_]", "", str(s)).lower().replace("0xff", "").replace(".0f", "f")
out = {}
for r in rows:
    a, t = parse(r["answer"]), truth[r["task"]]
    ok = (str(a.get("file", "")).split("/")[-1] == t["file"] and abs(int(a.get("line") or -99) - t["line"]) <= 3
          and norm(t["value"]) in norm(a.get("new_value", "")))
    out.setdefault(r["arm"], []).append((r["task"], ok, r["cost_usd"] or 0, r["turns"] or 0, r["seconds"]))
for arm, xs in sorted(out.items()):
    print(f"arm {arm}: correct {sum(x[1] for x in xs)}/{len(xs)}  cost total ${sum(x[2] for x in xs):.2f} "
          f"median ${median(x[2] for x in xs):.3f}  median turns {median(x[3] for x in xs)}  median {median(x[4] for x in xs)}s")
    print("   wrong:", [x[0] for x in xs if not x[1]])
