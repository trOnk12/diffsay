package dev.sample

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class Thread(val from: String, val preview: String, val time: String, val unread: Int)

val THREADS = listOf(
    Thread("Grace Hopper", "The compiler finally works on the Mark I", "09:12", 2),
    Thread("Alan Turing", "Can machines think? Let's discuss tonight", "Yesterday", 0),
    Thread("Katherine Johnson", "Trajectory numbers attached", "Mon", 1),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboxScreen() {
    MaterialTheme {
        Scaffold(topBar = { CenterAlignedTopAppBar(title = { Text("Inbox") }) }) { padding ->
            Column(Modifier.padding(padding).fillMaxSize()) {
                THREADS.forEach { ThreadRow(it) }
            }
        }
    }
}

@Composable
fun ThreadRow(thread: Thread) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(44.dp).clip(CircleShape).background(Color(0xFF90CAF9)), contentAlignment = Alignment.Center) {
            Text(thread.from.take(1), fontWeight = FontWeight.Bold, color = Color(0xFF0D47A1))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(thread.from, fontWeight = if (thread.unread > 0) FontWeight.Bold else FontWeight.Normal, fontSize = 15.sp)
            Text(thread.preview, fontSize = 13.sp, color = Color(0xFF757575), maxLines = 1)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(thread.time, fontSize = 12.sp, color = Color(0xFF9E9E9E))
            if (thread.unread > 0) {
                Badge { Text("${thread.unread}") }
            }
        }
    }
}
