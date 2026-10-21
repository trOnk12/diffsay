# Does diffsay help an agent? Study protocol (pre-registered)

Question: on a real failed Compose screenshot test, does a coding agent find the cause faster,
cheaper or more often with diffsay than with the screenshots and the code alone?

Tasks: 10 failures sampled (seed 5150) from the 28 visible JetNews edits of
`jetnews_v5_sites.json`, listed in `agent_study_tasks.json`. Each task is a copy of JetNews' `app/src`
with the edit applied (no git history), and the failed screenshots (golden and actual PNG) of that
run, as Roborazzi left them.

Arms, same model and settings (`claude -p`, Read/Grep/Glob/Bash, 40 turns max):
- **A, screenshots:** "These screenshot tests failed after a code change. Find the change."
- **B, diffsay:** the same, plus "`diffsay` is installed: `diffsay scan screenshots --source app`" and
  the slot dumps beside the screenshots.

The agent answers with JSON `{"file", "line", "new_value"}`. Correct = the edited file, a line within
3 of the edit, and the new value. Scored by script against the site file; also recorded: total cost
(USD, as reported by the CLI), turns and wall time.

Limits stated up front: one model, 10 tasks per arm, the agent can't run Gradle, and it has no git
history (in real work `git diff` often narrows the search; this measures the case where it doesn't:
a teammate's change, a dependency bump, a long session with many edits).

## Amendments (recorded before the affected results were counted)

1. **Leak fixed.** The first runs of study 1 were discarded: the edited file had a newer mtime than
   every other file, and `Glob`/`ls -t` order by mtime. All task files now share one timestamp.
2. **Observed confound in study 1:** the agent uses priors about this well-known public code and
   about Material defaults ("original was likely 0xFFFFB3B4"; "23.sp is atypical"). On famous sample
   code, study 1 therefore measures the easy case.

## Study 1b (pre-registered, seed 2718)

Same protocol on **private code**: 10 of the 30 held-out hand-written edits to the sample app's three
screens (`agent_study_1b_tasks.json`), which no model has seen. Edits are realistic (aspect ratio,
copy, shapes, spacing), not offsets.

## Study 2: triage at scale (pre-registered, seed 424242)

Reviewing a PR whose screenshot changes are mostly intended, with one unintended change hidden
among them (the Element X AGP 9 upgrade: 143 re-recorded screenshots, regressions found by eye).
8 JetNews tasks (`agent_study_2_tasks.json`): each applies one *intended* theme edit (Type.kt or
Color.kt, 5-16 failing screenshots) plus, in 6 of 8, one *hidden* edit elsewhere (2-4 screenshots).
2 tasks are controls with no hidden edit.

The agent is told the intended change ("this PR changes `<file>` line N") and that the branch also
contains other work, without history. It must answer `{"hidden": null}` or
`{"hidden": {"file", "line", "new_value"}}`. Correct = control answered null, or the hidden edit
found (file, line within 3, new value). Arms and settings as in study 1.

## Results: studies 1 and 1b (single edit, single cause)

| Study | Arm | Correct | Total cost | Median cost | Median time |
| --- | --- | --- | --- | --- | --- |
| 1, JetNews (public code) | A, screenshots | 9/10 | $0.50 | $0.042 | 13 s |
| | B, diffsay | 10/10 | $0.58 | $0.031 | 16 s |
| 1b, sample app (private code) | A, screenshots | 10/10 | $0.62 | $0.063 | 10 s |
| | B, diffsay | 10/10 | $1.08 | $0.068 | 15 s |

**No meaningful benefit.** For one failure caused by one edit, the agent looks at the golden and
actual images, opens the file the test is named after, and spots the value (it even measured an
aspect ratio from pixel sizes). With diffsay it was about as accurate and, in 1b, more expensive:
it ran the tool *and* still opened the images. diffsay's per-edit attribution is accurate (see the
mutation benchmarks), but on this task an agent doesn't need it.

Scoring note for 1b: the first scoring compared the whole replaced fragment (`aspectRatio(2.0f)`)
with the answer's value (`2.0f`) and failed every answer in both arms. Rescored, for both arms
alike, against the token that differs between the old and new fragment (`study1b_truth.json`).
