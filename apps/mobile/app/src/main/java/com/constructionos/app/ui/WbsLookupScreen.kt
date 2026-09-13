package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AccountTree
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.database.WbsEntity
import com.constructionos.app.core.wbs.WbsRepository
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
import kotlinx.coroutines.launch
import retrofit2.HttpException

@Composable
fun WbsLookupScreen(
    project: ProjectEntity,
    repository: WbsRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scope = rememberCoroutineScope()
    var query by remember(project.id) { mutableStateOf("") }
    var refreshing by remember(project.id) { mutableStateOf(false) }
    var refreshError by remember(project.id) { mutableStateOf<String?>(null) }
    val rowsFlow = remember(project.id, query) { repository.observe(project.id, query) }
    val rows by rowsFlow.collectAsState(initial = emptyList())

    suspend fun refresh() {
        refreshing = true
        refreshError = null
        runCatching { repository.refresh(project.id) }
            .onFailure { refreshError = wbsRefreshError(it) }
        refreshing = false
    }

    LaunchedEffect(project.id) { refresh() }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Rounded.ArrowBack, contentDescription = "Back")
            }
            Column(modifier = Modifier.weight(1f)) {
                Text("WBS / Cost Codes", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "${project.number} · ${project.name}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = { scope.launch { refresh() } }, enabled = !refreshing) {
                Icon(Icons.Rounded.Refresh, contentDescription = "Refresh")
            }
        }

        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp),
        ) {
            Text(
                "Field-safe structure only — BOQ rates, amounts and budgets stay server-side.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(12.dp),
            )
        }

        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            placeholder = { Text("Search code, name or path") },
            leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
            singleLine = true,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 10.dp),
        )

        when {
            refreshError != null -> Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) {
                Text(refreshError!!, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(10.dp))
            }
            refreshing -> Row(
                modifier = Modifier.padding(top = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                Text("Refreshing WBS…", style = MaterialTheme.typography.bodySmall)
            }
        }

        if (rows.isEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 28.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(
                    Icons.Rounded.AccountTree,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(36.dp),
                )
                Text(
                    if (query.isBlank()) "No WBS cached yet" else "No WBS matches '$query'",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 10.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(top = 10.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(rows, key = { it.id }) { row ->
                    WbsCard(row = row, searching = query.isNotBlank())
                }
            }
        }
    }
}

@Composable
private fun WbsCard(
    row: WbsEntity,
    searching: Boolean,
) {
    val indentation = if (searching) 0.dp else (row.depth.coerceAtMost(3) * 10).dp
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = indentation),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    row.code,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    row.name,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier
                        .weight(1f)
                        .padding(start = 8.dp),
                )
                CosStatusPill(
                    text = wbsKindLabel(row.kind),
                    tone = if (row.kind == "cost_code") CosStatusTone.PRIMARY else CosStatusTone.NEUTRAL,
                )
            }
            Row(
                modifier = Modifier.padding(top = 7.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                CosStatusPill(row.status, tone = if (row.status == "active") CosStatusTone.SUCCESS else CosStatusTone.NEUTRAL)
                if (row.childCount > 0) CosStatusPill("${row.childCount} children")
            }
            if (searching && row.pathCodes.isNotBlank()) {
                Text(
                    row.pathCodes,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 7.dp),
                )
            }
            row.description?.takeIf { it.isNotBlank() }?.let { description ->
                Text(
                    description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
}

private fun wbsKindLabel(kind: String): String = when (kind) {
    "group" -> "Group"
    "trade" -> "Trade"
    "work_package" -> "Work package"
    "cost_code" -> "Cost code"
    else -> kind.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

private fun wbsRefreshError(error: Throwable): String = when (error) {
    is HttpException -> when (error.code()) {
        403 -> "WBS access is no longer allowed for this project. Cached data is kept on the device."
        else -> "Could not refresh WBS from the company server. Cached data remains available."
    }
    else -> "Could not refresh WBS. Cached data remains available while offline."
}
