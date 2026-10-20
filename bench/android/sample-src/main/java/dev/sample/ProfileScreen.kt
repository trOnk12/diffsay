package dev.sample

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun ProfileScreen() {
    MaterialTheme {
        Column(
            Modifier.fillMaxSize().background(Color(0xFFFAFAFA)).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                Modifier.size(88.dp).clip(CircleShape).background(Color(0xFF7E57C2)),
                contentAlignment = Alignment.Center,
            ) {
                Text("AL", color = Color.White, fontSize = 32.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(12.dp))
            Text("Ada Lovelace", fontSize = 24.sp, fontWeight = FontWeight.SemiBold)
            Text("Analyst · London", fontSize = 14.sp, color = Color(0xFF757575))
            Spacer(Modifier.height(20.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                Stat("128", "Posts")
                Stat("4.2k", "Followers")
                Stat("312", "Following")
            }
            Spacer(Modifier.height(20.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(onClick = {}, label = { Text("Math") })
                AssistChip(onClick = {}, label = { Text("Engines") })
                AssistChip(onClick = {}, label = { Text("Poetry") })
            }
            Spacer(Modifier.height(24.dp))
            OutlinedButton(onClick = {}, shape = RoundedCornerShape(20.dp), modifier = Modifier.fillMaxWidth()) {
                Text("Edit profile")
            }
        }
    }
}

@Composable
fun Stat(value: String, label: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Text(label, fontSize = 12.sp, color = Color(0xFF9E9E9E))
    }
}
