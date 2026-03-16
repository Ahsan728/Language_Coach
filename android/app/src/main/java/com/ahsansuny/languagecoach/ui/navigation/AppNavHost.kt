package com.ahsansuny.languagecoach.ui.navigation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.ahsansuny.languagecoach.R
import com.ahsansuny.languagecoach.domain.repository.AppSessionState
import com.ahsansuny.languagecoach.ui.AppStateViewModel
import com.ahsansuny.languagecoach.ui.screen.auth.LoginRoute
import com.ahsansuny.languagecoach.ui.screen.dashboard.DashboardRoute
import com.ahsansuny.languagecoach.ui.screen.placeholder.FeaturePlaceholderRoute

@Composable
fun AppNavHost(
    navController: NavHostController = rememberNavController(),
    appStateViewModel: AppStateViewModel = hiltViewModel(),
) {
    val sessionState = appStateViewModel.sessionState.collectAsStateWithLifecycle().value

    NavHost(
        navController = navController,
        startDestination = AppDestination.Splash,
    ) {
        composable(AppDestination.Splash) {
            SplashRoute(
                sessionState = sessionState,
                onNavigateToLogin = {
                    navController.navigate(AppDestination.Login) {
                        popUpTo(AppDestination.Splash) { inclusive = true }
                    }
                },
                onNavigateToDashboard = {
                    navController.navigate(AppDestination.Dashboard) {
                        popUpTo(AppDestination.Splash) { inclusive = true }
                    }
                },
            )
        }
        composable(AppDestination.Login) {
            LoginRoute(
                onSignedIn = {
                    navController.navigate(AppDestination.Dashboard) {
                        popUpTo(AppDestination.Login) { inclusive = true }
                    }
                },
            )
        }
        composable(AppDestination.Dashboard) {
            DashboardRoute(
                onSignOut = {
                    appStateViewModel.signOut()
                    navController.navigate(AppDestination.Login) {
                        popUpTo(AppDestination.Dashboard) { inclusive = true }
                    }
                },
                onNavigate = { route -> navController.navigate(route) },
            )
        }
        composable(AppDestination.Languages) {
            FeaturePlaceholderRoute(
                title = "Languages",
                body = "Language selection, CEFR grouping, and next-lesson recommendations attach here.",
                onBack = { navController.popBackStack() },
            )
        }
        composable(AppDestination.Lessons) {
            FeaturePlaceholderRoute(
                title = "Lessons",
                body = "Lesson detail, grammar blocks, and download support plug into this route.",
                onBack = { navController.popBackStack() },
            )
        }
        composable(AppDestination.Vocabulary) {
            FeaturePlaceholderRoute(
                title = "Vocabulary",
                body = "Search, category filtering, and spaced-repetition hooks fit this screen.",
                onBack = { navController.popBackStack() },
            )
        }
        composable(AppDestination.Practice) {
            FeaturePlaceholderRoute(
                title = "Practice",
                body = "Quiz, flashcards, review, dictation, and speaking flows will branch from here.",
                onBack = { navController.popBackStack() },
            )
        }
        composable(AppDestination.Progress) {
            FeaturePlaceholderRoute(
                title = "Progress",
                body = "Progress snapshots and sync status belong in this area once the APIs land.",
                onBack = { navController.popBackStack() },
            )
        }
        composable(AppDestination.Resources) {
            FeaturePlaceholderRoute(
                title = "Resources",
                body = "Local resources, study links, and future offline downloads can be surfaced here.",
                onBack = { navController.popBackStack() },
            )
        }
    }
}

@Composable
private fun SplashRoute(
    sessionState: AppSessionState,
    onNavigateToLogin: () -> Unit,
    onNavigateToDashboard: () -> Unit,
) {
    LaunchedEffect(sessionState) {
        when (sessionState) {
            AppSessionState.Loading -> Unit
            is AppSessionState.Authenticated -> onNavigateToDashboard()
            AppSessionState.Unauthenticated -> onNavigateToLogin()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Text(
            text = stringResource(id = R.string.splash_loading),
            modifier = Modifier.padding(top = 16.dp),
            style = MaterialTheme.typography.bodyLarge,
        )
    }
}
