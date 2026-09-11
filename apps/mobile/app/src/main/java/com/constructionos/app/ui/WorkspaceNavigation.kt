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
import androidx.compose.material3.Card
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.constructionos.app.core.authorization.projectHomeActions
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.workspace.WorkspaceCoordinator

private const val PROJECT_SELECTOR_ROUTE = "project-selector"
private const val PROJECT_HOME_ROUTE = "project-home/{projectId}"

@Composable
fun WorkspaceNavigation(
    context: SessionContextResponse,
    workspace: WorkspaceCoordinator,
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

    LaunchedEffect(
        context.organizationId,
        context.authorizationRevision,
        context.configurationRevision,
    ) {
        workspace.onAuthenticated(context)
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
                ProjectHomeScreen(
                    project = project,
                    context = context,
                    onChangeProject = {
                        restoreSavedSelection = false
                        navController.navigate(PROJECT_SELECTOR_ROUTE)
                    },
                    onLogout = onLogout,
                )
            }
        }
    }
}

@Composable
private fun ProjectSelectorScreen(
    projects: List<ProjectEntity>,
    selectedProjectId: String?,
    onSelectProject: (ProjectEntity) -> Unit,
    onLogout: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
    ) {
        Text("Construction OS", style = MaterialTheme.typography.headlineMedium)
        Text(
            text = "Choose project",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(top = 8.dp),
        )
        Text(
            text = "Only projects authorized by the server are shown here.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 4.dp, bottom = 16.dp),
        )

        if (projects.isEmpty()) {
            Text(
                text = "No cached projects yet. The app will refresh automatically when online.",
                modifier = Modifier.padding(top = 16.dp),
            )
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(projects, key = { it.id }) { project ->
                    OutlinedButton(
                        onClick = { onSelectProject(project) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalAlignment = Alignment.Start,
                        ) {
                            Text(project.name, style = MaterialTheme.typography.titleMedium)
                            Text("${project.number} • ${project.status}")
                            if (project.id == selectedProjectId) {
                                Text(
                                    "Last selected",
                                    style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier.padding(top = 4.dp),
                                )
                            }
                        }
                    }
                }
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Offline project cache active", style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onLogout) { Text("Sign out") }
        }
    }
}

@Composable
private fun ProjectHomeScreen(
    project: ProjectEntity,
    context: SessionContextResponse,
    onChangeProject: () -> Unit,
    onLogout: () -> Unit,
) {
    val actions = remember(context, project.id) { context.projectHomeActions(project.id) }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("Construction OS", style = MaterialTheme.typography.labelLarge)
            Text(project.name, style = MaterialTheme.typography.headlineMedium)
            Text(
                "${project.number} • ${project.status}",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 4.dp),
            )
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Project home", style = MaterialTheme.typography.titleLarge)
                TextButton(onClick = onChangeProject) { Text("Change project") }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Ready for field work", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Project data is cached locally and refreshes in the background when online.",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }
        }

        item {
            Text("Available workflows", style = MaterialTheme.typography.titleMedium)
        }

        if (actions.isEmpty()) {
            item {
                Text(
                    "No mobile field workflows are available for your current project access.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        } else {
            items(actions, key = { it.key.name }) { action ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(action.title, style = MaterialTheme.typography.titleMedium)
                        Text(
                            action.subtitle,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                        Text(
                            "Available for this project",
                            style = MaterialTheme.typography.labelSmall,
                            modifier = Modifier.padding(top = 10.dp),
                        )
                    }
                }
            }
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Background sync enabled", style = MaterialTheme.typography.bodySmall)
                TextButton(onClick = onLogout) { Text("Sign out") }
            }
        }
    }
}

@Composable
private fun MissingProjectScreen(onChooseProject: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Project is no longer available", style = MaterialTheme.typography.titleLarge)
        Text(
            "Your cached access changed. Choose another project.",
            modifier = Modifier.padding(top = 8.dp, bottom = 16.dp),
        )
        Button(onClick = onChooseProject) { Text("Choose project") }
    }
}

private fun projectHomeRoute(projectId: String): String = "project-home/$projectId"
