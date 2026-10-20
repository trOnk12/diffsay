package dev.sample

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Every knob a real UI change might turn; defaults are the shipped design. */
data class Style(
    val cardPadding: Int = 16,
    val buttonColor: Color = Color(0xFF1E88E5),
    val titleWeight: FontWeight = FontWeight.SemiBold,
    val buttonRadius: Int = 8,
    val buttonText: String = "Pay now",
    val headerAlign: Alignment.Horizontal = Alignment.CenterHorizontally,
    val bodySize: Int = 14,
    val rowGap: Int = 12,
    val noteAlpha: Float = 1f,
    val fieldBorder: Color = Color(0xFFBDBDBD),
    val badgeOffset: Int = 0,
    val bodyLineHeight: Int = 20,
)

@Composable
fun CheckoutScreen(style: Style = Style()) {
    MaterialTheme {
        Column(Modifier.fillMaxSize().background(Color(0xFFF5F5F5)).padding(16.dp)) {
            Column(Modifier.fillMaxWidth(), horizontalAlignment = style.headerAlign) {
                Text("Checkout", fontSize = 22.sp, fontWeight = style.titleWeight, color = Color(0xFF212121))
                Text("2 items · free delivery", fontSize = 13.sp, color = Color(0xFF757575))
            }
            Spacer(Modifier.height(16.dp))
            Card(
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(style.cardPadding.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Wireless earbuds", fontSize = style.bodySize.sp, modifier = Modifier.weight(1f))
                        Surface(color = Color(0xFFE8F5E9), shape = RoundedCornerShape(4.dp),
                            modifier = Modifier.offset(x = style.badgeOffset.dp)) {
                            Text("-20%", fontSize = 12.sp, color = Color(0xFF2E7D32), modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                        }
                    }
                    Spacer(Modifier.height(style.rowGap.dp))
                    Text(
                        "Delivered by Friday. Returns accepted for 30 days after delivery, no questions asked.",
                        fontSize = style.bodySize.sp, lineHeight = style.bodyLineHeight.sp, color = Color(0xFF424242),
                    )
                    Spacer(Modifier.height(style.rowGap.dp))
                    Surface(
                        border = BorderStroke(1.dp, style.fieldBorder), shape = RoundedCornerShape(6.dp),
                        color = Color.White, modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Promo code", fontSize = 14.sp, color = Color(0xFF9E9E9E), modifier = Modifier.padding(12.dp))
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            Text("Prices include VAT.", fontSize = 12.sp, color = Color(0xFF616161), modifier = Modifier.alpha(style.noteAlpha))
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {}, shape = RoundedCornerShape(style.buttonRadius.dp),
                colors = ButtonDefaults.buttonColors(containerColor = style.buttonColor),
                modifier = Modifier.fillMaxWidth().height(48.dp),
            ) { Text(style.buttonText, fontSize = 16.sp, fontWeight = FontWeight.Medium) }
        }
    }
}
