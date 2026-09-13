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
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
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
import com.constructionos.app.core.database.WorkforceCrewDirectoryRow
import com.constructionos.app.core.database.WorkforceWorkerDirectoryRow
import com.constructionos.app.core.workforce.WorkforceRepository
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
import kotlinx.coroutines.launch

private enum class WorkforceDirectoryTab {
    WORKERS,
    CREWS,
}

@Composable
fun WorkforceDirectoryScreen(
    organizationId: String,
    project: ProjectEntity,
    repository: WorkforceRepository,
    canViewWorkers: Boolean,
    canViewCrews: Boolean,
    canViewAssignments: Boolean,
    onBack: () -> Unit,
) {
    val canShowWorkers = canViewWorkers && canViewAssignments
    var selectedTab by remember(project.id, canShowWorkers, canViewCrews) {
        mutableStateOf(
            if (canShowWorkers) WorkforceDirectoryTab.WORKERS else WorkforceDirectoryTab.CREWS,
        )
    }
    var query by remember(project.id) { mutableStateOf("") }
    var refreshing by remember(project.id) { mutableStateOf(false) }
    var refreshError by remember(project.id) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    val workerFlow = remember(project.id, query) {
        repository.observeProjectWorkers(project.id, query)
    }
    val workers by workerFlow.collectAsState(initial = emptyList())
    val crewFlow = remember(organizationId, project.id, query) {
        repository.observeCrews(organizationId, project.id, query)
    }
    val crews by crewFlow.collectAsState(initial = emptyList())

    fun refresh() {
        scope.launch {
            refreshing = true
            refreshError = null
            repository.refresh(
                organizationId = organizationId,
                projectId = project.id,
                canViewWorkers = canViewWorkers,
                canViewCrews = canViewCrews,
                canViewAssignments = canViewAssignments,
            ).onFailure {
                refreshError = "Could not refresh workforce. Saved device data is still available."
            }
            refreshing = false
        }
    }

    LaunchedEffect(project.id, canViewWorkers, canViewCrews, canViewAssignments) { refresh() }

    Column(
        modifier = Modifier
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
                Text("Workforce", style = MaterialTheme.typography.headlineSmall)
                Text(
                    project.name,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (refreshing) {
                CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                IconButton(onClick = ::refresh) {
                    Icon(Icons.Rounded.Refresh, contentDescription = "Refresh")
                }
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
                "Project workers and crews are cached for fast field lookup. Commercial rates remain server-side.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(12.dp),
            )
        }

        refreshError?.let {
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) {
                Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(10.dp))
            }
        }

        Row(
            modifier = Modifier.padding(top = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (canShowWorkers) {
                FilterChip(
                    selected = selectedTab == WorkforceDirectoryTab.WORKERS,
                    onClick = { selectedTab = WorkforceDirectoryTab.WORKERS },
                    label = { Text("Workers ${workers.size}") },
                )
            }
            if (canViewCrews) {
                FilterChip(
                    selected = selectedTab == WorkforceDirectoryTab.CREWS,
                    onClick = { selectedTab = WorkforceDirectoryTab.CREWS },
                    label = { Text("Crews ${crews.size}") },
                )
            }
        }

        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            placeholder = {
                Text(if (selectedTab == WorkforceDirectoryTab.WORKERS) "Search workers" else "Search crews")
            },
            leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
            singleLine = true,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 6.dp),
        )

        if (refreshing && workers.isEmpty() && crews.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator()
                Text("Loading workforce…", modifier = Modifier.padding(top = 12.dp))
            }
        } else {
            when (selectedTab) {
                WorkforceDirectoryTab.WORKERS -> WorkerList(workers, Modifier.weight(1f))
                WorkforceDirectoryTab.CREWS -> CrewList(crews, Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun WorkerList(
    rows: List<WorkforceWorkerDirectoryRow>,
    modifier: Modifier = Modifier,
) {
    if (rows.isEmpty()) {
        EmptyWorkforceState(
            "No project workers match this search. If offline, the last saved project workforce is shown when available.",
            modifier,
        )
        return
    }

    LazyColumn(
        modifier = modifier.padding(top = 10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(rows, key = { it.assignmentId }) { row ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.large,
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(modifier = Modifier.padding(15.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                row.displayName,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                row.workerNumber,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(top = 2.dp),
                            )
                        }
                        CosStatusPill(
                            row.assignmentStatus.replace('_', ' '),
                            tone = if (row.assignmentStatus == "active") CosStatusTone.SUCCESS else CosStatusTone.NEUTRAL,
                        )
                    }
                    val descriptors = listOfNotNull(row.projectRole, row.trade, row.jobTitle).distinct()
                    if (descriptors.isNotEmpty()) {
                        Text(
                            descriptors.joinToString(" • "),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                    }
                    Row(
                        modifier = Modifier.padding(top = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(7.dp),
                    ) {
                        row.crewName?.let { CosStatusPill("Crew: $it", tone = CosStatusTone.PRIMARY) }
                        row.engagementType?.let { CosStatusPill(it.replace('_', ' ')) }
                    }
                    row.defaultCostCode?.let {
                        Text(
                            "Default cost code: $it",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 7.dp),
                        )
                    }
                    if (row.startDate != null || row.endDate != null) {
                        Text(
                            "Assignment: ${row.startDate ?: "open"} → ${row.endDate ?: "open"}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 3.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CrewList(
    rows: List<WorkforceCrewDirectoryRow>,
    modifier: Modifier = Modifier,
) {
    if (rows.isEmpty()) {
        EmptyWorkforceState(
            "No crews match this search. If offline, the last saved company crews are shown when available.",
            modifier,
        )
        return
    }

    LazyColumn(
        modifier = modifier.padding(top = 10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(rows, key = { it.id }) { row ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.large,
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(modifier = Modifier.padding(15.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            row.name,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.weight(1f),
                        )
                        CosStatusPill(
                            row.status.replace('_', ' '),
                            tone = if (row.status == "active") CosStatusTone.SUCCESS else CosStatusTone.NEUTRAL,
                        )
                    }
                    Text(
                        "${row.assignedCount} active project assignment${if (row.assignedCount == 1) "" else "s"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 7.dp),
                    )
                    row.supervisorName?.let {
                        CosStatusPill(
                            "Supervisor: $it",
                            tone = CosStatusTone.PRIMARY,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyWorkforceState(message: String, modifier: Modifier) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Rounded.Groups,
            contentDescription = null,
            modifier = Modifier.size(38.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 10.dp),
        )
    }
}
