package dev.sample

import androidx.compose.runtime.Composable
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import java.io.File
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h640dp-xhdpi")
class ScreensScreenshotTest {
    @get:Rule val compose = createComposeRule()

    private fun shoot(name: String, content: @Composable () -> Unit) {
        val slots = SlotRecorder()
        compose.setContent { slots.Record(content) }
        compose.onRoot().captureRoboImage()
        val root = compose.onRoot().fetchSemanticsNode().positionInWindow
        val suffix = if (System.getProperty("roborazzi.test.record") == "true") "" else "_actual"
        slots.write(File("build/outputs/roborazzi", "dev.sample.ScreensScreenshotTest.$name$suffix.slots.json"), root.x.toInt(), root.y.toInt())
    }

    @Test fun settings() = shoot("settings") { SettingsScreen() }
    @Test fun profile() = shoot("profile") { ProfileScreen() }
    @Test fun feed() = shoot("feed") { FeedScreen() }
    @Test fun login() = shoot("login") { LoginScreen() }
    @Test fun product() = shoot("product") { ProductScreen() }
    @Test fun inbox() = shoot("inbox") { InboxScreen() }
}
