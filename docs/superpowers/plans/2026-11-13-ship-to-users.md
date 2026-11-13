# Ship diffsay to users — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A stranger with a Roborazzi or Paparazzi project gets diffsay's cause table on their PRs with `pip install diffsay-compose`, `diffsay init app`, and one `uses:` line in a workflow.

**Architecture:** No change to the analysis code. Task 1 makes the package installable from PyPI under a free name and proves the wheel works. Task 2 adds a tag-triggered release with PyPI trusted publishing. Task 3 adds a composite GitHub Action at the repo root that wraps today's documented recipe and adds a sticky comment, a job summary and safe failure. Task 4 is the launch checklist, which you own.

**Tech Stack:** Python ≥3.10, setuptools, unittest, GitHub Actions (composite action, `pypa/gh-action-pypi-publish`), `gh` CLI.

**Spec:** this file's Decisions section plus the 2026-11-13 project-pick note (diffsay chosen; success signal = 1 outside repo running it in CI within 4 weeks of release).

## Decisions (settled 2026-11-13)

- PyPI name `diffsay` belongs to an unrelated commit-message tool (0.2.0, 2026-09-21). Publish as **`diffsay-compose`**. The CLI command stays `diffsay` and the import package stays `diffsay`.
- Kotlin hooks keep shipping inside the wheel and get copied by `diffsay init`. No Maven artifact in this milestone (YAGNI: signing and Central setup cost more than the first users need).
- Pre-flight audit: `pyproject.toml` version 0.2.0 is duplicated in `src/diffsay/__init__.py:5`; install lines point at `git+https://github.com/trOnk12/diffsay` in `README.md:62` and `docs/github-actions.md:29`; CI (`.github/workflows/ci.yml`) installs from source only, so a broken wheel would pass.

## Global Constraints

- Distribution name `diffsay-compose`; console script `diffsay = "diffsay.cli:main"`; import package `diffsay`.
- Release version `0.3.0`, single-sourced from `diffsay.__version__`.
- `requires-python = ">=3.10"`; runtime deps stay exactly `numpy`, `scipy`, `pillow`; license MIT.
- No network and no model at analysis time (README promise). Network calls live only in the Action's shell steps.
- Action major tag `v0`; the Action installs `diffsay-compose==0.3.0` by default.

## Review Focus

1. **Wheel without the `.kt` files**: `pip install diffsay-compose` then `diffsay init app` must copy the Kotlin files. A source-tree test cannot catch this. Pinned by the wheel smoke job (Task 1).
2. **PRs from forks**: `GITHUB_TOKEN` is read-only there, so posting the comment fails. The job must stay green and the cause table must still appear in the job summary. Pinned in Task 3 (Step 6, manual check).
3. **Every push adds another comment**: the Action edits its one comment, found by the marker `<!-- diffsay -->`. When a later push has no changes, it rewrites that comment to say so instead of leaving stale causes. Pinned in Task 3.
4. **Shallow checkout or missing base ref**: `--diff origin/<base>` fails without history. The Action fetches the base ref itself and, if that still fails, runs without `--diff` and prints a `::warning::`. Pinned in Task 3.
5. **Tag and version disagree**: pushing `v0.3.1` while `__version__` is `0.3.0` must fail before upload. Pinned in Task 2.

---

### Task 1: Package as `diffsay-compose` and prove the wheel works

**Files:**
- Modify: `pyproject.toml` (name, dynamic version, urls)
- Modify: `src/diffsay/__init__.py:5` (`__version__ = "0.3.0"`)
- Modify: `src/diffsay/cli.py` (top-level `--version` flag in `main`)
- Modify: `README.md:62`, `docs/github-actions.md:29` (install lines)
- Modify: `.github/workflows/ci.yml` (new `wheel` job)
- Test: `tests/test_init.py` (add `VersionTest`)

**Interfaces:**
- Produces: `diffsay --version` prints `diffsay-compose 0.3.0` and returns 0. Task 2 reads `diffsay.__version__`.

- [ ] **Step 1: Write the failing test** in `tests/test_init.py`

```python
class VersionTest(unittest.TestCase):
    def test_version_flag_names_the_distribution(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, cli.main(["--version"]))
        self.assertEqual("diffsay-compose 0.3.0", out.getvalue().strip())
```

- [ ] **Step 2: Run it and confirm it fails.** `python -m unittest tests.test_init.VersionTest -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** In `main(argv)`, return early on `--version` and print `f"diffsay-compose {__version__}"`. Import the version from `diffsay` lazily inside the branch to avoid a circular import. Set `__version__ = "0.3.0"`. In `pyproject.toml`: `name = "diffsay-compose"`, remove `version`, add `dynamic = ["version"]` and `[tool.setuptools.dynamic] version = { attr = "diffsay.__version__" }`, and add `[project.urls]` with `Homepage` and `Source` = `https://github.com/trOnk12/diffsay`.
- [ ] **Step 4: Run the full suite.** `python -m unittest discover -s tests -v`. Expected: all pass.
- [ ] **Step 5: Add the `wheel` job to `ci.yml`** (ubuntu-latest, Python 3.12):
  1. `pip install build && python -m build`
  2. `python -m venv /tmp/v && /tmp/v/bin/pip install dist/*.whl`
  3. from `/tmp` (outside the repo, so the source tree can't be imported): `mkdir -p m/src/test/kotlin && printf 'android {\n    namespace = "com.acme"\n}\n' > m/build.gradle.kts && /tmp/v/bin/diffsay init m`
  4. `test -f m/src/test/kotlin/dev/diffsay/SlotRecorder.kt && test -f m/src/test/kotlin/dev/diffsay/DiffsayPreviewTester.kt`
  5. `/tmp/v/bin/diffsay --version | grep -x "diffsay-compose 0.3.0"`
- [ ] **Step 6: Verify locally** with the same commands in Git Bash (use `/tmp/v/Scripts/diffsay` on Windows). Expected: both files exist and the version line matches.
- [ ] **Step 7: Replace both install lines** with `pip install diffsay-compose`. Under the README line, add: "(The command is `diffsay`. The PyPI package named `diffsay` is a different project.)"
- [ ] **Step 8: Commit.** `git commit -am "build: publish as diffsay-compose 0.3.0, smoke-test the wheel in CI"`

### Task 2: Tag-triggered release with trusted publishing

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `diffsay.__version__` (Task 1).
- Produces: pushing tag `vX.Y.Z` publishes `diffsay-compose X.Y.Z` to PyPI; a manual run (`workflow_dispatch`) publishes to TestPyPI.

- [ ] **Step 1: Write `release.yml`.** Triggers: `push: tags: ["v*"]` and `workflow_dispatch`. One `build` job with these steps: checkout, setup-python 3.12, the version guard below, `python -m build`, upload `dist/` as an artifact. One `publish` job: `needs: build`, `environment: pypi`, `permissions: id-token: write`, downloads the artifact, runs `pypa/gh-action-pypi-publish@release/v1`, and sets `repository-url: https://test.pypi.org/legacy/` when `github.event_name == 'workflow_dispatch'`.
- [ ] **Step 2: Version guard (only on tag pushes):** `test "${GITHUB_REF_NAME#v}" = "$(python -c 'import ast,pathlib;print([n.value.value for n in ast.parse(pathlib.Path("src/diffsay/__init__.py").read_text()).body if isinstance(n,ast.Assign) and n.targets[0].id=="__version__"][0])')"`. This reads the version without importing numpy.
- [ ] **Step 3: Check the guard both ways locally.** With `GITHUB_REF_NAME=v0.3.0` the guard exits 0; with `v0.3.1` it exits 1.
- [ ] **Step 4: (You, on pypi.org and test.pypi.org)** Add a *pending trusted publisher* for project `diffsay-compose`: owner `trOnk12`, repo `diffsay`, workflow `release.yml`, environment `pypi`. In GitHub repo settings, create the environment `pypi`. These are account actions and stay yours.
- [ ] **Step 5: Dry run.** After merge, run the workflow manually. Expected: TestPyPI shows `diffsay-compose 0.3.0`, and `pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple diffsay-compose && diffsay --version` prints `diffsay-compose 0.3.0`.
- [ ] **Step 6: Commit.** `git commit -m "ci: release to PyPI on tag via trusted publishing"`

### Task 3: Composite GitHub Action

**Files:**
- Create: `action.yml` (repo root)
- Create: `scripts/action/run.sh` (scan, write the summary, set outputs)
- Create: `scripts/action/comment.sh` (sticky comment)
- Create: `tests/make_fixture.py` (writes one golden/actual pair into a directory)
- Modify: `.github/workflows/ci.yml` (new `action` job)
- Modify: `docs/github-actions.md` (lead with the `uses:` form, keep the manual recipe below it)

**Interfaces:**
- Consumes: the `diffsay scan DIR --source S --markdown [--diff REF]` CLI, which exits 1 when screenshots changed and 0 otherwise.
- Produces: Action inputs `module-dir` (required), `source` (default: `module-dir`), `base-ref` (default: `${{ github.base_ref }}`), `install` (default: `diffsay-compose==0.3.0`), `comment` (default: `"true"`), and `github-token` (default: `${{ github.token }}`). Outputs: `changed` (`"true"`/`"false"`) and `causes-file` (path to the markdown).

- [ ] **Step 1: Write `tests/make_fixture.py OUT_DIR`.** Reuse `screen()` from `tests/test_diffsay.py` and save `LoginTest.png` = `screen()` and `LoginTest_actual.png` = `screen(radius=24)`, the same pair `test_actual_beside_golden_pairs` uses.
- [ ] **Step 2: Add the `action` CI job.** It runs `python tests/make_fixture.py fx`, then `uses: ./` with `module-dir: fx`, `install: .`, `comment: "false"`, `base-ref: ""`. A follow-up step asserts `steps.<id>.outputs.changed == 'true'` and `grep -q '^### ' "${{ steps.<id>.outputs.causes-file }}"`. It will fail until Step 3 exists.
- [ ] **Step 3: Implement `action.yml`** (`runs: using: composite`). It runs `actions/setup-python@v5` (3.12), `pip install "${{ inputs.install }}"`, then `scripts/action/run.sh`, then `scripts/action/comment.sh` when `inputs.comment == 'true' && github.event_name == 'pull_request'`. Pass inputs to the scripts through `env:`, never by interpolating them inline into `run:` (avoids script injection).
- [ ] **Step 4: `run.sh` behavior.**
  - If `BASE_REF` is set, run `git fetch --no-tags --depth=200 origin "$BASE_REF"`. If the fetch or a later `git rev-parse origin/$BASE_REF` fails, print `::warning::diffsay: base ref unavailable, running without --diff` and drop `--diff`.
  - Run the scan into `$RUNNER_TEMP/diffsay-causes.md`. Treat exit 1 as `changed=true` and exit 0 as `changed=false`; any other exit code fails the step.
  - Append the file to `$GITHUB_STEP_SUMMARY` and write both outputs to `$GITHUB_OUTPUT`.
- [ ] **Step 5: `comment.sh` behavior.** Body = `<!-- diffsay -->` + newline + the causes file, or `<!-- diffsay -->\nNo screenshot changes in the latest push.` when `changed=false`. Find the first PR comment whose body starts with the marker: `gh api repos/$REPO/issues/$PR/comments --paginate --jq '.[] | select(.body|startswith("<!-- diffsay -->")) | .id' | head -1`. If one exists, PATCH it. Otherwise create a comment, but only when `changed=true`. On any `gh` failure, print `::warning::diffsay: could not comment (fork PR or missing pull-requests: write); see the job summary` and exit 0.
- [ ] **Step 6: Verify.** Push the branch and confirm the CI `action` job passes. Then open a throwaway PR in this repo that runs a workflow using `uses: ./` against the fixture with `comment: "true"`. Push twice and check there is exactly one comment, edited in place. For Review Focus 2, check that the job stays green with `permissions: pull-requests: read`. Close the PR.
- [ ] **Step 7: Rewrite the top of `docs/github-actions.md`** to the 8-line form: checkout with `fetch-depth: 0`, setup-java, `./gradlew :app:compareRoborazziDebug`, `- uses: trOnk12/diffsay@v0` with `module-dir: app/build` and `source: app`, plus `permissions: pull-requests: write`. Keep the existing recipe under "Without the Action".
- [ ] **Step 8: Commit.** `git commit -m "feat: GitHub Action with sticky PR comment and job summary"`

### Task 4: Release and launch (you own this; no code)

- [ ] Merge the branch, then `git tag v0.3.0 && git push origin v0.3.0`. Confirm the PyPI page for `diffsay-compose` shows 0.3.0.
- [ ] `git tag -f v0 v0.3.0 && git push -f origin v0`. This moves the major tag the Action docs reference.
- [ ] README top: replace the install section with three lines (pip, `diffsay init app`, link to the Action docs) above the demo gif.
- [ ] From a clean machine or Codespace, follow only the README on Google's Reply sample. Any step that needs knowledge outside the README is a bug: fix it before announcing.
- [ ] Announce, one channel per day, each post linking the Element X case study: a Show & Tell discussion on Roborazzi's repo, r/androiddev, Kotlin Slack #compose, then a note to the Element X maintainers offering the case study. Sending these is yours.
- [ ] Weekly for 4 weeks, record the results in this file: PyPI downloads (`pypistats recent diffsay-compose`), GitHub code search for `trOnk12/diffsay@` in workflow files, stars and issues. **Success = at least 1 outside repo using the Action within 4 weeks of the v0.3.0 tag.** If it misses, write why here before starting anything new.

---

## Status (2026-11-13)

- Tasks 1–3 done on `release/ship-to-users` (not pushed). Suite: 45 tests OK locally (Windows, Python 3.13).
- Final review (fresh Opus reviewer) fixed in one pass, each with a test that failed first: scan crash no longer
  reports a change; missing `module-dir` fails instead of "no changes"; base ref used without fetching (no
  shallowing of full clones); release runs the tests first; release ignores the moving `v0` tag;
  `PYTHONIOENCODING=utf-8` in the Action (the `--diff` report crashed on Windows code pages).
- PR #1 open. GitHub CI did not run: account locked over billing (jobs end with 0 steps). Stand-in: the three CI
  jobs' steps run in WSL Ubuntu 22.04 / Python 3.10 on a clean clone of ce09e0c: `test` 45/45 OK, `wheel` PASS
  (wheel builds, `init` copies the .kt files, version line matches), Action `run.sh` on the fixture PASS
  (`changed=true`, summary has the table).
- Not verified yet: a real GitHub runner, Task 2 Step 5 TestPyPI dry run, Task 3 Step 6 live PR comment.
- Fresh-project test (Task 4), EventFahrplan @09c47c6 (281★, Roborazzi generated preview tests with its own
  `PackageStrippingComposePreviewTester`), clone in `Dev/_fresh/`. Findings so far:
  1. **diffsay bug:** `init` sees "already generates preview tests" but not the custom tester; its advice
     (set `testerQualifiedClassName` to `dev.diffsay.DiffsayPreviewTester`) would silently drop the user's tester.
  2. **diffsay bug:** the README's custom-tester path says "see `SlotCapture`", but `SlotCapture` is `private`
     in the copied file; users must edit diffsay's file. With it public, integration was 5 lines in their capturer.
  3. **Blocked, not diffsay:** recording fails 163/163 with `NoSuchMethodError: ComposablePreview.invoke(Composer,
     int)` on the unmodified project too (reproduced with edits stashed). Not today's Roborazzi bump: 1.76.0 fails
     the same. Their CI is green because plain unit runs don't render previews. Cause not found; stopped digging.
  Not reached yet: a real UI change explained by `diffsay scan`.
  Bugs 1 and 2 fixed (tests failed first; suite 47/47). Checked in the clone: the new `init` names their tester
  and prints the capturer snippet; `compileCcc39c3DebugUnitTestKotlin --rerun` succeeds with public `SlotCapture`.
- Without billing: publish 0.3.0 by hand (`python -m build && twine upload dist/*` with your PyPI token);
  the Action runs on its users' minutes, not yours.
- Known, deferred: the plain CLI still crashes on Windows when `scan --diff` output is redirected (cp1250 can't
  encode `❔`); reviewer minors — `head -1` + pipefail with duplicate comments, fork-specific warning text for
  every gh failure, no `concurrency` in the docs example, `body.md` written into the checkout, Action's
  setup-python changes `python` for later steps, no comment on `pull_request_target`.
- Next: push the branch and open a PR so CI runs, then Task 2 Step 4 (your PyPI trusted publisher), then Task 4.
