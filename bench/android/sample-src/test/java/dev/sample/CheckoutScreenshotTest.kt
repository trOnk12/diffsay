package dev.sample

import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.text.font.FontWeight
import java.io.File
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** -Pmutation=<name> renders the screen with one realistic change applied. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h640dp-xhdpi")
class CheckoutScreenshotTest {
    @get:Rule val compose = createComposeRule()

    @Test fun checkout() {
        val style = when (System.getProperty("mutation", "none")) {
            "padding" -> Style(cardPadding = 24)
            "color" -> Style(buttonColor = Color(0xFF43A047))
            "weight" -> Style(titleWeight = FontWeight.Normal)
            "radius" -> Style(buttonRadius = 24)
            "text" -> Style(buttonText = "Pay now!")
            "align" -> Style(headerAlign = Alignment.Start)
            "fontsize" -> Style(bodySize = 16)
            "gap" -> Style(rowGap = 20)
            "alpha" -> Style(noteAlpha = 0.5f)
            "border" -> Style(fieldBorder = Color(0xFF616161))
            "offset" -> Style(badgeOffset = 8)
            "lineheight" -> Style(bodyLineHeight = 26)
            else -> Style()
        }
        val slots = SlotRecorder()
        compose.setContent { slots.Record { CheckoutScreen(style) } }
        compose.onRoot().captureRoboImage()
        // Baseline runs write <name>.slots.json; compare/verify runs write <name>_actual.slots.json.
        val root = compose.onRoot().fetchSemanticsNode().positionInWindow
        val suffix = if (System.getProperty("roborazzi.test.record") == "true") "" else "_actual"
        slots.write(
            File(System.getProperty("treeDir", "build/outputs/roborazzi"), "dev.sample.CheckoutScreenshotTest.checkout$suffix.slots.json"),
            root.x.toInt(), root.y.toInt(),
        )
        // Semantics tree in diffsay's JSON format, beside the screenshot Roborazzi writes.
        val dir = File(System.getProperty("treeDir", "build/outputs/roborazzi"))
        dir.mkdirs()
        File(dir, "dev.sample.CheckoutScreenshotTest.checkout.tree.json")
            .writeText("[" + json(compose.onRoot(useUnmergedTree = true).fetchSemanticsNode()) + "]")
    }

    private fun json(node: SemanticsNode): String {
        val c = node.config
        val label = c.getOrNull(SemanticsProperties.Text)?.joinToString(" ") { it.text }
            ?: c.getOrNull(SemanticsProperties.ContentDescription)?.joinToString(" ")
            ?: c.getOrNull(SemanticsProperties.TestTag) ?: ""
        val role = c.getOrNull(SemanticsProperties.Role)?.toString()
            ?: if (c.getOrNull(SemanticsProperties.Text) != null) "Text" else ""
        val b = node.boundsInRoot
        val kids = node.children.joinToString(",") { json(it) }
        val esc = label.replace("\\", "\\\\").replace("\"", "\\\"")
        return "{\"role\":\"$role\",\"label\":\"$esc\",\"bounds\":[${b.left.toInt()},${b.top.toInt()},${b.right.toInt()},${b.bottom.toInt()}],\"children\":[$kids]}"
    }
}
