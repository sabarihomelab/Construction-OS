package com.constructionos.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
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

    Column(modifier = modifier.fillMaxSize()) {
        TextButton(
            onClick = onBack,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
        ) {
            Text("Back")
        }
        Text(
            "Additional DPR fields",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(horizontal = 16.dp),
        )
        Text(
            project.name,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 3.dp),
        )
        HorizontalDivider(modifier = Modifier.padding(top = 8.dp))

        if (reports.isEmpty()) {
            Text(
                "Start a Daily Report before entering configured fields.",
                modifier = Modifier.padding(16.dp),
            )
            return@Column
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
        ) {
            Text(
                "Report",
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.padding(top = 12.dp),
            )
            reports.take(MAX_CUSTOM_FIELD_REPORT_CHOICES).forEach { item ->
                OutlinedButton(
                    onClick = { selectedReportId = item.id },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp),
                ) {
                    Text(
                        "${item.reportDate} • ${item.shiftCode} • ${item.status.replace('_', ' ')}" +
                            if (item.id == selectedReportId) " • selected" else "",
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

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
