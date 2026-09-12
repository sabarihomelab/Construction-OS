package com.constructionos.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.database.WbsEntity
import com.constructionos.app.core.wbs.WbsRepository
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

    Column(modifier = modifier.fillMaxSize()) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            TextButton(onClick = onBack) { Text("Back") }
            Text("WBS / Cost Codes", style = MaterialTheme.typography.headlineSmall)
            Text(
                "${project.number} · ${project.name}",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 3.dp),
            )
            Text(
                "Field-safe project structure only. BOQ rates, amounts and budgets are not downloaded here.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
        HorizontalDivider()

        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            label = { Text("Search code, name or path") },
            singleLine = true,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 10.dp),
        )

        if (refreshError != null) {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Text(
                    refreshError!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
                TextButton(onClick = { scope.launch { refresh() } }, enabled = !refreshing) {
                    Text("Retry refresh")
                }
            }
            HorizontalDivider()
        } else if (refreshing) {
            Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                CircularProgressIndicator(modifier = Modifier.width(18.dp), strokeWidth = 2.dp)
                Text(
                    "Refreshing WBS…",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            HorizontalDivider()
        }

        if (rows.isEmpty()) {
            Text(
                if (query.isBlank()) {
                    "No WBS is cached for this project yet."
                } else {
                    "No WBS matches '$query'."
                },
                modifier = Modifier.padding(16.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(rows, key = { it.id }) { row ->
                    WbsRow(row = row, searching = query.isNotBlank())
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun WbsRow(
    row: WbsEntity,
    searching: Boolean,
) {
    val indentation = if (searching) 0.dp else (row.depth.coerceAtMost(4) * 16).dp
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 16.dp + indentation, end = 16.dp, top = 9.dp, bottom = 9.dp),
    ) {
        Text(
            "${row.code} · ${row.name}",
            style = MaterialTheme.typography.titleSmall,
        )
        Text(
            "${wbsKindLabel(row.kind)} · ${row.status}${if (row.childCount > 0) " · ${row.childCount} children" else ""}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 2.dp),
        )
        if (searching && row.pathCodes.isNotBlank()) {
            Text(
                row.pathCodes,
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.padding(top = 3.dp),
            )
        }
        row.description?.takeIf { it.isNotBlank() }?.let { description ->
            Text(
                description,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 3.dp),
            )
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
