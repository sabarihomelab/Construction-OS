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
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.estimating.EstimatingReviewRepository
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.parties.PartyRepository
import com.constructionos.app.core.wbs.WbsRepository
import com.constructionos.app.core.workspace.WorkspaceCoordinator

private const val PROJECT_SELECTOR_ROUTE = "project-selector"
private const val PROJECT_HOME_ROUTE = "project-home/{projectId}"
private const val ATTENDANCE_ROUTE = "attendance/{projectId}"
private const val DAILY_REPORT_ROUTE = "daily-report/{projectId}"
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
    partyRepository: PartyRepository,
    wbsRepository: WbsRepository,
    boqFieldRepository: BoqFieldRepository,
    estimatingReviewRepository: EstimatingReviewRepository,
    accessAdminRepository: AccessAdminRepository,
    projectAccessAdminRepository: ProjectAccessAdminRepository,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val navController = rememberNavController()
    val projectFlow = remember(context.organizationId) {
        workspace.projects(context.organizationId)
    }
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
                    navController.navigate(projectHomeRoute(project.id)) {
                        launchSingleTop = true
                    }
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
                DailyReportScreen(
                    project = project,
                    context = context,
                    repository = dprRepository,
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
        modifier = modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator()
        Text("Syncing latest site data…", modifier = Modifier.padding(top = 16.dp), style = MaterialTheme.typography.bodyLarge)
        Text("If the site is offline, saved device data opens automatically.", modifier = Modifier.padding(top = 6.dp), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ProjectSelectorScreen(
    projects: List<ProjectEntity>,
    selectedProjectId: String?,
    onSelectProject: (ProjectEntity) -> Unit,
    onLogout: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text("Construction OS", style = MaterialTheme.typography.headlineMedium)
        Text(text = "Choose project", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 6.dp))
        Text(text = "Only projects authorized by the server are shown.", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 3.dp, bottom = 12.dp))
        if (projects.isEmpty()) {
            Text(text = "No saved projects yet. Connect once to load your authorized projects.", modifier = Modifier.padding(top = 16.dp))
        } else {
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(projects, key = { it.id }) { project ->
                    TextButton(onClick = { onSelectProject(project) }, modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalAlignment = Alignment.Start) {
                            Text(project.name, style = MaterialTheme.typography.titleMedium)
                            Text("${project.number} • ${project.status}", style = MaterialTheme.typography.bodySmall)
                            if (project.id == selectedProjectId) {
                                Text("Last selected", style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(top = 3.dp))
                            }
                        }
                    }
                    HorizontalDivider()
                }
            }
        }
        Row(modifier = Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text("Offline project cache active", style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onLogout) { Text("Sign out") }
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
    onOpenPartyDirectory: () -> Unit,
    onOpenWbs: () -> Unit,
    onOpenBoq: () -> Unit,
    onOpenEstimating: () -> Unit,
    onOpenProjectAccess: () -> Unit,
    onOpenAccessManagement: () -> Unit,
    onLogout: () -> Unit,
) {
    var selectedTab by rememberSaveable(project.id) { mutableStateOf(ProjectTab.HOME.name) }
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
    val canViewProjectAccess = "projects.membership.view" in projectPermissions

    Column(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 9.dp)) {
            Text(project.name, style = MaterialTheme.typography.titleLarge)
            Text("${project.number} • ${project.status}", style = MaterialTheme.typography.bodySmall)
        }
        HorizontalDivider()
        when (ProjectTab.valueOf(selectedTab)) {
            ProjectTab.HOME -> ProjectHomeContent(actions, pending, attention, onOpenAttendance, onOpenDailyReport, Modifier.weight(1f))
            ProjectTab.FIELD -> ProjectFieldContent(actions, onOpenAttendance, onOpenDailyReport, Modifier.weight(1f))
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
                modifier = Modifier.weight(1f),
            )
        }
        NavigationBar {
            NavigationBarItem(selected = selectedTab == ProjectTab.HOME.name, onClick = { selectedTab = ProjectTab.HOME.name }, icon = {}, label = { Text("Home") })
            NavigationBarItem(selected = selectedTab == ProjectTab.FIELD.name, onClick = { selectedTab = ProjectTab.FIELD.name }, icon = {}, label = { Text("Field") })
            NavigationBarItem(selected = false, onClick = onChooseProject, icon = {}, label = { Text("Projects") })
            NavigationBarItem(selected = selectedTab == ProjectTab.MORE.name, onClick = { selectedTab = ProjectTab.MORE.name }, icon = {}, label = { Text("More") })
        }
    }
}

@Composable
private fun ProjectHomeContent(
    actions: List<ProjectHomeAction>,
    pending: Int,
    attention: Int,
    onOpenAttendance: () -> Unit,
    onOpenDailyReport: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(modifier = modifier) {
        item {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                Text("Today", style = MaterialTheme.typography.titleLarge)
                Text("Daily work and anything needing attention.", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 2.dp))
            }
            HorizontalDivider()
        }
        if (attention > 0) {
            item {
                Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                    Text("Needs attention", style = MaterialTheme.typography.titleMedium)
                    Text("$attention attendance sync issue${if (attention == 1) "" else "s"} need review.", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 3.dp))
                }
                HorizontalDivider()
            }
        } else if (pending > 0) {
            item {
                Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                    Text("Saved on device", style = MaterialTheme.typography.titleMedium)
                    Text("$pending attendance change${if (pending == 1) "" else "s"} will sync when network is available.", modifier = Modifier.padding(top = 3.dp))
                }
                HorizontalDivider()
            }
        }
        if (actions.isEmpty()) {
            item { Text("No mobile workflows are available for your current project permissions.", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(16.dp)) }
        } else {
            items(actions, key = { it.key.name }) { action ->
                ProjectActionRow(action = action, onClick = actionClick(action, onOpenAttendance, onOpenDailyReport))
            }
        }
    }
}

@Composable
private fun ProjectFieldContent(
    actions: List<ProjectHomeAction>,
    onOpenAttendance: () -> Unit,
    onOpenDailyReport: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(modifier = modifier) {
        item {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                Text("Field", style = MaterialTheme.typography.titleLarge)
                Text("Fast site workflows for this project.", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 2.dp))
            }
            HorizontalDivider()
        }
        items(actions, key = { it.key.name }) { action ->
            ProjectActionRow(action = action, onClick = actionClick(action, onOpenAttendance, onOpenDailyReport))
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
private fun ProjectActionRow(action: ProjectHomeAction, onClick: (() -> Unit)?) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(action.title, style = MaterialTheme.typography.titleMedium)
            Text(
                when (action.mode) {
                    ProjectActionMode.WORK -> "Work"
                    ProjectActionMode.REVIEW -> "Review"
                    ProjectActionMode.VIEW -> "View"
                },
                style = MaterialTheme.typography.labelMedium,
            )
        }
        Text(action.subtitle, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 3.dp))
        if (onClick != null) {
            TextButton(onClick = onClick, modifier = Modifier.padding(top = 2.dp)) { Text("Open") }
        }
    }
    HorizontalDivider()
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
    modifier: Modifier = Modifier,
) {
    LazyColumn(modifier = modifier) {
        item {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                Text("More", style = MaterialTheme.typography.titleLarge)
                Text("Project information and account actions.", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 2.dp))
            }
            HorizontalDivider()
        }
        item {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                Text("Project", style = MaterialTheme.typography.titleMedium)
                Text(project.name, modifier = Modifier.padding(top = 3.dp))
                Text(project.number, style = MaterialTheme.typography.bodySmall)
                project.locality?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
            HorizontalDivider()
        }
        if (canViewPartyDirectory) {
            item {
                MoreLink("Party directory", "Clients, vendors, suppliers and subcontractors with project relationships.", onOpenPartyDirectory)
            }
        }
        if (canViewWbs) {
            item {
                MoreLink("WBS / Cost Codes", "Search the project hierarchy from the local field cache.", onOpenWbs)
            }
        }
        if (canViewBoq) {
            item {
                MoreLink("Approved BOQ", "Search approved field-safe BOQ items from the local cache.", onOpenBoq)
            }
        }
        if (canViewEstimating) {
            item {
                MoreLink("Estimating & Budget", "Review governed estimate and budget status and approve when permitted.", onOpenEstimating)
            }
        }
        if (canViewProjectAccess) {
            item {
                MoreLink("Project access", "Project members and project-scoped roles. Online company-server access only.", onOpenProjectAccess)
            }
        }
        if (canViewAccessManagement) {
            item {
                MoreLink("People & access", "Company roles, permissions and memberships. Online company-server access only.", onOpenAccessManagement)
            }
        }
        item {
            OutlinedButton(onClick = onChooseProject, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp)) { Text("Change project") }
        }
        item {
            TextButton(onClick = onLogout, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) { Text("Sign out") }
        }
    }
}

@Composable
private fun MoreLink(title: String, subtitle: String, onOpen: () -> Unit) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(subtitle, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
        TextButton(onClick = onOpen, modifier = Modifier.padding(top = 2.dp)) { Text("Open") }
    }
    HorizontalDivider()
}

@Composable
private fun MissingProjectScreen(onChooseProject: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Project is no longer available", style = MaterialTheme.typography.titleLarge)
        Text("Your cached access changed. Choose another project.", modifier = Modifier.padding(top = 8.dp, bottom = 16.dp))
        Button(onClick = onChooseProject) { Text("Choose project") }
    }
}

@Composable
private fun MissingPermissionScreen(message: String, onBack: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Access unavailable", style = MaterialTheme.typography.titleLarge)
        Text(message, modifier = Modifier.padding(top = 8.dp, bottom = 16.dp))
        Button(onClick = onBack) { Text("Back") }
    }
}

private fun projectHomeRoute(projectId: String): String = "project-home/$projectId"
private fun attendanceRoute(projectId: String): String = "attendance/$projectId"
private fun dailyReportRoute(projectId: String): String = "daily-report/$projectId"
private fun partyDirectoryRoute(projectId: String): String = "party-directory/$projectId"
private fun wbsRoute(projectId: String): String = "wbs/$projectId"
private fun boqRoute(projectId: String): String = "boq/$projectId"
private fun estimatingRoute(projectId: String): String = "estimating/$projectId"
private fun projectAccessRoute(projectId: String): String = "project-access/$projectId"
