package dev.diffsay

import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onGloballyPositioned
import app.cash.paparazzi.Paparazzi
import java.io.File
import java.util.Locale

/**
 * `paparazzi.snapshot(name) { … }` that also writes the composition, so `diffsay scan` can name the
 * cause of a failure: `<golden>.slots.json.gz` beside the golden when recording, and
 * `<golden name>_actual.slots.json.gz` in Paparazzi's failures directory when verifying.
 */
fun Paparazzi.snapshotWithCauses(name: String? = null, content: @Composable () -> Unit) {
    val recorder = SlotRecorder()
    val file = slotsFile(name)
    snapshot(name) {
        recorder.Record {
            // Written once laid out, while the composition is alive; a later layout pass overwrites it.
            Box(Modifier.onGloballyPositioned { file?.let { recorder.write(it) } }) { content() }
        }
    }
}

private val testNameField = Paparazzi::class.java.getDeclaredField("testName").apply { isAccessible = true }

/** Mirrors Paparazzi's Snapshot.toFileName(): <package>_<class>_<method>[_<name>]. */
private fun Paparazzi.slotsFile(name: String?): File? {
    val testName = testNameField.get(this) ?: return null
    fun field(n: String) = testName.javaClass.getMethod("get" + n.replaceFirstChar { it.uppercase() }).invoke(testName) as String
    val label = name?.let { "_" + it.lowercase(Locale.US).replace("\\s".toRegex(), "_") } ?: ""
    val base = "${field("packageName")}_${field("className")}_${field("methodName").replace("\\s".toRegex(), "_")}$label"
    return if (System.getProperty("paparazzi.test.record")?.toBoolean() == true) {
        File(System.getProperty("paparazzi.snapshot.dir") ?: "src/test/snapshots", "images/$base.slots.json.gz")
    } else {
        val failures = System.getProperty("paparazzi.failures.dir") ?: return null
        File(failures, "${base}_actual.slots.json.gz").also { it.parentFile.mkdirs() }
    }
}
