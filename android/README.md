# Android setup

diffsay's cause-in-code mode needs the composition of each screenshot, saved beside it by
[`SlotRecorder.kt`](../src/diffsay/android/SlotRecorder.kt) during the Robolectric test:

- `<name>.slots.json` when recording goldens
- `<name>_actual.slots.json` when comparing or verifying

`diffsay init <module>` copies the two Kotlin files into `<module>/src/test/(kotlin|java)/dev/diffsay/`
and prints the Gradle lines. Below is what it sets up.

## Roborazzi's generated @Preview tests (no test code)

Tested with Roborazzi 1.74.0 and 1.76.0, Compose BOM 2026.09, Kotlin 2.4.

```kotlin
dependencies {
    testImplementation("androidx.compose.ui:ui-tooling-data")
}

roborazzi {
    @OptIn(com.github.takahirom.roborazzi.ExperimentalRoborazziApi::class)
    generateComposePreviewRobolectricTests {
        enable = true
        packages = listOf("com.example.app")
        useScanOptionParametersInTester = true   // the tester still honours includePrivatePreviews etc.
        testerQualifiedClassName = "dev.diffsay.DiffsayPreviewTester"
    }
}
```

[`DiffsayPreviewTester`](../src/diffsay/android/DiffsayPreviewTester.kt) delegates to Roborazzi's
`AndroidComposePreviewTester` and adds one capture option, which records the composition while the
preview is shown and writes it once the screenshot is taken. Every preview variant (dark theme, font
scale, RTL, devices) gets its own dump.

If you already use your own `ComposePreviewTester`, add the same option to your capturer: see the
`SlotCapture` class in that file.

## Hand-written Roborazzi tests

Replace `setContent { … }` + `onRoot().captureRoboImage(path)` with `captureWithCauses`:

```kotlin
@get:Rule val compose = createComposeRule()

@Test fun checkout() = compose.captureWithCauses("src/test/screenshots/checkout.png") {
    CheckoutScreen()
}
```

## A shared screenshot helper

If your tests go through one helper that calls `setContent` itself (Now in Android's
`captureMultiTheme`, for example), wrap the content and write after each capture:

```kotlin
val recorder = SlotRecorder()
setContent { recorder.Record { AppTheme { content() } } }
// … for each variant:
onRoot().captureRoboImage(path)
recorder.writeBeside(path, onRoot())
```

Screenshots saved downscaled (`RecordOptions(resizeScale = 0.5)`) are handled: `scan` scales
the changed regions back to layout pixels.

## Then

```bash
./gradlew recordRoborazziDebug
# change code
./gradlew compareRoborazziDebug
diffsay scan app/build --source app
```

`scan` reads Roborazzi's results (`build/test-results/roborazzi/**.json`) to find the changed
screenshots, so it also works when goldens live in `src/test/screenshots`.

## What it can and can't see

- Calls into library composables (`Text`, `Card`, `Surface`, …), their remembered values, and
  every modifier chain: yes. Parameter *names* aren't readable on Compose 1.12 with Kotlin 2.x, so
  values are compared by position and named by the source lookup (`padding(12.dp) is written at
  ReplyEmailListItem.kt:81`).
- Arguments to your own composables show up where they're used, and in the source lookup.
- Drawing inside `drawBehind { }` / `Canvas` lambdas: no. Those failures say `composition identical`.
- `Arrangement`/`Alignment` on inline `Row`/`Column`: reported as children moving, at the right
  lines, without the parameter.
- Robolectric renders on the JVM; it isn't a device.
