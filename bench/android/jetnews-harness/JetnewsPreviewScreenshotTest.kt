package com.example.jetnews

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
import com.example.jetnews.ui.PreviewAppDrawer
import com.example.jetnews.ui.components.PreviewAppNavRail
import com.example.jetnews.ui.home.BookmarkButtonBookmarkedPreview
import com.example.jetnews.ui.home.BookmarkButtonPreview
import com.example.jetnews.ui.home.HistoryPostPreview
import com.example.jetnews.ui.home.PostCardTopPreview
import com.example.jetnews.ui.home.PreviewHomeListDrawerScreen
import com.example.jetnews.ui.home.PreviewHomeListNavRailScreen
import com.example.jetnews.ui.home.SimplePostPreview
import com.example.jetnews.ui.interests.PreviewInterestsScreenDrawer
import com.example.jetnews.ui.interests.PreviewPeopleTab
import com.example.jetnews.ui.interests.PreviewPublicationsTab
import com.example.jetnews.ui.interests.PreviewTopicsTab
import com.example.jetnews.ui.interests.SelectTopicButtonPreviewOff
import com.example.jetnews.ui.interests.SelectTopicButtonPreviewOn
import com.example.jetnews.ui.post.PreviewPost
import com.example.jetnews.ui.post.PreviewPostDrawer
import com.example.jetnews.ui.post.PreviewPostNavRail
import com.example.jetnews.ui.home.PreviewPostCardPopular
import com.example.jetnews.ui.home.PreviewPostCardPopularLongText
import com.example.jetnews.data.posts.impl.post1

/**
 * Every @Preview in JetNews, light and dark, captured with its composition so failures explain
 * themselves. SDK 30 so the static LightColors/DarkColors render instead of dynamic colour.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [30])
class JetnewsPreviewScreenshotTest {
    @get:Rule val compose = createComposeRule()

    private fun shoot(name: String, content: @Composable () -> Unit) =
        compose.captureWithCauses("src/test/screenshots/$name.png") {
            CompositionLocalProvider(LocalInspectionMode provides true) { content() }
        }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewInterestsScreenDrawer() = shoot("PreviewInterestsScreenDrawer") { PreviewInterestsScreenDrawer() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewInterestsScreenDrawerDark() = shoot("PreviewInterestsScreenDrawerDark") { PreviewInterestsScreenDrawer() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewTopicsTab() = shoot("PreviewTopicsTab") { PreviewTopicsTab() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewTopicsTabDark() = shoot("PreviewTopicsTabDark") { PreviewTopicsTab() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewPeopleTab() = shoot("PreviewPeopleTab") { PreviewPeopleTab() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewPeopleTabDark() = shoot("PreviewPeopleTabDark") { PreviewPeopleTab() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewPublicationsTab() = shoot("PreviewPublicationsTab") { PreviewPublicationsTab() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewPublicationsTabDark() = shoot("PreviewPublicationsTabDark") { PreviewPublicationsTab() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun selectTopicButtonPreviewOff() = shoot("SelectTopicButtonPreviewOff") { SelectTopicButtonPreviewOff() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun selectTopicButtonPreviewOffDark() = shoot("SelectTopicButtonPreviewOffDark") { SelectTopicButtonPreviewOff() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun selectTopicButtonPreviewOn() = shoot("SelectTopicButtonPreviewOn") { SelectTopicButtonPreviewOn() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun selectTopicButtonPreviewOnDark() = shoot("SelectTopicButtonPreviewOnDark") { SelectTopicButtonPreviewOn() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewPost() = shoot("PreviewPost") { PreviewPost() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewPostDark() = shoot("PreviewPostDark") { PreviewPost() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewPostDrawer() = shoot("PreviewPostDrawer") { PreviewPostDrawer() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewPostDrawerDark() = shoot("PreviewPostDrawerDark") { PreviewPostDrawer() }

    @Config(qualifiers = "w840dp-h900dp-xhdpi")
    @Test fun previewPostNavRail() = shoot("PreviewPostNavRail") { PreviewPostNavRail() }

    @Config(qualifiers = "w840dp-h900dp-night-xhdpi")
    @Test fun previewPostNavRailDark() = shoot("PreviewPostNavRailDark") { PreviewPostNavRail() }

    @Config(qualifiers = "w840dp-h900dp-xhdpi")
    @Test fun previewAppNavRail() = shoot("PreviewAppNavRail") { PreviewAppNavRail() }

    @Config(qualifiers = "w840dp-h900dp-night-xhdpi")
    @Test fun previewAppNavRailDark() = shoot("PreviewAppNavRailDark") { PreviewAppNavRail() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewAppDrawer() = shoot("PreviewAppDrawer") { PreviewAppDrawer() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewAppDrawerDark() = shoot("PreviewAppDrawerDark") { PreviewAppDrawer() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewHomeListDrawerScreen() = shoot("PreviewHomeListDrawerScreen") { PreviewHomeListDrawerScreen() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewHomeListDrawerScreenDark() = shoot("PreviewHomeListDrawerScreenDark") { PreviewHomeListDrawerScreen() }

    @Config(qualifiers = "w840dp-h900dp-xhdpi")
    @Test fun previewHomeListNavRailScreen() = shoot("PreviewHomeListNavRailScreen") { PreviewHomeListNavRailScreen() }

    @Config(qualifiers = "w840dp-h900dp-night-xhdpi")
    @Test fun previewHomeListNavRailScreenDark() = shoot("PreviewHomeListNavRailScreenDark") { PreviewHomeListNavRailScreen() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun postCardTopPreview() = shoot("PostCardTopPreview") { PostCardTopPreview() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun postCardTopPreviewDark() = shoot("PostCardTopPreviewDark") { PostCardTopPreview() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun bookmarkButtonPreview() = shoot("BookmarkButtonPreview") { BookmarkButtonPreview() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun bookmarkButtonPreviewDark() = shoot("BookmarkButtonPreviewDark") { BookmarkButtonPreview() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun bookmarkButtonBookmarkedPreview() = shoot("BookmarkButtonBookmarkedPreview") { BookmarkButtonBookmarkedPreview() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun bookmarkButtonBookmarkedPreviewDark() = shoot("BookmarkButtonBookmarkedPreviewDark") { BookmarkButtonBookmarkedPreview() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun simplePostPreview() = shoot("SimplePostPreview") { SimplePostPreview() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun simplePostPreviewDark() = shoot("SimplePostPreviewDark") { SimplePostPreview() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun historyPostPreview() = shoot("HistoryPostPreview") { HistoryPostPreview() }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun historyPostPreviewDark() = shoot("HistoryPostPreviewDark") { HistoryPostPreview() }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewPostCardPopular() = shoot("PreviewPostCardPopular") { PreviewPostCardPopular(post1) }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewPostCardPopularDark() = shoot("PreviewPostCardPopularDark") { PreviewPostCardPopular(post1) }

    @Config(qualifiers = "w360dp-h740dp-xhdpi")
    @Test fun previewPostCardPopularLongText() = shoot("PreviewPostCardPopularLongText") { PreviewPostCardPopularLongText(post1) }

    @Config(qualifiers = "w360dp-h740dp-night-xhdpi")
    @Test fun previewPostCardPopularLongTextDark() = shoot("PreviewPostCardPopularLongTextDark") { PreviewPostCardPopularLongText(post1) }
}
