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
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprLifecycleRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.dpr.requireAttendanceSummaryRepository
import com.constructionos.app.core.dpr.requirePhotoRepository
import com.constructionos.app.core.network.SessionContextResponse

enum class DailyReportHubTab(val label: String) {
    ENTRY("Entry"),
    CREW("Crew"),
    PHOTOS("Photos"),
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
    val canViewAttendance = "workforce.attendance.view" in permissions
    val canSubmit = "field.daily_report.submit" in permissions
    val canApprove = "field.daily_report.approve" in permissions
    val canReopen = "field.daily_report.update" in permissions
    val canManage = "field.daily_report.manage" in permissions
    val showReview = canSubmit || canApprove || canReopen || canManage
    val tabs = remember(canViewAttendance, showReview) {
        buildList {
            add(DailyReportHubTab.ENTRY)
            if (canViewAttendance) add(DailyReportHubTab.CREW)
            add(DailyReportHubTab.PHOTOS)
            if (showReview) add(DailyReportHubTab.REVIEW)
        }
    }
    val attendanceSummaryRepository = remember(repository) {
        repository.requireAttendanceSummaryRepository()
    }
    val photoRepository = remember(repository) { repository.requirePhotoRepository() }
    var selected by rememberSaveable(project.id) { mutableStateOf(DailyReportHubTab.ENTRY.name) }
    val selectedTab = DailyReportHubTab.valueOf(selected).let { tab ->
        if (tab in tabs) tab else DailyReportHubTab.ENTRY
    }

    Column(modifier = modifier.fillMaxSize()) {
        Row(modifier = Modifier.fillMaxWidth()) {
            tabs.forEach { tab ->
                Column(modifier = Modifier.weight(1f)) {
                    TextButton(
                        onClick = { selected = tab.name },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            tab.label,
                            fontWeight = if (selectedTab == tab) FontWeight.Bold else FontWeight.Normal,
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                    HorizontalDivider(
                        thickness = if (selectedTab == tab) 3.dp else 1.dp,
                        color = if (selectedTab == tab) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.outlineVariant
                        },
                    )
                }
            }
        }

        when (selectedTab) {
            DailyReportHubTab.ENTRY -> DailyReportScreen(
                project = project,
                context = context,
                repository = repository,
                onBack = onBack,
                modifier = Modifier.weight(1f),
            )
            DailyReportHubTab.CREW -> DprAttendanceSummaryScreen(
                project = project,
                repository = attendanceSummaryRepository,
                onBack = onBack,
                modifier = Modifier.weight(1f),
            )
            DailyReportHubTab.PHOTOS -> DprPhotosScreen(
                project = project,
                context = context,
                dprRepository = repository,
                photoRepository = photoRepository,
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
