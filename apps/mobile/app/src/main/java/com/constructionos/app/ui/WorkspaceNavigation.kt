package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AccountTree
import androidx.compose.material.icons.rounded.AdminPanelSettings
import androidx.compose.material.icons.rounded.Assignment
import androidx.compose.material.icons.rounded.Business
import androidx.compose.material.icons.rounded.Calculate
import androidx.compose.material.icons.rounded.CloudDone
import androidx.compose.material.icons.rounded.Engineering
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.MoreHoriz
import androidx.compose.material.icons.rounded.People
import androidx.compose.material.icons.rounded.ReceiptLong
import androidx.compose.material.icons.rounded.Sync
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.constructionos.app.core.attendance.AttendanceRepository
import com.constructionos.app.core.authorization.AccessAdminRepository
import com.constructionos.app.core.authorization.ProjectAccessAdminRepository
import com.constructionos.app.core.authorization.ProjectActionMode
import com.constructionos.app.core.authorization.ProjectHomeAction
import com.constructionos.app.core.authorization.ProjectHomeActionKey
import com.constructionos.app.core.authorization.projectHomeActions
import com.constructionos.app.core.boq.BoqFieldRepository
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprLifecycleRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.estimating.EstimatingReviewRepository
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.parties.PartyRepository
import com.constructionos.app.core.wbs.WbsRepository
import com.constructionos.app.core.workforce.WorkforceRepository
import com.constructionos.app.core.workspace.WorkspaceCoordinator
import com.constructionos.app.ui.design.CosActionCard
import com.constructionos.app.ui.design.CosMetricCard
import com.constructionos.app.ui.design.CosProjectHeader
import com.constructionos.app.ui.design.CosSectionHeader
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
import kotlinx.coroutines.launch

private const val PROJECT_SELECTOR_ROUTE = "project-selector"
private const val PROJECT_HOME_ROUTE = "project-home/{projectId}"
private const val ATTENDANCE_ROUTE = "attendance/{projectId}"
private const val DAILY_REPORT_ROUTE = "daily-report/{projectId}"
private const val WORKFORCE_ROUTE = "workforce/{projectId}"
private const val PARTY_DIRECTORY_ROUTE = "party-directory/{projectId}"
private const val WBS_ROUTE = "wbs/{projectId}"
private const val BOQ_ROUTE = "boq/{projectId}"
private const val ESTIMATING_ROUTE = "estimating/{projectId}"
private const val PROJECT_ACCESS_ROUTE = "project-access/{projectId}"
private const val ACCESS_MANAGEMENT_ROUTE = "access-management"

private enum class ProjectTab(val label: String) {
    HOME("Home"),
    FIELD("Field"),
    MORE("More"),
}

@Composable
fun WorkspaceNavigation(
    context: SessionContextResponse,
    workspace: WorkspaceCoordinator,
    attendanceRepository: AttendanceRepository,
    dprRepository: DprRepository,
    dprLifecycleRepository: DprLifecycleRepository,
    partyRepository: PartyRepository,
    wbsRepository: WbsRepository,
    boqFieldRepository: BoqFieldRepository,
    estimatingReviewRepository: EstimatingReviewRepository,
    workforceRepository: WorkforceRepository,
    accessAdminRepository: AccessAdminRepository,
    projectAccessAdminRepository: ProjectAccessAdminRepository,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val navController = rememberNavController()
    val projectFlow = remember(context.organizationId) { workspace.projects(context.organizationId) }
    val projects by projectFlow.collectAsState(initial = emptyList())
    var selectedProjectId by remember(context.organizationId) {
        mutableStateOf(workspace.selectedProjectId(context.organizationId))
    }
    var restoreSavedSelection by rememberSaveable(context.organizationId) { mutableStateOf(true) }
    var startupPrepared by rememberSaveable(context.organizationId) { mutableStateOf(false) }

    LaunchedEffect(context.organizationId) {
        workspace.onAuthenticated()
        startupPrepared = true
    }

    if (!startupPrepared) {
        WorkspaceStartupScreen(modifier = modifier)
        return
    }

    LaunchedEffect(projects, restoreSavedSelection) {
        if (!restoreSavedSelection || projects.isEmpty()) return@LaunchedEffect
        restoreSavedSelection = false
        val selected = selectedProjectId
        if (selected != null && projects.any { it.id == selected }) {
            navController.navigate(projectHomeRoute(selected)) {
                popUpTo(PROJECT_SELECTOR_ROUTE) { inclusive = true }
                launchSingleTop = true
            }
        } else if (selected != null) {
            workspace.clearProjectSelection(context.organizationId)
            selectedProjectId = null
        }
    }

    NavHost(
        navController = navController,
        startDestination = PROJECT_SELECTOR_ROUTE,
        modifier = modifier,
    ) {
        composable(PROJECT_SELECTOR_ROUTE) {
            ProjectSelectorScreen(
                projects = projects,
                selectedProjectId = selectedProjectId,
                onSelectProject = { project ->
                    workspace.selectProject(context.organizationId, project.id)
                    selectedProjectId = project.id
                    navController.navigate(projectHomeRoute(project.id)) { launchSingleTop = true }
                },
                onLogout = onLogout,
            )
        }

        composable(
            route = PROJECT_HOME_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            if (project == null) {
                MissingProjectScreen(
                    onChooseProject = {
                        navController.navigate(PROJECT_SELECTOR_ROUTE) {
                            popUpTo(PROJECT_HOME_ROUTE) { inclusive = true }
                        }
                    },
                )
            } else {
                ProjectWorkspaceScreen(
                    project = project,
                    context = context,
                    attendanceRepository = attendanceRepository,
                    onChooseProject = {
                        restoreSavedSelection = false
                        navController.navigate(PROJECT_SELECTOR_ROUTE)
                    },
                    onOpenAttendance = { navController.navigate(attendanceRoute(project.id)) },
                    onOpenDailyReport = { navController.navigate(dailyReportRoute(project.id)) },
                    onOpenWorkforce = { navController.navigate(workforceRoute(project.id)) },
                    onOpenPartyDirectory = { navController.navigate(partyDirectoryRoute(project.id)) },
                    onOpenWbs = { navController.navigate(wbsRoute(project.id)) },
                    onOpenBoq = { navController.navigate(boqRoute(project.id)) },
                    onOpenEstimating = { navController.navigate(estimatingRoute(project.id)) },
                    onOpenProjectAccess = { navController.navigate(projectAccessRoute(project.id)) },
                    onOpenAccessManagement = { navController.navigate(ACCESS_MANAGEMENT_ROUTE) },
                    onLogout = onLogout,
                )
            }
        }

        composable(
            route = ATTENDANCE_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else {
                AttendanceScreen(
                    project = project,
                    context = context,
                    repository = attendanceRepository,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(
            route = DAILY_REPORT_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else {
                DailyReportHubScreen(
                    project = project,
                    context = context,
                    repository = dprRepository,
                    lifecycleRepository = dprLifecycleRepository,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(
            route = WORKFORCE_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            val permissions = context.projectPermissions(projectId)
            val workforceReleased = context.hasMobileFeature("workforce")
            val canViewWorkers = "workforce.worker.view" in permissions
            val canViewCrews = "workforce.crew.view" in permissions
            val canViewAssignments = "workforce.assignment.view" in permissions
            val canOpenDirectory = canViewCrews || (canViewWorkers && canViewAssignments)
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else if (!workforceReleased || !canOpenDirectory) {
                MissingPermissionScreen(
                    message = "Workforce directory is not available for this project and session.",
                    onBack = { navController.popBackStack() },
                )
            } else {
                WorkforceDirectoryScreen(
                    organizationId = context.organizationId,
                    project = project,
                    repository = workforceRepository,
                    canViewWorkers = canViewWorkers,
                    canViewCrews = canViewCrews,
                    canViewAssignments = canViewAssignments,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(
            route = PARTY_DIRECTORY_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else if ("commercial.party.view" !in context.permissions) {
                MissingPermissionScreen(
                    message = "The server no longer allows Party Directory access for this session.",
                    onBack = { navController.popBackStack() },
                )
            } else {
                PartyDirectoryScreen(
                    organizationId = context.organizationId,
                    project = project,
                    repository = partyRepository,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(
            route = WBS_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            val permissions = context.projectPermissions(projectId)
            val wbsReleased = context.hasMobileFeature("commercial.wbs")
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else if (!wbsReleased || "commercial.wbs.view" !in permissions) {
                MissingPermissionScreen(
                    message = "WBS / Cost Codes are not available for this project and session.",
                    onBack = { navController.popBackStack() },
                )
            } else {
                WbsLookupScreen(
                    project = project,
                    repository = wbsRepository,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(
            route = BOQ_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            val permissions = context.projectPermissions(projectId)
            val boqReleased = context.hasMobileFeature("commercial.boq")
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else if (!boqReleased || "commercial.boq.view" !in permissions) {
                MissingPermissionScreen(
                    message = "Approved BOQ is not available for this project and session.",
                    onBack = { navController.popBackStack() },
                )
            } else {
                BoqLookupScreen(
                    project = project,
                    repository = boqFieldRepository,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(
            route = ESTIMATING_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            val permissions = context.projectPermissions(projectId)
            val estimatingReleased = context.hasMobileFeature("estimating")
            val canViewEstimates = "estimating.estimate.view" in permissions
            val canViewBudgets = "estimating.budget.view" in permissions
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else if (!estimatingReleased || (!canViewEstimates && !canViewBudgets)) {
                MissingPermissionScreen(
                    message = "Estimating / Budget is not available for this project and session.",
                    onBack = { navController.popBackStack() },
                )
            } else {
                EstimatingReviewScreen(
                    project = project,
                    repository = estimatingReviewRepository,
                    canViewEstimates = canViewEstimates,
                    canApproveEstimates = "estimating.estimate.approve" in permissions,
                    canViewBudgets = canViewBudgets,
                    canApproveBudgets = "estimating.budget.approve" in permissions,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(
            route = PROJECT_ACCESS_ROUTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val projectId = backStackEntry.arguments?.getString("projectId").orEmpty()
            val project = projects.firstOrNull { it.id == projectId }
            val permissions = context.projectPermissions(projectId)
            if (project == null) {
                MissingProjectScreen(onChooseProject = { navController.popBackStack() })
            } else if ("projects.membership.view" !in permissions) {
                MissingPermissionScreen(
                    message = "The server no longer allows project membership access for this project.",
                    onBack = { navController.popBackStack() },
                )
            } else {
                ProjectAccessManagementScreen(
                    project = project,
                    repository = projectAccessAdminRepository,
                    canManage = "projects.membership.manage" in permissions,
                    onBack = { navController.popBackStack() },
                )
            }
        }

        composable(ACCESS_MANAGEMENT_ROUTE) {
            if ("security.role.view" !in context.permissions) {
                MissingPermissionScreen(
                    message = "The server no longer allows role and membership access for this session.",
                    onBack = { navController.popBackStack() },
                )
            } else {
                AccessManagementScreen(
                    repository = accessAdminRepository,
                    canManage = "security.role.manage" in context.permissions,
                    onBack = { navController.popBackStack() },
                )
            }
        }
    }
}

private fun SessionContextResponse.projectPermissions(projectId: String): Set<String> =
    permissions.toSet() + projectPermissions[projectId].orEmpty()

private fun SessionContextResponse.hasMobileFeature(featureKey: String): Boolean =
    features.any { it.key == featureKey && it.mobileEnabled }

@Composable
private fun WorkspaceStartupScreen(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .statusBarsPadding()
            .padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(strokeWidth = 3.dp)
        Text(
            "Preparing your site",
            modifier = Modifier.padding(top = 18.dp),
            style = MaterialTheme.typography.titleLarge,
        )
        Text(
            "Latest field data is syncing. Saved device data remains available offline.",
            modifier = Modifier.padding(top = 6.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun ProjectSelectorScreen(
    projects: List<ProjectEntity>,
    selectedProjectId: String?,
    onSelectProject: (ProjectEntity) -> Unit,
    onLogout: () -> Unit,
) {
    Surface(color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .padding(horizontal = 18.dp),
        ) {
            Text(
                "Construction OS",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.padding(top = 18.dp),
            )
            Text(
                "Choose your project",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(top = 22.dp),
            )
            Text(
                "Only server-authorized projects appear here. Swipe and tap into the site you are working on.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp, bottom = 16.dp),
            )
            if (projects.isEmpty()) {
                CosActionCard(
                    title = "No projects cached yet",
                    subtitle = "Connect once to load your authorized project workspace.",
                    icon = Icons.Rounded.Sync,
                    onClick = null,
                    modifier = Modifier.fillMaxWidth(),
                )
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(projects, key = { it.id }) { project ->
                        CosActionCard(
                            title = project.name,
                            subtitle = buildString {
                                append(project.number)
                                append(" • ")
                                append(project.status)
                                project.locality?.takeIf { it.isNotBlank() }?.let {
                                    append(" • ")
                                    append(it)
                                }
                            },
                            icon = Icons.Rounded.Business,
                            onClick = { onSelectProject(project) },
                            badge = if (project.id == selectedProjectId) "Recent" else null,
                            emphasized = project.id == selectedProjectId,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                CosStatusPill("Offline cache ready", CosStatusTone.SUCCESS)
                TextButton(onClick = onLogout) { Text("Sign out") }
            }
        }
    }
}

@Composable
private fun ProjectWorkspaceScreen(
    project: ProjectEntity,
    context: SessionContextResponse,
    attendanceRepository: AttendanceRepository,
    onChooseProject: () -> Unit,
    onOpenAttendance: () -> Unit,
    onOpenDailyReport: () -> Unit,
    onOpenWorkforce: () -> Unit,
    onOpenPartyDirectory: () -> Unit,
    onOpenWbs: () -> Unit,
    onOpenBoq: () -> Unit,
    onOpenEstimating: () -> Unit,
    onOpenProjectAccess: () -> Unit,
    onOpenAccessManagement: () -> Unit,
    onLogout: () -> Unit,
) {
    val actions = remember(context, project.id) { context.projectHomeActions(project.id) }
    val pendingFlow = remember(project.id) { attendanceRepository.observePendingMutationCount(project.id) }
    val attentionFlow = remember(project.id) { attendanceRepository.observeAttentionCount(project.id) }
    val pending by pendingFlow.collectAsState(initial = 0)
    val attention by attentionFlow.collectAsState(initial = 0)
    val canViewPartyDirectory = "commercial.party.view" in context.permissions
    val canViewAccessManagement = "security.role.view" in context.permissions
    val projectPermissions = context.projectPermissions(project.id)
    val canViewWbs = context.hasMobileFeature("commercial.wbs") && "commercial.wbs.view" in projectPermissions
    val canViewBoq = context.hasMobileFeature("commercial.boq") && "commercial.boq.view" in projectPermissions
    val canViewEstimating = context.hasMobileFeature("estimating") && (
        "estimating.estimate.view" in projectPermissions || "estimating.budget.view" in projectPermissions
    )
    val canViewWorkforce = context.hasMobileFeature("workforce") && (
        "workforce.crew.view" in projectPermissions ||
            ("workforce.worker.view" in projectPermissions && "workforce.assignment.view" in projectPermissions)
    )
    val canViewProjectAccess = "projects.membership.view" in projectPermissions
    val tabs = ProjectTab.entries
    val pagerState = rememberPagerState(initialPage = 0, pageCount = { tabs.size })
    val scope = rememberCoroutineScope()

    Surface(color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.fillMaxSize().statusBarsPadding()) {
            CosProjectHeader(
                title = project.name,
                subtitle = "${project.number} • ${project.status}",
                onProjectClick = onChooseProject,
            )
            HorizontalPager(
                state = pagerState,
                modifier = Modifier.weight(1f),
                beyondViewportPageCount = 1,
            ) { page ->
                when (tabs[page]) {
                    ProjectTab.HOME -> ProjectHomeContent(
                        actions = actions,
                        pending = pending,
                        attention = attention,
                        onOpenAttendance = onOpenAttendance,
                        onOpenDailyReport = onOpenDailyReport,
                    )
                    ProjectTab.FIELD -> ProjectFieldContent(
                        actions = actions,
                        onOpenAttendance = onOpenAttendance,
                        onOpenDailyReport = onOpenDailyReport,
                    )
                    ProjectTab.MORE -> ProjectMoreContent(
                        project = project,
                        canViewPartyDirectory = canViewPartyDirectory,
                        canViewWbs = canViewWbs,
                        canViewBoq = canViewBoq,
                        canViewEstimating = canViewEstimating,
                        canViewProjectAccess = canViewProjectAccess,
                        canViewAccessManagement = canViewAccessManagement,
                        onOpenPartyDirectory = onOpenPartyDirectory,
                        onOpenWbs = onOpenWbs,
                        onOpenBoq = onOpenBoq,
                        onOpenEstimating = onOpenEstimating,
                        onOpenProjectAccess = onOpenProjectAccess,
                        onOpenAccessManagement = onOpenAccessManagement,
                        onChooseProject = onChooseProject,
                        onLogout = onLogout,
                    )
                }
            }
            NavigationBar(
                modifier = Modifier.navigationBarsPadding(),
                containerColor = MaterialTheme.colorScheme.surface,
                tonalElevation = 0.dp,
            ) {
                ProjectBottomItem(
                    selected = pagerState.currentPage == ProjectTab.HOME.ordinal,
                    label = "Home",
                    icon = Icons.Rounded.Home,
                    onClick = { scope.launch { pagerState.animateScrollToPage(ProjectTab.HOME.ordinal) } },
                )
                ProjectBottomItem(
                    selected = pagerState.currentPage == ProjectTab.FIELD.ordinal,
                    label = "Field",
                    icon = Icons.Rounded.Engineering,
                    onClick = { scope.launch { pagerState.animateScrollToPage(ProjectTab.FIELD.ordinal) } },
                )
                if (canViewWorkforce) {
                    ProjectBottomItem(
                        selected = false,
                        label = "Crew",
                        icon = Icons.Rounded.Groups,
                        onClick = onOpenWorkforce,
                    )
                }
                ProjectBottomItem(
                    selected = pagerState.currentPage == ProjectTab.MORE.ordinal,
                    label = "More",
                    icon = Icons.Rounded.MoreHoriz,
                    onClick = { scope.launch { pagerState.animateScrollToPage(ProjectTab.MORE.ordinal) } },
                )
            }
        }
    }
}

@Composable
private fun ProjectBottomItem(
    selected: Boolean,
    label: String,
    icon: ImageVector,
    onClick: () -> Unit,
) {
    NavigationBarItem(
        selected = selected,
        onClick = onClick,
        icon = { Icon(icon, contentDescription = label) },
        label = { Text(label) },
        alwaysShowLabel = false,
    )
}

@Composable
private fun ProjectHomeContent(
    actions: List<ProjectHomeAction>,
    pending: Int,
    attention: Int,
    onOpenAttendance: () -> Unit,
    onOpenDailyReport: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            CosSectionHeader(
                title = "Today",
                subtitle = "Your active field workflows and sync health.",
            )
        }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                CosMetricCard(
                    value = pending.toString(),
                    label = if (pending == 1) "change waiting" else "changes waiting",
                    tone = if (pending > 0) CosStatusTone.WARNING else CosStatusTone.SUCCESS,
                    modifier = Modifier.weight(1f),
                )
                CosMetricCard(
                    value = attention.toString(),
                    label = "needs attention",
                    tone = if (attention > 0) CosStatusTone.ERROR else CosStatusTone.SUCCESS,
                    modifier = Modifier.weight(1f),
                )
            }
        }
        if (attention > 0) {
            item {
                CosActionCard(
                    title = "Resolve sync issue",
                    subtitle = "$attention attendance change${if (attention == 1) "" else "s"} need review before the next governed action.",
                    icon = Icons.Rounded.WarningAmber,
                    onClick = onOpenAttendance,
                    emphasized = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        } else if (pending == 0) {
            item {
                CosActionCard(
                    title = "Site data synced",
                    subtitle = "Your local field queue is clear and ready for work.",
                    icon = Icons.Rounded.CloudDone,
                    onClick = null,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        item {
            CosSectionHeader(
                title = "Quick actions",
                subtitle = "Tap a card or swipe to Field for the full set.",
                modifier = Modifier.padding(top = 4.dp),
            )
        }
        if (actions.isEmpty()) {
            item {
                CosActionCard(
                    title = "No field actions available",
                    subtitle = "Your current server permissions do not expose a mobile workflow in this project.",
                    icon = Icons.Rounded.Assignment,
                    onClick = null,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        } else {
            items(actions, key = { it.key.name }) { action ->
                ProjectActionCard(
                    action = action,
                    onClick = actionClick(action, onOpenAttendance, onOpenDailyReport),
                )
            }
        }
    }
}

@Composable
private fun ProjectFieldContent(
    actions: List<ProjectHomeAction>,
    onOpenAttendance: () -> Unit,
    onOpenDailyReport: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            CosSectionHeader(
                title = "Field",
                subtitle = "Fast, one-handed site actions. Swipe left or right to change space.",
            )
        }
        items(actions, key = { it.key.name }) { action ->
            ProjectActionCard(
                action = action,
                onClick = actionClick(action, onOpenAttendance, onOpenDailyReport),
            )
        }
    }
}

private fun actionClick(
    action: ProjectHomeAction,
    onOpenAttendance: () -> Unit,
    onOpenDailyReport: () -> Unit,
): (() -> Unit)? = when (action.key) {
    ProjectHomeActionKey.ATTENDANCE -> onOpenAttendance
    ProjectHomeActionKey.DAILY_REPORT -> onOpenDailyReport
}

@Composable
private fun ProjectActionCard(action: ProjectHomeAction, onClick: (() -> Unit)?) {
    CosActionCard(
        title = action.title,
        subtitle = action.subtitle,
        icon = when (action.key) {
            ProjectHomeActionKey.ATTENDANCE -> Icons.Rounded.Groups
            ProjectHomeActionKey.DAILY_REPORT -> Icons.Rounded.Assignment
        },
        onClick = onClick,
        badge = when (action.mode) {
            ProjectActionMode.WORK -> "Work"
            ProjectActionMode.REVIEW -> "Review"
            ProjectActionMode.VIEW -> "View"
        },
        emphasized = action.mode == ProjectActionMode.WORK,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun ProjectMoreContent(
    project: ProjectEntity,
    canViewPartyDirectory: Boolean,
    canViewWbs: Boolean,
    canViewBoq: Boolean,
    canViewEstimating: Boolean,
    canViewProjectAccess: Boolean,
    canViewAccessManagement: Boolean,
    onOpenPartyDirectory: () -> Unit,
    onOpenWbs: () -> Unit,
    onOpenBoq: () -> Unit,
    onOpenEstimating: () -> Unit,
    onOpenProjectAccess: () -> Unit,
    onOpenAccessManagement: () -> Unit,
    onChooseProject: () -> Unit,
    onLogout: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            CosSectionHeader(
                title = "More",
                subtitle = "Project references, commercial lookups and account controls.",
            )
        }
        item {
            CosActionCard(
                title = project.name,
                subtitle = listOfNotNull(project.number, project.locality).joinToString(" • "),
                icon = Icons.Rounded.Business,
                onClick = onChooseProject,
                badge = "Change",
                modifier = Modifier.fillMaxWidth(),
            )
        }
        if (canViewPartyDirectory) {
            item { MoreCard("Party directory", "Clients, vendors, suppliers and subcontractors.", Icons.Rounded.Business, onOpenPartyDirectory) }
        }
        if (canViewWbs) {
            item { MoreCard("WBS / Cost Codes", "Search the project hierarchy from the field cache.", Icons.Rounded.AccountTree, onOpenWbs) }
        }
        if (canViewBoq) {
            item { MoreCard("Approved BOQ", "Field-safe approved quantities without exposing commercial values.", Icons.Rounded.ReceiptLong, onOpenBoq) }
        }
        if (canViewEstimating) {
            item { MoreCard("Estimating & Budget", "Review governed estimate and budget state.", Icons.Rounded.Calculate, onOpenEstimating) }
        }
        if (canViewProjectAccess) {
            item { MoreCard("Project access", "Project members and project-scoped roles.", Icons.Rounded.People, onOpenProjectAccess) }
        }
        if (canViewAccessManagement) {
            item { MoreCard("People & access", "Company roles, permissions and memberships.", Icons.Rounded.AdminPanelSettings, onOpenAccessManagement) }
        }
        item {
            TextButton(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            ) {
                Text("Sign out")
            }
        }
    }
}

@Composable
private fun MoreCard(
    title: String,
    subtitle: String,
    icon: ImageVector,
    onOpen: () -> Unit,
) {
    CosActionCard(
        title = title,
        subtitle = subtitle,
        icon = icon,
        onClick = onOpen,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun MissingProjectScreen(onChooseProject: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Project is no longer available", style = MaterialTheme.typography.titleLarge)
        Text(
            "Your cached access changed. Choose another project.",
            modifier = Modifier.padding(top = 8.dp, bottom = 16.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(onClick = onChooseProject) { Text("Choose project") }
    }
}

@Composable
private fun MissingPermissionScreen(message: String, onBack: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Access unavailable", style = MaterialTheme.typography.titleLarge)
        Text(
            message,
            modifier = Modifier.padding(top = 8.dp, bottom = 16.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(onClick = onBack) { Text("Back") }
    }
}

private fun projectHomeRoute(projectId: String): String = "project-home/$projectId"
private fun attendanceRoute(projectId: String): String = "attendance/$projectId"
private fun dailyReportRoute(projectId: String): String = "daily-report/$projectId"
private fun workforceRoute(projectId: String): String = "workforce/$projectId"
private fun partyDirectoryRoute(projectId: String): String = "party-directory/$projectId"
private fun wbsRoute(projectId: String): String = "wbs/$projectId"
private fun boqRoute(projectId: String): String = "boq/$projectId"
private fun estimatingRoute(projectId: String): String = "estimating/$projectId"
private fun projectAccessRoute(projectId: String): String = "project-access/$projectId"
