package dev.sample

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Composable
fun LoginScreen() {
    MaterialTheme {
        Surface(color = Color(0xFFFFFFFF)) {
            Column(Modifier.fillMaxSize().padding(horizontal = 28.dp, vertical = 40.dp)) {
                Text("Welcome back", style = MaterialTheme.typography.headlineMedium)
                Text(
                    "Sign in to continue to your workspace",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFF6B6B6B),
                )
                Spacer(Modifier.height(32.dp))
                OutlinedTextField(value = "ada@example.com", onValueChange = {}, label = { Text("Email") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(value = "", onValueChange = {}, label = { Text("Password") }, modifier = Modifier.fillMaxWidth())
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = {}) { Text("Forgot password?") }
                }
                Spacer(Modifier.height(16.dp))
                Button(onClick = {}, enabled = true, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("Sign in") }
                Spacer(Modifier.height(20.dp))
                Box(
                    Modifier.fillMaxWidth().border(1.dp, Color(0xFFE0E0E0), RoundedCornerShape(8.dp)).padding(12.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("New here? Create an account", textAlign = TextAlign.Center, color = Color(0xFF1A73E8))
                }
            }
        }
    }
}
