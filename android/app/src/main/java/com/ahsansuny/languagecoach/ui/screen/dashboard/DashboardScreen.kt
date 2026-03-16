package com.ahsansuny.languagecoach.ui.screen.dashboard

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.ahsansuny.languagecoach.R
import com.ahsansuny.languagecoach.core.config.RuntimeEnvironment
import com.ahsansuny.languagecoach.ui.components.FeatureCard
import com.ahsansuny.languagecoach.ui.components.LanguageCoachScaffold
import com.ahsansuny.languagecoach.ui.components.MetricStrip
import com.ahsansuny.languagecoach.ui.navigation.AppDestination

private data class DashboardFeature(
    val route: String,
    val title: String,
    val summary: String,
    val status: String,
)

@Composable
fun DashboardRoute(
    onNavigate: (String) -> Unit,
    onSignOut: () -> Unit,
) {
    val features = listOf(
        DashboardFeature(
            route = AppDestination.Languages,
            title = stringResource(id = R.string.feature_languages),
            summary = "Navigation foundation for French and Spanish learning paths.",
            status = "nav ready",
        ),
        DashboardFeature(
            route = AppDestination.Lessons,
            title = stringResource(id = R.string.feature_lessons),
            summary = "Room cache and repository interfaces are prepared for lesson ingestion.",
            status = "data ready",
        ),
        DashboardFeature(
            route = AppDestination.Vocabulary,
            title = stringResource(id = R.string.feature_vocabulary),
            summary = "Vocabulary sync, filters, and future SRS hooks plug into this route.",
            status = "cache ready",
        ),
        DashboardFeature(
            route = AppDestination.Practice,
            title = stringResource(id = R.string.feature_practice),
            summary = "Quiz, flashcards, dictation, and speaking branches are reserved.",
            status = "shell ready",
        ),
        DashboardFeature(
            route = AppDestination.Progress,
            title = stringResource(id = R.string.feature_progress),
            summary = "Progress snapshots already have local storage and repository contracts.",
            status = "sync ready",
        ),
        DashboardFeature(
            route = AppDestination.Resources,
            title = stringResource(id = R.string.feature_resources),
            summary = "Resources and offline packs can be attached without changing app structure.",
            status = "future",
        ),
    )

    LanguageCoachScaffold(
        title = stringResource(id = R.string.dashboard_title),
        subtitle = stringResource(id = R.string.dashboard_subtitle),
        action = {
            TextButton(onClick = onSignOut) {
                Text(text = stringResource(id = R.string.dashboard_sign_out))
            }
        },
    ) { modifier ->
        Column(
            modifier = modifier.verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            MetricStrip(
                metrics = listOf(
                    "Env" to RuntimeEnvironment.current.flavor.name.lowercase(),
                    "Host" to RuntimeEnvironment.current.baseUrlHost,
                    "Stack" to "Compose",
                ),
            )

            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                ),
                shape = MaterialTheme.shapes.extraLarge,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        text = "Foundation status",
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        text = "Build flavors, Hilt, Retrofit, Room, bearer-token auth scaffolding, and Compose navigation are all wired for future feature agents.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }

            features.forEach { feature ->
                FeatureCard(
                    title = feature.title,
                    summary = feature.summary,
                    chipLabel = feature.status,
                    onClick = { onNavigate(feature.route) },
                )
            }
        }
    }
}
