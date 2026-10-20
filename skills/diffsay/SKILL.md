---
name: diffsay
description: Explain why Compose screenshot tests (Roborazzi) failed - the source line and new value behind each changed screenshot - without opening images. Use after compareRoborazzi*/verifyRoborazzi* reports changed screenshots, or to check which screenshots a UI change affects.
---

# Why did these screenshots change?

1. If the module has no `dev/diffsay/SlotRecorder.kt` in its test sources, run `diffsay init <module>`
   and add the Gradle lines it prints. Record goldens once (`./gradlew recordRoborazziDebug`).
2. After `compareRoborazziDebug` or a failed `verifyRoborazziDebug`, run
   `diffsay scan <module>/build --source <module>`.
3. Read the summary: one line per cause in code (file:line, the new value) and the screenshots it broke.
   - A cause you intended: re-record those goldens.
   - A cause you didn't intend: fix that line.
   - `composition identical: ...`: the change is in drawing code (draw lambdas, Canvas, images) or the
     render isn't deterministic. Only then look at the `zoom:` crop (`--crops DIR`), not the full PNGs.
4. For a PR comment, use `--markdown`.

Don't open golden/actual PNGs to find a cause: the summary is ~30 tokens per cause; two screenshots
are ~2,700 image tokens and still don't name the line.
