package dev.sample

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class Post(val title: String, val author: String, val unread: Boolean)

val POSTS = listOf(
    Post("Release notes 4.2", "Mobile team", true),
    Post("Design review: onboarding", "Design", false),
    Post("Incident report #118", "SRE", true),
    Post("Hiring update", "People", false),
)

@Composable
fun FeedScreen() {
    MaterialTheme {
        Box(Modifier.fillMaxSize().background(Color(0xFFF2F4F7))) {
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(POSTS) { post -> PostCard(post) }
            }
            FloatingActionButton(
                onClick = {},
                containerColor = Color(0xFF00897B),
                modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp),
            ) { Icon(Icons.Filled.Add, contentDescription = "New post", tint = Color.White) }
        }
    }
}

@Composable
fun PostCard(post: Post) {
    Card(shape = RoundedCornerShape(10.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(post.title, fontSize = 16.sp)
                Text(post.author, fontSize = 13.sp, color = Color(0xFF6B7280))
            }
            if (post.unread) {
                Badge(containerColor = Color(0xFFE53935)) { Text("new", fontSize = 10.sp) }
            }
        }
    }
}
