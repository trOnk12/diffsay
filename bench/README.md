# Reproducing the DiffSpot numbers

```bash
pip install numpy scipy pillow pyarrow huggingface_hub
python prepare_diffspot.py /tmp/diffspot          # downloads ~0.5 GB (MIT) and writes pairs/ + index.json
python diffspot_eval.py /tmp/diffspot/pairs /tmp/diffspot/index.json --split dev
python diffspot_eval.py /tmp/diffspot/pairs /tmp/diffspot/index.json --split test
```

The split is fixed by seed `20261020`: 8 pairs per (operator, difficulty) cell, plus 8
no-change pairs, go to `dev` (320 pairs, used for tuning). The other 4,080 are `test`, scored
once per published result.

`diffspot_eval.py --show N` prints N failures per operator with diffsay's full report.

The blinded agent study in the main README used hard-tier test pairs, sampled with seeds 7, 11
and 23 (two per operator plus four no-change pairs each), with sets kept disjoint. Answers were
written before labels were read.

Raw records of the blinded study (pair row, truth, and the agent's answer) are in
[`blinded/`](blinded/): `set1.json` (full screenshots), `set2.json` (first-change crop), and
`set3.json` (all-change crops).
