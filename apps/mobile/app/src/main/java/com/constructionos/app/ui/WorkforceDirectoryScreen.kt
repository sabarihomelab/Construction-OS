package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.database.WorkforceCrewDirectoryRow
import com.constructionos.app.core.database.WorkforceWorkerDirectoryRow
import com.constructionos.app.core.workforce.WorkforceRepository
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

    LaunchedEffect(project.id, canViewWorkers, canViewCrews, canViewAssignments) {
        refresh()
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Column(modifier = Modifier.weight(1f).padding(start = 4.dp)) {
                Text("Workforce", style = MaterialTheme.typography.titleLarge)
                Text(project.name, style = MaterialTheme.typography.bodySmall)
            }
            OutlinedButton(onClick = { refresh() }, enabled = !refreshing) {
                Text(if (refreshing) "Refreshing" else "Refresh")
            }
        }
        HorizontalDivider()

        Text(
            "Project workers and crews are cached for fast lookup. Worker commercial rates are not downloaded to this screen.",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
        )

        refreshError?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (canShowWorkers) {
                if (selectedTab == WorkforceDirectoryTab.WORKERS) {
                    Button(onClick = { selectedTab = WorkforceDirectoryTab.WORKERS }) { Text("Workers") }
                } else {
                    OutlinedButton(onClick = { selectedTab = WorkforceDirectoryTab.WORKERS }) { Text("Workers") }
                }
            }
            if (canViewCrews) {
                if (selectedTab == WorkforceDirectoryTab.CREWS) {
                    Button(onClick = { selectedTab = WorkforceDirectoryTab.CREWS }) { Text("Crews") }
                } else {
                    OutlinedButton(onClick = { selectedTab = WorkforceDirectoryTab.CREWS }) { Text("Crews") }
                }
            }
        }

        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            label = { Text(if (selectedTab == WorkforceDirectoryTab.WORKERS) "Search workers" else "Search crews") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
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
                WorkforceDirectoryTab.WORKERS -> WorkerList(workers)
                WorkforceDirectoryTab.CREWS -> CrewList(crews)
            }
        }
    }
}

@Composable
private fun WorkerList(rows: List<WorkforceWorkerDirectoryRow>) {
    if (rows.isEmpty()) {
        Text(
            "No project workers match this search. If offline, the last saved project workforce is shown when available.",
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
        return
    }

    LazyColumn(modifier = Modifier.fillMaxSize()) {
        items(rows, key = { it.assignmentId }) { row ->
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 11.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(row.displayName, style = MaterialTheme.typography.titleMedium)
                    Text(row.assignmentStatus.replace('_', ' '), style = MaterialTheme.typography.labelMedium)
                }
                Text(row.workerNumber, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 2.dp))
                listOfNotNull(row.projectRole, row.trade, row.jobTitle)
                    .distinct()
                    .takeIf { it.isNotEmpty() }
                    ?.let { Text(it.joinToString(" • "), modifier = Modifier.padding(top = 4.dp)) }
                row.crewName?.let {
                    Text("Crew: $it", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
                }
                row.engagementType?.let {
                    Text("Engagement: ${it.replace('_', ' ')}", style = MaterialTheme.typography.bodySmall)
                }
                row.defaultCostCode?.let {
                    Text("Default cost code: $it", style = MaterialTheme.typography.bodySmall)
                }
                if (row.startDate != null || row.endDate != null) {
                    Text(
                        "Assignment: ${row.startDate ?: "open"} → ${row.endDate ?: "open"}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            HorizontalDivider()
        }
    }
}

@Composable
private fun CrewList(rows: List<WorkforceCrewDirectoryRow>) {
    if (rows.isEmpty()) {
        Text(
            "No crews match this search. If offline, the last saved company crews are shown when available.",
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
        return
    }

    LazyColumn(modifier = Modifier.fillMaxSize()) {
        items(rows, key = { it.id }) { row ->
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 11.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(row.name, style = MaterialTheme.typography.titleMedium)
                    Text(row.status.replace('_', ' '), style = MaterialTheme.typography.labelMedium)
                }
                Text(
                    "${row.assignedCount} active project assignment${if (row.assignedCount == 1) "" else "s"}",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 3.dp),
                )
                row.supervisorName?.let {
                    Text("Supervisor: $it", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
                }
            }
            HorizontalDivider()
        }
    }
}
