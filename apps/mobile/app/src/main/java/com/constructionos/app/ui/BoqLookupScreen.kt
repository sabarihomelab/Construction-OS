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
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Description
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
import com.constructionos.app.core.boq.BoqFieldRepository
import com.constructionos.app.core.database.BoqFieldEntity
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
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
                Text("Approved BOQ", style = MaterialTheme.typography.headlineSmall)
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
                "Field-safe approved items only — rates, amounts, tax and budgets stay server-side.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(12.dp),
            )
        }

        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            placeholder = { Text("Search BOQ or item") },
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
                Text("Refreshing approved BOQ…", style = MaterialTheme.typography.bodySmall)
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
                    Icons.Rounded.Description,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(36.dp),
                )
                Text(
                    if (query.isBlank()) "No approved BOQ items cached yet" else "No BOQ item matches '$query'",
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
                items(rows, key = { it.itemId }) { row ->
                    BoqItemCard(row)
                }
            }
        }
    }
}

@Composable
private fun BoqItemCard(row: BoqFieldEntity) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    row.itemCode,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                CosStatusPill(
                    text = row.unitCode,
                    tone = CosStatusTone.PRIMARY,
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            Text(
                row.description,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 7.dp),
            )
            Text(
                "${row.boqCode} · ${row.boqName}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 5.dp),
            )
            Row(
                modifier = Modifier.padding(top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                CosStatusPill("Qty ${row.quantity}")
                CosStatusPill("Line ${row.lineNumber}")
            }
        }
    }
}

private fun boqRefreshError(error: Throwable): String = when (error) {
    is HttpException -> when (error.code()) {
        403 -> "BOQ access is no longer allowed for this project. Cached safe references are kept on the device."
        else -> "Could not refresh approved BOQ from the company server. Cached safe references remain available."
    }
    else -> "Could not refresh approved BOQ. Cached safe references remain available while offline."
}
