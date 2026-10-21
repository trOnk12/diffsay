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

## Results: study 2 (triage), and study 2b (pre-registered after it)

| Arm | Correct | Total cost | Median cost | Median turns | Median time |
| --- | --- | --- | --- | --- | --- |
| A, screenshots | 7/8 | $2.18 | $0.16 | 14 | 26 s |
| B, diffsay | 7/8 | $2.23 | $0.09 | 4.5 | 41 s |

Both arms found the hidden edit in all 6 tasks that had one. A raised a false alarm on control T2
(an invented `Shape.kt` change). B ran out of turns on control T1: it read diffsay's single cause,
distrusted it ("the tool reports the same cause for every screenshot; I want to see what else
changed") and hand-diffed the dumps for 60 turns. On the six hidden-edit tasks B cost about half of A
($0.07 vs $0.15 median) in a third of the turns; on controls both were expensive.

That transcript led to a change (5e0b9e1): diffsay now states whether its causes account for every
change in each composition. **Study 2b** tests it on fresh tasks, so the change isn't scored on the
task that prompted it: 8 new combinations (seed 77, `agent_study_2b_tasks.json`; T1's intended edit
excluded, hidden edits unused before), 4 controls and 4 with a hidden edit, both arms rerun, same
protocol and prompts.

### Study 2b results

| Arm | Correct | Total cost | Median cost | Median turns | Median time |
| --- | --- | --- | --- | --- | --- |
| A, screenshots | 7/8 | $3.72 | $0.19 | 12 | 34 s |
| B, diffsay (with coverage statement) | 6/8 | $3.42 | $0.07 | 4 | 23 s |

The coverage statement did not help. On control U1 the agent read "these causes account for every
composition change in 16 of 16", then saw diffsay's pixel-heuristic section ("corner", "moved") and
hunted for those "unexplained" changes until it ran out of turns. On control U3 it reported an
invented `Shape.kt` change, the same kind of false alarm arm A made in study 2. On the four
hidden-edit tasks both arms were right, and B cost about a third ($0.07 vs $0.15 median).

## Conclusion across studies 1, 1b, 2 and 2b (46 paired tasks)

For a coding agent with vision, diffsay does **not** improve accuracy: the agent finds the edit from
the images and the code, whether it is the only change or hidden among intended ones. diffsay makes
the diagnosis cheaper (often a third to a half of the tokens) when there is something to find, and
does not settle "nothing else changed": agents still verify that themselves, at length, and its pixel
section can send them looking for more. That is a cost optimisation, not a capability.
