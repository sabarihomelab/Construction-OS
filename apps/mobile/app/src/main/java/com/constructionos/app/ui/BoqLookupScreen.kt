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
import com.constructionos.app.core.boq.BoqFieldRepository
import com.constructionos.app.core.database.BoqFieldEntity
import com.constructionos.app.core.database.ProjectEntity
import kotlinx.coroutines.launch
import retrofit2.HttpException

@Composable
fun BoqLookupScreen(
    project: ProjectEntity,
    repository: BoqFieldRepository,
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
            .onFailure { refreshError = boqRefreshError(it) }
        refreshing = false
    }

    LaunchedEffect(project.id) { refresh() }

    Column(modifier = modifier.fillMaxSize()) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            TextButton(onClick = onBack) { Text("Back") }
            Text("Approved BOQ", style = MaterialTheme.typography.headlineSmall)
            Text(
                "${project.number} · ${project.name}",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 3.dp),
            )
            Text(
                "Field-safe approved items only. Rates, amounts, budgets, tax and approval metadata are not downloaded to this screen.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
        HorizontalDivider()

        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            label = { Text("Search BOQ or item") },
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
                    "Refreshing approved BOQ…",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            HorizontalDivider()
        }

        if (rows.isEmpty()) {
            Text(
                if (query.isBlank()) {
                    "No approved BOQ items are cached for this project yet."
                } else {
                    "No approved BOQ item matches '$query'."
                },
                modifier = Modifier.padding(16.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(rows, key = { it.itemId }) { row ->
                    BoqItemRow(row)
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun BoqItemRow(row: BoqFieldEntity) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        Text(
            "${row.itemCode} · ${row.description}",
            style = MaterialTheme.typography.titleSmall,
        )
        Text(
            "${row.boqCode} · ${row.boqName}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 2.dp),
        )
        Text(
            "Qty ${row.quantity} ${row.unitCode} · line ${row.lineNumber}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 3.dp),
        )
    }
}

private fun boqRefreshError(error: Throwable): String = when (error) {
    is HttpException -> when (error.code()) {
        403 -> "BOQ access is no longer allowed for this project. Cached safe references are kept on the device."
        else -> "Could not refresh approved BOQ from the company server. Cached safe references remain available."
    }
    else -> "Could not refresh approved BOQ. Cached safe references remain available while offline."
}
