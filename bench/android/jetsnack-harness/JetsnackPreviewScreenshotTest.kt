package com.example.jetsnack

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.test.junit4.createComposeRule
import dev.diffsay.captureWithCauses
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import com.example.jetsnack.ui.components.ButtonPreview
import com.example.jetsnack.ui.components.CardPreview
import com.example.jetsnack.ui.components.DividerPreview
import com.example.jetsnack.ui.components.FilterDisabledPreview
import com.example.jetsnack.ui.components.FilterEnabledPreview
import com.example.jetsnack.ui.components.GradientTintedIconButtonPreview
import com.example.jetsnack.ui.components.QuantitySelectorPreview
import com.example.jetsnack.ui.components.QuantitySelectorPreviewRtl
import com.example.jetsnack.ui.components.RectangleButtonPreview
import com.example.jetsnack.ui.components.SnackCardPreview
import com.example.jetsnack.ui.home.FilterScreenPreview
import com.example.jetsnack.ui.home.HomePreview
import com.example.jetsnack.ui.home.JetsnackBottomNavPreview
import com.example.jetsnack.ui.home.PreviewDestinationBar
import com.example.jetsnack.ui.home.ProfilePreview
import com.example.jetsnack.ui.home.cart.CartPreview
import com.example.jetsnack.ui.home.search.PreviewSuggestions
import com.example.jetsnack.ui.home.search.SearchBarPreview
import com.example.jetsnack.ui.home.search.SearchCategoryPreview
import com.example.jetsnack.ui.home.search.SearchResultPreview
import com.example.jetsnack.ui.snackdetail.SnackDetailPreview
import com.example.jetsnack.widget.layout.ImageTextListLayoutPreview

/** Every @Preview in Jetsnack, captured with its composition so failures explain themselves. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h740dp-xhdpi")
class JetsnackPreviewScreenshotTest {
    @get:Rule val compose = createComposeRule()

    private fun shoot(name: String, content: @Composable () -> Unit) =
        compose.captureWithCauses("src/test/screenshots/$name.png") {
            CompositionLocalProvider(LocalInspectionMode provides true) { content() }
        }

    @Test fun buttonPreview() = shoot("ButtonPreview") { ButtonPreview() }
    @Test fun rectangleButtonPreview() = shoot("RectangleButtonPreview") { RectangleButtonPreview() }
    @Test fun cardPreview() = shoot("CardPreview") { CardPreview() }
    @Test fun dividerPreview() = shoot("DividerPreview") { DividerPreview() }
    @Test fun filterDisabledPreview() = shoot("FilterDisabledPreview") { FilterDisabledPreview() }
    @Test fun filterEnabledPreview() = shoot("FilterEnabledPreview") { FilterEnabledPreview() }
    @Test fun gradientTintedIconButtonPreview() = shoot("GradientTintedIconButtonPreview") { GradientTintedIconButtonPreview() }
    @Test fun quantitySelectorPreview() = shoot("QuantitySelectorPreview") { QuantitySelectorPreview() }
    @Test fun quantitySelectorPreviewRtl() = shoot("QuantitySelectorPreviewRtl") { QuantitySelectorPreviewRtl() }
    @Test fun snackCardPreview() = shoot("SnackCardPreview") { SnackCardPreview() }
    @Test fun previewDestinationBar() = shoot("PreviewDestinationBar") { PreviewDestinationBar() }
    @Test fun filterScreenPreview() = shoot("FilterScreenPreview") { FilterScreenPreview() }
    @Test fun jetsnackBottomNavPreview() = shoot("JetsnackBottomNavPreview") { JetsnackBottomNavPreview() }
    @Test fun profilePreview() = shoot("ProfilePreview") { ProfilePreview() }
    @Test fun searchCategoryPreview() = shoot("SearchCategoryPreview") { SearchCategoryPreview() }
    @Test fun searchResultPreview() = shoot("SearchResultPreview") { SearchResultPreview() }
    @Test fun searchBarPreview() = shoot("SearchBarPreview") { SearchBarPreview() }
    @Test fun previewSuggestions() = shoot("PreviewSuggestions") { PreviewSuggestions() }
    @Test fun snackDetailPreview() = shoot("SnackDetailPreview") { SnackDetailPreview() }
}
