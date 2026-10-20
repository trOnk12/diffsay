package dev.sample

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val SIZES = listOf("XS", "S", "M", "L", "XL")

@Composable
fun ProductScreen(inStock: Boolean = true) {
    MaterialTheme {
        Column(Modifier.fillMaxSize().background(Color.White)) {
            Box(Modifier.fillMaxWidth().aspectRatio(1.6f).background(Color(0xFFFFE0B2)), contentAlignment = Alignment.Center) {
                Text("photo", color = Color(0xFFBF7B30))
            }
            Column(Modifier.padding(20.dp)) {
                Text(
                    "Trail runner jacket with sealed seams and packable hood",
                    fontSize = 20.sp, fontWeight = FontWeight.Medium, maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Star, contentDescription = null, tint = Color(0xFFFFB300), modifier = Modifier.size(18.dp))
                    Text(" 4.6 (212 reviews)", fontSize = 13.sp, color = Color(0xFF616161))
                }
                Spacer(Modifier.height(12.dp))
                Text("$129.00", fontSize = 26.sp, fontWeight = FontWeight.Bold, color = Color(0xFF1B5E20))
                if (inStock) {
                    Text("In stock · ships tomorrow", fontSize = 13.sp, color = Color(0xFF2E7D32))
                }
                Spacer(Modifier.height(16.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(SIZES) { size -> SizeChip(size, selected = size == "M") }
                }
            }
        }
    }
}

@Composable
fun SizeChip(label: String, selected: Boolean) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = if (selected) Color(0xFF263238) else Color(0xFFECEFF1),
        modifier = Modifier.size(width = 48.dp, height = 36.dp),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(label, color = if (selected) Color.White else Color(0xFF263238), fontSize = 14.sp)
        }
    }
}
