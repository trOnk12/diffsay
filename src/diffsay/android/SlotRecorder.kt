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

    /** Where [writeTarget] writes; set before the content is composed. */
    var target: File? = null

    fun writeTarget() {
        target?.let { write(it) }
    }

    override fun toString() = "SlotRecorder"  // stable when a composition remembers a lambda that captures it

    /** [offsetX]/[offsetY]: where the captured node sits in the window, so boxes line up with screenshot pixels. */
    fun write(file: File, offsetX: Int = 0, offsetY: Int = 0) {
        // A recorder must never fail the test it observes: on any error, write nothing and say why.
        try {
            dx = offsetX
            dy = offsetY
            val roots = tables.map { it.asTree() }
            file.parentFile.mkdirs()
            val text = "[" + roots.joinToString(",") { json(it) } + "]"
            // Full screens dump 1-3 MB of JSON; gzipped it's ~20x smaller.
            if (file.name.endsWith(".gz")) GZIPOutputStream(file.outputStream()).bufferedWriter().use { it.write(text) }
            else file.writeText(text)
        } catch (e: Throwable) {
            System.err.println("diffsay: no composition dump for ${file.name}: $e")
        }
    }

    private var dx = 0
    private var dy = 0

    private fun json(g: Group): String {
        val r = g.box
        val b = if (r.width == 0 && r.height == 0) r else r.translate(-dx, -dy)
        val loc = g.location
        // Parameter metadata goes through Kotlin reflection, which throws on some function references.
        val parameters = runCatching { g.parameters }.getOrDefault(emptyList())
        val params = parameters.filter { !it.fromDefault || it.name in setOf("shape", "colors", "modifier") }
            .joinToString(",") { "{\"name\":${str(it.name)},\"value\":${str(render(it.value))}}" }
        val kids = g.children.joinToString(",") { json(it) }
        val mods = g.modifierInfo.joinToString(".") { render(it.modifier) }
        // Raw slot values: what the composer remembered for this group, when parameter metadata is missing.
        val data = if (parameters.isEmpty()) g.data.filter { it !is Function<*> && it != null }.take(8)
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
        // toString() of a value holding a function reference can go through Kotlin reflection and throw an Error.
        else -> try { v.toString().take(6000) } catch (e: Throwable) { "<${v.javaClass.simpleName}>" }
    }

    private fun str(s: String) = "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ") + "\""
}
