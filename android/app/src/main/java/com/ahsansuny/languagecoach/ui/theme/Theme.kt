package com.ahsansuny.languagecoach.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF1F6FB2),
    onPrimary = Color(0xFFFFFFFF),
    secondary = Color(0xFF3A8F8D),
    onSecondary = Color(0xFFFFFFFF),
    tertiary = Color(0xFFC24C3A),
    surface = Color(0xFFF6F7FB),
    background = Color(0xFFF6F7FB),
)

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFF8BC2F5),
    onPrimary = Color(0xFF052B4A),
    secondary = Color(0xFF83D0CD),
    onSecondary = Color(0xFF032927),
    tertiary = Color(0xFFFFB4A7),
    surface = Color(0xFF17212B),
    background = Color(0xFF10171F),
)

@Composable
fun LanguageCoachTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme,
        content = content,
    )
}
