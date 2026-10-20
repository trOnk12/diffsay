package dev.diffsay

import androidx.compose.runtime.Composable
import com.github.takahirom.roborazzi.AndroidComposePreviewTester
import com.github.takahirom.roborazzi.ComposePreviewTester
import com.github.takahirom.roborazzi.ComposePreviewTester.TestParameter.JUnit4TestParameter.AndroidPreviewJUnit4TestParameter
import com.github.takahirom.roborazzi.ExperimentalRoborazziApi
import com.github.takahirom.roborazzi.RoborazziComposeCaptureOption
import com.github.takahirom.roborazzi.RoborazziComposeComposableOption
import java.io.File

/**
 * Roborazzi's generated @Preview tests, with each capture's composition written beside the image,
 * so `diffsay scan` can name the call site and value behind every failure. Enable it with:
 *
 * ```kotlin
 * roborazzi {
 *   generateComposePreviewRobolectricTests {
 *     enable = true
 *     useScanOptionParametersInTester = true // the delegate still honours includePrivatePreviews etc.
 *     testerQualifiedClassName = "dev.diffsay.DiffsayPreviewTester"
 *   }
 * }
 * ```
 */
@OptIn(ExperimentalRoborazziApi::class)
class DiffsayPreviewTester : ComposePreviewTester<AndroidPreviewJUnit4TestParameter> by AndroidComposePreviewTester(
    capturer = { parameter ->
        val slots = SlotCapture(File(parameter.filePath).absoluteFile, parameter.roborazziOptions.taskType.isRecording())
        AndroidComposePreviewTester.DefaultCapturer().capture(
            parameter.copy(roborazziComposeOptions = parameter.roborazziComposeOptions.builder().addOption(slots).build()),
        )
    },
)

/** Records the composition while it is shown and writes it once captured, before the activity closes. */
@OptIn(ExperimentalRoborazziApi::class)
private class SlotCapture(private val image: File, private val recording: Boolean) :
    RoborazziComposeComposableOption, RoborazziComposeCaptureOption {
    private val recorder = SlotRecorder()

    override fun configureWithComposable(content: @Composable () -> Unit): @Composable () -> Unit =
        { recorder.Record(content) }

    override fun beforeCapture() {}

    override fun afterCapture() {
        // The preview fills a full-screen ComposeView at the window origin, so no offset.
        val suffix = if (recording) ".slots.json.gz" else "_actual.slots.json.gz"
        recorder.write(File(image.parentFile, image.nameWithoutExtension + suffix))
    }
}
