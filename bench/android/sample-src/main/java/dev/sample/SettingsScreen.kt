package dev.sample

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen() {
    MaterialTheme {
        Column(Modifier.fillMaxSize().background(Color.White)) {
            TopAppBar(title = { Text("Settings") })
            SectionHeader("Account")
            ListItem(
                headlineContent = { Text("Profile") },
                supportingContent = { Text("Name, photo, bio") },
                leadingContent = { Icon(Icons.Filled.Person, contentDescription = null) },
            )
            ListItem(
                headlineContent = { Text("Privacy") },
                supportingContent = { Text("Blocked users, visibility") },
                leadingContent = { Icon(Icons.Filled.Lock, contentDescription = null) },
            )
            HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = Color(0xFFE0E0E0))
            SectionHeader("Preferences")
            ListItem(
                headlineContent = { Text("Notifications") },
                leadingContent = { Icon(Icons.Filled.Notifications, contentDescription = null) },
                trailingContent = { Switch(checked = true, onCheckedChange = {}) },
            )
            ListItem(
                headlineContent = { Text("Dark mode") },
                trailingContent = { Switch(checked = false, onCheckedChange = {}) },
            )
            Spacer(Modifier.height(24.dp))
            TextButton(onClick = {}, modifier = Modifier.padding(horizontal = 8.dp)) {
                Text("Sign out", color = Color(0xFFD32F2F))
            }
        }
    }
}

@Composable
fun SectionHeader(title: String) {
    Text(
        title.uppercase(),
        fontSize = 12.sp,
        fontWeight = FontWeight.Bold,
        color = Color(0xFF1565C0),
        modifier = Modifier.padding(start = 16.dp, top = 16.dp, bottom = 4.dp),
    )
}
