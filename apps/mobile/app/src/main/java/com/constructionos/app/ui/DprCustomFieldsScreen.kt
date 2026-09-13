package com.constructionos.app.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.authorization.hasProjectPermission
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprCustomFieldRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.network.SessionContextResponse

@Composable
fun DprCustomFieldsScreen(
    project: ProjectEntity,
    context: SessionContextResponse,
    dprRepository: DprRepository,
    customFieldRepository: DprCustomFieldRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val reports by remember(project.id) {
        dprRepository.observeProjectReports(project.id)
    }.collectAsState(initial = emptyList())
    var selectedReportId by rememberSaveable(project.id) { mutableStateOf<String?>(null) }

    LaunchedEffect(reports) {
        val selected = selectedReportId
        if (selected == null || reports.none { it.id == selected }) {
            selectedReportId = reports.firstOrNull { it.status == DprRepository.STATUS_DRAFT }?.id
                ?: reports.firstOrNull()?.id
        }
    }

    val report = reports.firstOrNull { it.id == selectedReportId }
    val canUpdate = context.hasProjectPermission(project.id, "field.daily_report.update")

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
                Text("Additional fields", style = MaterialTheme.typography.headlineSmall)
                Text(
                    project.name,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Surface(
                shape = MaterialTheme.shapes.large,
                color = MaterialTheme.colorScheme.primaryContainer,
            ) {
                Icon(
                    Icons.Rounded.Tune,
                    contentDescription = null,
                    modifier = Modifier.padding(10.dp),
                )
            }
        }

        if (reports.isEmpty()) {
            Surface(
                shape = MaterialTheme.shapes.large,
                color = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) {
                Text(
                    "Start a Daily Report before entering configured fields.",
                    modifier = Modifier.padding(16.dp),
                )
            }
            return@Column
        }

        Text(
            "Report",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(top = 12.dp),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
        ) {
            reports.take(MAX_CUSTOM_FIELD_REPORT_CHOICES).forEach { item ->
                FilterChip(
                    selected = item.id == selectedReportId,
                    onClick = { selectedReportId = item.id },
                    label = {
                        Text("${item.reportDate} • ${item.shiftCode} • ${item.status.replace('_', ' ')}")
                    },
                    modifier = Modifier.padding(end = 8.dp),
                )
            }
        }

        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.42f),
            modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
        ) {
            Text(
                if (report?.status == DprRepository.STATUS_DRAFT && canUpdate) {
                    "Configured project fields save locally first and sync through the same DPR revision queue."
                } else {
                    "Configured fields are read-only for this report state or permission set."
                },
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(11.dp),
            )
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(top = 8.dp),
        ) {
            if (report != null) {
                DprCustomFieldsSection(
                    projectId = project.id,
                    report = report,
                    repository = customFieldRepository,
                    editable = canUpdate && report.status == DprRepository.STATUS_DRAFT,
                )
            }
        }
    }
}

private const val MAX_CUSTOM_FIELD_REPORT_CHOICES = 10
