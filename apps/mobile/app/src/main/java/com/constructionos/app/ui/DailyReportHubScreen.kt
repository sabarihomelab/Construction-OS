package com.constructionos.app.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.EditNote
import androidx.compose.material.icons.rounded.FactCheck
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprLifecycleRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.dpr.requireAttendanceSummaryRepository
import com.constructionos.app.core.dpr.requireCustomFieldRepository
import com.constructionos.app.core.dpr.requirePhotoRepository
import com.constructionos.app.core.network.SessionContextResponse
import kotlinx.coroutines.launch

enum class DailyReportHubTab(
    val label: String,
    val icon: ImageVector,
) {
    ENTRY("Entry", Icons.Rounded.EditNote),
    CREW("Crew", Icons.Rounded.Groups),
    FIELDS("Fields", Icons.Rounded.Tune),
    PHOTOS("Photos", Icons.Rounded.PhotoLibrary),
    REVIEW("Review", Icons.Rounded.FactCheck),
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
    val attendanceSummaryRepository = remember(repository) {
        repository.requireAttendanceSummaryRepository()
    }
    val customFieldRepository = remember(repository) {
        repository.requireCustomFieldRepository()
    }
    val photoRepository = remember(repository) { repository.requirePhotoRepository() }
    val customDefinitions by remember(project.id) {
        customFieldRepository.observeDefinitions(project.id)
    }.collectAsState(initial = emptyList())
    val hasCustomFields = customDefinitions.isNotEmpty()

    LaunchedEffect(project.id, context.configurationRevision) {
        runCatching { customFieldRepository.refreshDefinitions(project.id) }
    }

    val tabs = remember(canViewAttendance, hasCustomFields, showReview) {
        buildList {
            add(DailyReportHubTab.ENTRY)
            if (canViewAttendance) add(DailyReportHubTab.CREW)
            if (hasCustomFields) add(DailyReportHubTab.FIELDS)
            add(DailyReportHubTab.PHOTOS)
            if (showReview) add(DailyReportHubTab.REVIEW)
        }
    }
    val pagerState = rememberPagerState(initialPage = 0, pageCount = { tabs.size })
    val scope = rememberCoroutineScope()

    LaunchedEffect(tabs.size) {
        if (pagerState.currentPage >= tabs.size) pagerState.scrollToPage(0)
    }

    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                tabs.forEachIndexed { index, tab ->
                    FilterChip(
                        selected = pagerState.currentPage == index,
                        onClick = { scope.launch { pagerState.animateScrollToPage(index) } },
                        label = { Text(tab.label) },
                        leadingIcon = {
                            Icon(
                                imageVector = tab.icon,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp),
                            )
                        },
                    )
                }
            }

            HorizontalPager(
                state = pagerState,
                modifier = Modifier.weight(1f),
                beyondViewportPageCount = 1,
            ) { page ->
                when (tabs[page]) {
                    DailyReportHubTab.ENTRY -> DailyReportScreen(
                        project = project,
                        context = context,
                        repository = repository,
                        onBack = onBack,
                        modifier = Modifier.fillMaxSize(),
                    )
                    DailyReportHubTab.CREW -> DprAttendanceSummaryScreen(
                        project = project,
                        repository = attendanceSummaryRepository,
                        onBack = onBack,
                        modifier = Modifier.fillMaxSize(),
                    )
                    DailyReportHubTab.FIELDS -> DprCustomFieldsScreen(
                        project = project,
                        context = context,
                        dprRepository = repository,
                        customFieldRepository = customFieldRepository,
                        onBack = onBack,
                        modifier = Modifier.fillMaxSize(),
                    )
                    DailyReportHubTab.PHOTOS -> DprPhotosScreen(
                        project = project,
                        context = context,
                        dprRepository = repository,
                        photoRepository = photoRepository,
                        onBack = onBack,
                        modifier = Modifier.fillMaxSize(),
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
    }
}
