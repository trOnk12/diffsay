"""Downloads DiffSpot (MIT) and writes before/after PNG pairs plus index.json with the dev/test split.

    python prepare_diffspot.py <out-dir>
"""

from __future__ import annotations

import collections
import json
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

SEED = 20261020
DEV_PER_CELL = 8


def main() -> None:
    out = Path(sys.argv[1])
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    parquet = hf_hub_download("tencent/DiffSpot", "test-00000-of-00001.parquet", repo_type="dataset", local_dir=out)
    meta = pq.read_table(parquet, columns=["mutation_types", "mutation_dicts_json", "difficulty", "pixel_diff",
                                           "target_bbox_x", "target_bbox_y", "target_bbox_w", "target_bbox_h"]).to_pylist()
    order = list(range(len(meta)))
    random.Random(SEED).shuffle(order)
    seen: collections.Counter = collections.Counter()
    split = {}
    for i in order:
        cell = ((meta[i]["mutation_types"] or ["none"])[0], meta[i]["difficulty"])
        seen[cell] += 1
        split[i] = "dev" if seen[cell] <= DEV_PER_CELL else "test"
    index, row = [], 0
    pf = pq.ParquetFile(parquet)
    for group in range(pf.num_row_groups):
        for images in pf.read_row_group(group, columns=["image_before", "image_after"]).to_pylist():
            m = meta[row]
            name = f"{row:04d}"
            (out / "pairs" / f"{name}_a.png").write_bytes(images["image_before"]["bytes"])
            (out / "pairs" / f"{name}_b.png").write_bytes(images["image_after"]["bytes"])
            d = json.loads(m["mutation_dicts_json"][0]) if m["mutation_dicts_json"] else None
            index.append({
                "name": name, "split": split[row], "op": (m["mutation_types"] or ["none"])[0].replace("mutate_", ""),
                "difficulty": m["difficulty"], "property": d and d["property"], "direction": d and d["direction"],
                "old": d and d["old_value"], "new": d and d["new_value"],
                "bbox": [m["target_bbox_x"], m["target_bbox_y"], m["target_bbox_w"], m["target_bbox_h"]],
                "pixel_diff": m["pixel_diff"],
            })
            row += 1
    (out / "index.json").write_text(json.dumps(index))
    print(f"{row} pairs -> {out}; split {collections.Counter(r['split'] for r in index)}")


if __name__ == "__main__":
    main()
