# The problem: screenshot diffs say *that* the UI changed, never *why*

Screenshot tests are now standard in serious Android codebases (Google's
[Now in Android](https://github.com/android/nowinandroid), Matrix's
[Element X](https://github.com/element-hq/element-x-android), the
[DroidKaigi app](https://github.com/DroidKaigi/conference-app-2025)). Every tool in that workflow,
from Roborazzi and Paparazzi to Android Studio and hosted services, reports a failure the same way:
a golden image, an actual image, a diff image. Deciding *why* the pixels changed, and whether that
was intended, is left to a person, or to a bot that re-records the goldens.

This page is the evidence, measured from those projects' public git history and pull requests.

## 1. Most golden changes are re-recorded by bots, not reviewed changes

| Project | Window | Commits touching goldens | Golden-image changes | Changed by a re-record bot |
| --- | --- | --- | --- | --- |
| Now in Android | full history | 46 | 1,594 | **837 (53%)**, "🤖 Updates screenshots" |
| Element X Android | Jan 2025 – Oct 2026 | 686 | 23,140 | **17,035 (74%)**, ElementBot "Update screenshots" |

Element X keeps 3,298 goldens, so each one changed about **seven times** in under two years. Each
change is an image pair a reviewer had to judge.

How it's counted: `git log --name-only` over the golden directories
(`*/screenshots/*.png` in Now in Android, `tests/uitests/src/test/snapshots/` in Element X), with a
commit classed as a bot re-record when its subject is the bot's "Update(s) screenshots".
Reproduce with [`bench/problem_evidence.py`](../bench/problem_evidence.py).

## 2. Changes nobody wrote cause visual changes nobody can explain

Dependency and tooling updates change screenshots without touching any UI code:

- **Now in Android #1630**, a Dependabot bump of *protobuf* 4.26.1 → 4.28.2: the bot re-recorded
  **126 screenshots**, the PR merged, and it was then reverted (`729681b7`), with the 126 screenshots
  restored. Nothing in the PR explains what changed visually or why
  ([PR](https://github.com/android/nowinandroid/pull/1630)).
- **Now in Android `0dd99876`** "Update dependencies" (Compose BOM, Robolectric, Roborazzi):
  126 screenshots changed, followed by a commit titled "revert screenshots".
- **Element X #6021**, the AGP 9 upgrade: **143 screenshots** re-recorded by the bot. The maintainer
  reviewed them by eye and left ten notes on visual regressions, among them *"Error banner has vanished
  here."*, *"Expand arrow has vanished here. In AS preview too."*, *"QrCode is not correctly displayed
  here."*, *"Layout is broken here. (same in AS preview)"* and *"Text color has changed"*. Then: *"Maybe
  we can merge the PR with this limitations?"* The thread names no root cause
  ([PR](https://github.com/element-hq/element-x-android/pull/6021)).
- **Element X #4712**, Coil 3.2.0: **138 screenshots** re-recorded; the reviewer checked a device by
  hand and wrote "We'll have to check how the `ContentScale.Fit` -> `ContentScale.Crop` change behaves in
  the wild" ([PR](https://github.com/element-hq/element-x-android/pull/4712)).

In Element X, 10 dependency bumps since 2025 changed 356 goldens.

## 3. Why existing tools don't close the gap

| Tool | What a failure gives you | Cause in code? |
| --- | --- | --- |
| Roborazzi compare / verify | golden, actual, `_compare.png` diff | no |
| Roborazzi UI-tree dump (1.69+) | semantics tree JSON beside each image, for agents | no: not diffed, no source location |
| Roborazzi AI assertions | a model checks a prompt against the image | no: asserts, doesn't attribute |
| Paparazzi | `delta-*.png` (expected, diff, actual) | no |
| Android Studio / Compose Preview Screenshot Testing | side-by-side images, match % | no |
| DroidKaigi-style CI | a PR comment with a table of diff images | no |
| Emerge / Sentry Snapshots | hosted image diffs per PR | no |
| `git diff` | what code changed | not *which* change broke *which* screenshot, and nothing for dependency bumps |

So the cost lands on a reviewer looking at image pairs, or on a bot that makes the goldens match
whatever the code now renders.

## 4. What diffsay measures, honestly

- **Attribution accuracy** (random, pre-registered edits to Google's compose-samples and Now in
  Android, engine frozen before each sample): 82–94% of edits that changed a screenshot are named at
  the edited line with the new value ([README](../README.md#evidence)).
- **Agent study, single edit** ([details](../bench/AGENT_STUDY.md)): when one edit causes the failure,
  a strong coding agent finds it from the images and the code just as well without diffsay, at the
  same or lower cost. diffsay is **not** worth adding for that case.
- **Agent study, triage** (an intended change plus a hidden one among many failing screenshots): see
  [AGENT_STUDY.md](../bench/AGENT_STUDY.md#study-2-triage-at-scale-pre-registered-seed-424242).
- **Not yet shown:** explaining dependency bumps (the cause lies inside a library). It's the case in
  section 2, and the next thing to measure.
