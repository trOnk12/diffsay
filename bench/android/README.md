# Android evidence

Everything behind the numbers in the main README.

## Random-edit benchmark on android/compose-samples

`jetsnack_mutations.py` works on any app checkout (the name is historical):

```bash
python jetsnack_mutations.py select <app-dir> sites.json <seed> [exclude.json]  # sample literal sites
python jetsnack_mutations.py run    <app-dir> sites.json <out-dir>              # patch, compare, restore
python jetsnack_mutations.py score  <app-dir> sites.json <out-dir> [noise-dir]  # explained / located
```

`noise-dir` holds the slot dumps of one compare run on unchanged code; values that differ between
two runs of the same code are ignored.

| File | What |
| --- | --- |
| `jetsnack_sites.json`, `jetsnack_heldout_sites.json` | Jetsnack samples, seeds 42 and 7 |
| `jetnews_sites.json`, `jetnews_v5_sites.json` | JetNews samples, seeds 2026 and 2027 (disjoint) |
| `*_results_frozen_<commit>.txt` | scored once, with the engine as committed before the sample was seen |
| `*_results_posthoc*.txt` | later engines on the same samples (not held-out) |
| `jetsnack-harness/`, `jetnews-harness/` | the screenshot test over each app's @Previews, and the build changes |

The commits named in the file names are from the private repository where diffsay was built;
each sample file was committed there before its run.

## From-scratch setup on Reply

`reply-setup.diff` is everything added to Google's Reply sample to run Roborazzi's generated
preview tests with `DiffsayPreviewTester` (Roborazzi 1.74.0), after `diffsay init app`.
`reply-edit.diff` is the two-line change behind the README's first example. (The Maven mirror
lines are only there because the machine it ran on was rate-limited by Maven Central.)

## Sample screens

`sample-src/`, `mutations_dev.py`, `mutations_heldout.py`, `dev_results.txt`,
`heldout_results_*.txt`: the first benchmark, on three hand-written screens (Compose 1.7/1.8),
31 dev and 30 held-out edits.
