@file:OptIn(UiToolingDataApi::class)

package dev.diffsay

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.currentComposer
import androidx.compose.runtime.tooling.CompositionData
import androidx.compose.runtime.tooling.LocalInspectionTables
import androidx.compose.ui.tooling.data.Group
import androidx.compose.ui.tooling.data.UiToolingDataApi
import androidx.compose.ui.tooling.data.asTree
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import androidx.compose.ui.platform.InspectableValue
import androidx.compose.ui.platform.isDebugInspectorInfoEnabled
import java.io.File
import java.util.Collections
import java.util.WeakHashMap
import java.util.zip.GZIPOutputStream

/**
 * Records the composition's slot table like Android Studio's Layout Inspector does, so each
 * pixel region can be traced back to a composable call (file:line) and its parameter values.
 */
class SlotRecorder {
    init {
        isDebugInspectorInfoEnabled = true // modifiers then describe themselves, e.g. padding(all=16.dp)
    }

    val tables: MutableSet<CompositionData> = Collections.newSetFromMap(WeakHashMap())

    @Composable
    fun Record(content: @Composable () -> Unit) {
        currentComposer.collectParameterInformation()
        tables.add(currentComposer.compositionData)
        CompositionLocalProvider(LocalInspectionTables provides tables) { content() }
    }

    /** [offsetX]/[offsetY]: where the captured node sits in the window, so boxes line up with screenshot pixels. */
    fun write(file: File, offsetX: Int = 0, offsetY: Int = 0) {
        dx = offsetX
        dy = offsetY
        val roots = tables.map { it.asTree() }
        file.parentFile.mkdirs()
        val text = "[" + roots.joinToString(",") { json(it) } + "]"
        // Full screens dump 1-3 MB of JSON; gzipped it's ~20x smaller.
        if (file.name.endsWith(".gz")) GZIPOutputStream(file.outputStream()).bufferedWriter().use { it.write(text) }
        else file.writeText(text)
    }

    private var dx = 0
    private var dy = 0

    private fun json(g: Group): String {
        val r = g.box
        val b = if (r.width == 0 && r.height == 0) r else r.translate(-dx, -dy)
        val loc = g.location
        val params = g.parameters.filter { !it.fromDefault || it.name in setOf("shape", "colors", "modifier") }
            .joinToString(",") { "{\"name\":${str(it.name)},\"value\":${str(render(it.value))}}" }
        val kids = g.children.joinToString(",") { json(it) }
        val mods = g.modifierInfo.joinToString(".") { render(it.modifier) }
        // Raw slot values: what the composer remembered for this group, when parameter metadata is missing.
        val data = if (g.parameters.isEmpty()) g.data.filter { it !is Function<*> && it != null }.take(8)
            .joinToString(",") { str(render(it)) } else ""
        return "{\"modifiers\":${str(mods)},\"name\":${str(g.name ?: "")},\"file\":${str(loc?.sourceFile ?: "")},\"line\":${loc?.lineNumber ?: -1}," +
            "\"bounds\":[${b.left},${b.top},${b.right},${b.bottom}],\"params\":[$params],\"data\":[$data],\"children\":[$kids]}"
    }

    private fun render(v: Any?): String = when (v) {
        null -> "null"
        is Function<*> -> "λ"
        is Modifier -> v.foldIn(mutableListOf<String>()) { acc, element ->
            acc += (element as? InspectableValue)?.let { iv ->
                val args = iv.inspectableElements.joinToString(", ") { "${it.name}=${render(it.value)}" }
                val value = iv.valueOverride?.let { render(it) }
                "${iv.nameFallback ?: element.javaClass.simpleName}(${value ?: args})"
            } ?: element.javaClass.simpleName
            acc
        }.joinToString(".").ifEmpty { "Modifier" }
        else -> v.toString().take(6000)
    }

    private fun str(s: String) = "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ") + "\""
}

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
    val origin = onRoot().fetchSemanticsNode().positionInWindow
    val golden = File(filePath)
    val recording = System.getProperty("roborazzi.test.record") == "true"
    val name = golden.nameWithoutExtension + if (recording) ".slots.json.gz" else "_actual.slots.json.gz"
    recorder.write(File(golden.absoluteFile.parentFile, name), origin.x.toInt(), origin.y.toInt())
}
