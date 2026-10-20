"""Scores diffsay on DiffSpot pairs with a strict rule-based judge.

A pair counts as correct only if diffsay's primary change names the mutated property
(and its direction, where the benchmark records one) and its region overlaps the
mutated element. No-diff pairs are correct only if diffsay reports no change.

    python diffspot_eval.py <pairs-dir> <index.json> --split dev|test [--show N]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diffsay import cli as diffsay  # noqa: E402

KINDS = {
    "position": {"moved"}, "justify": {"alignment"}, "spacing": {"spacing"}, "text": {"text"},
    "font_size": {"font-size"}, "font_weight": {"font-weight"}, "letter_spacing": {"letter-spacing"},
    "line_height": {"line-height"}, "color": {"text-color", "fill-color"}, "border": {"border-color"},
    "opacity": {"opacity"}, "rounded": {"rounded"}, "gradient": {"gradient"}, "none": set(),
}


def direction_ok(row: dict, change: diffsay.Change) -> bool:
    want = row["direction"] or ""
    if not want or row["op"] in ("spacing",) and want not in ("increased", "decreased"):
        return True
    if row["op"] == "position":
        n, d = re.match(r"(\d+)px (\w+)", want).groups()
        dx, dy = change.evidence.get("dx", 0), change.evidence.get("dy", 0)
        got = {"left": -dx, "right": dx, "up": -dy, "down": dy}[d]
        return abs(got - int(n)) <= 2
    if row["op"] == "opacity":
        return True
    return change.direction == want


def overlaps(row: dict, change: diffsay.Change) -> bool:
    x, y, w, h = row["bbox"]
    cx, cy, cw, ch = change.bbox
    return cx < x + w + 8 and x < cx + cw + 8 and cy < y + h + 8 and y < cy + ch + 8


def judge(args) -> dict:
    pairs, row = args
    changes = diffsay.compare(diffsay.load(f"{pairs}/{row['name']}_a.png"), diffsay.load(f"{pairs}/{row['name']}_b.png"))
    if row["op"] == "none":
        return {**row, "ok": not changes, "kind": changes[0].kind if changes else "none", "summary": diffsay.report(changes)}
    if not changes:
        return {**row, "ok": False, "kind": "none", "summary": "no visible change"}
    primary = changes[0]
    ok = primary.kind in KINDS[row["op"]] and direction_ok(row, primary) and overlaps(row, primary)
    return {**row, "ok": ok, "kind": primary.kind, "kind_ok": primary.kind in KINDS[row["op"]],
            "located": overlaps(row, primary), "summary": diffsay.report(changes)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs")
    parser.add_argument("index")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--show", type=int, default=0, help="print N failures per operator")
    parser.add_argument("--only", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    rows = [r for r in json.load(open(args.index)) if r["split"] == args.split and (not args.only or r["op"] == args.only)]
    start = time.time()
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(judge, [(args.pairs, r) for r in rows], chunksize=4))
    elapsed = time.time() - start
    by = collections.defaultdict(list)
    for r in results:
        by[r["op"]].append(r)
    print(f"{args.split}: {len(results)} pairs in {elapsed:.0f}s")
    print(f"{'operator':15} {'easy':>6} {'med':>6} {'hard':>6} {'all':>6}   top predicted kinds")
    diff_rows = [r for r in results if r["op"] != "none"]
    for op in sorted(by):
        rs = by[op]
        cells = []
        for tier in ("easy", "medium", "hard"):
            t = [r for r in rs if r["difficulty"] == tier]
            cells.append(f"{100 * sum(r['ok'] for r in t) / len(t):5.1f}" if t else "    -")
        kinds = collections.Counter(r["kind"] for r in rs).most_common(3)
        print(f"{op:15} {cells[0]:>6} {cells[1]:>6} {cells[2]:>6} {100 * sum(r['ok'] for r in rs) / len(rs):6.1f}   {kinds}")
    tiers = {t: [r for r in diff_rows if r["difficulty"] == t] for t in ("easy", "medium", "hard")}
    nd = by.get("none", [])
    print(f"\nRecall easy {100 * sum(r['ok'] for r in tiers['easy']) / max(1, len(tiers['easy'])):.1f} · "
          f"medium {100 * sum(r['ok'] for r in tiers['medium']) / max(1, len(tiers['medium'])):.1f} · "
          f"hard {100 * sum(r['ok'] for r in tiers['hard']) / max(1, len(tiers['hard'])):.1f} · "
          f"diff overall {100 * sum(r['ok'] for r in diff_rows) / max(1, len(diff_rows)):.1f} · "
          f"no-diff {100 * sum(r['ok'] for r in nd) / max(1, len(nd)):.1f} · "
          f"overall {100 * sum(r['ok'] for r in results) / len(results):.1f} · "
          f"located {100 * sum(r.get('located', False) for r in diff_rows) / max(1, len(diff_rows)):.1f}")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1))
    for op in sorted(by):
        bad = [r for r in by[op] if not r["ok"]][: args.show]
        for r in bad:
            print(f"\n[{op}/{r['difficulty']}] {r['name']} want {r['property']} {r['direction']} ({r['old']} -> {r['new']}) bbox {r['bbox']}\n  {r['summary']}")


if __name__ == "__main__":
    main()
