package dev.diffsay

import androidx.compose.runtime.Composable
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import java.io.File

/**
 * The one call a Roborazzi test needs: sets [content], captures it to [filePath] like
 * `captureRoboImage(filePath)`, and writes the composition beside it — `<name>.slots.json.gz` when
 * recording goldens, `<name>_actual.slots.json.gz` when comparing or verifying. `diffsay scan` turns a
 * failure into causes in code from those two files.
 */
fun ComposeContentTestRule.captureWithCauses(filePath: String, content: @Composable () -> Unit) {
    val recorder = SlotRecorder()
    setContent { recorder.Record(content) }
    onRoot().captureRoboImage(filePath)
    recorder.writeBeside(filePath, onRoot())
}

/**
 * For a shared screenshot helper that calls `setContent` itself: wrap the content in
 * `recorder.Record { … }`, and after each `captureRoboImage(filePath)` call
 * `recorder.writeBeside(filePath, onRoot())`.
 */
fun SlotRecorder.writeBeside(filePath: String, root: SemanticsNodeInteraction) {
    val origin = root.fetchSemanticsNode().positionInWindow
    val golden = File(filePath)
    val recording = System.getProperty("roborazzi.test.record") == "true"
    val name = golden.nameWithoutExtension + if (recording) ".slots.json.gz" else "_actual.slots.json.gz"
    write(File(golden.absoluteFile.parentFile, name), origin.x.toInt(), origin.y.toInt())
}
