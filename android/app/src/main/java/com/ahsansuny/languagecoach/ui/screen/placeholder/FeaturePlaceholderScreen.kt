package com.ahsansuny.languagecoach.ui.screen.placeholder

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.ahsansuny.languagecoach.R
import com.ahsansuny.languagecoach.ui.components.LanguageCoachScaffold

@Composable
fun FeaturePlaceholderRoute(
    title: String,
    body: String,
    onBack: () -> Unit,
) {
    LanguageCoachScaffold(
        title = title,
        subtitle = "Foundation route ready for future feature agents.",
    ) { modifier ->
        Column(
            modifier = modifier,
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
                shape = MaterialTheme.shapes.extraLarge,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(
                        text = body,
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        text = "The navigation contract is stable, so future work can stay focused on feature logic and API contracts.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Button(onClick = onBack) {
                Text(text = stringResource(id = R.string.feature_placeholder_cta))
            }
        }
    }
}
