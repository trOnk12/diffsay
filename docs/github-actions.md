# Screenshot causes as a PR comment

When Roborazzi's compare finds changed screenshots on a pull request, post diffsay's table of
causes on it. Reviewers see *which lines* changed the UI, and the agent that wrote the PR can
read the same comment.

Goldens must be available to compare against: either committed (`src/test/screenshots`, or
Roborazzi's `outputDir`), or restored from the base branch's artifact as in
[Roborazzi's CI guide](https://github.com/takahirom/roborazzi#github-actions). The `.slots.json.gz`
files written next to the goldens must travel with them.

```yaml
name: screenshots
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  compare:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: 21 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: ./gradlew :app:compareRoborazziDebug
      - run: pip install git+https://github.com/trOnk12/diffsay
      - name: Explain changed screenshots
        run: diffsay scan app/build --source app --markdown > causes.md || true
      - name: Comment
        if: hashFiles('causes.md') != ''
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          if grep -q "screenshot test" causes.md; then
            gh pr comment ${{ github.event.pull_request.number }} --body-file causes.md
          fi
```

`diffsay scan` exits 1 when something changed, 0 when nothing did; the `|| true` keeps the job
going so the comment is posted.

The comment looks like:

> ### 5 screenshot test(s) changed
>
> | Cause | Screenshots |
> | --- | --- |
> | `ReplyEmailListItem.kt:129 now uses titleMedium (Type.kt:50) instead of bodyLarge` | 5: ReplyAppPreview.WITH_BACKGROUND, … |
> | `padding(12.dp) is written at ReplyEmailListItem.kt:81` | 5: ReplyAppPreview.WITH_BACKGROUND, … |
