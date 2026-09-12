package com.constructionos.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprLifecycleRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.network.SessionContextResponse

enum class DailyReportHubTab(val label: String) {
    ENTRY("Entry"),
    REVIEW("Review"),
}

@Composable
fun DailyReportHubScreen(
    project: ProjectEntity,
    context: SessionContextResponse,
    repository: DprRepository,
    lifecycleRepository: DprLifecycleRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val permissions = context.permissions.toSet() + context.projectPermissions[project.id].orEmpty()
    val canSubmit = "field.daily_report.submit" in permissions
    val canApprove = "field.daily_report.approve" in permissions
    val canReopen = "field.daily_report.update" in permissions
    val canManage = "field.daily_report.manage" in permissions
    val showReview = canSubmit || canApprove || canReopen || canManage
    var selected by rememberSaveable(project.id) { mutableStateOf(DailyReportHubTab.ENTRY.name) }

    if (!showReview) {
        DailyReportScreen(
            project = project,
            context = context,
            repository = repository,
            onBack = onBack,
            modifier = modifier,
        )
        return
    }

    Column(modifier = modifier.fillMaxSize()) {
        Row(modifier = Modifier.fillMaxWidth()) {
            DailyReportHubTab.entries.forEach { tab ->
                Column(modifier = Modifier.weight(1f)) {
                    TextButton(
                        onClick = { selected = tab.name },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            tab.label,
                            fontWeight = if (selected == tab.name) FontWeight.Bold else FontWeight.Normal,
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                    HorizontalDivider(
                        thickness = if (selected == tab.name) 3.dp else 1.dp,
                        color = if (selected == tab.name) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.outlineVariant
                        },
                    )
                }
            }
        }

        when (DailyReportHubTab.valueOf(selected)) {
            DailyReportHubTab.ENTRY -> DailyReportScreen(
                project = project,
                context = context,
                repository = repository,
                onBack = onBack,
                modifier = Modifier.weight(1f),
            )
            DailyReportHubTab.REVIEW -> DprReviewScreen(
                project = project,
                dprRepository = repository,
                lifecycleRepository = lifecycleRepository,
                canSubmit = canSubmit,
                canApprove = canApprove,
                canReopen = canReopen,
                canManage = canManage,
                onBack = onBack,
            )
        }
    }
}
