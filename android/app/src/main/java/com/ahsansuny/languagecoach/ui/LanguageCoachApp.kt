package com.ahsansuny.languagecoach.ui

import androidx.compose.runtime.Composable
import com.ahsansuny.languagecoach.ui.navigation.AppNavHost
import com.ahsansuny.languagecoach.ui.theme.LanguageCoachTheme

@Composable
fun LanguageCoachApp() {
    LanguageCoachTheme {
        AppNavHost()
    }
}
