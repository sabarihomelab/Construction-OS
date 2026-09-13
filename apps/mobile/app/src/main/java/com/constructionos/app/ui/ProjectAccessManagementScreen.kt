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
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.authorization.ProjectAccessAdminRepository
import com.constructionos.app.core.authorization.ProjectAccessAdminSnapshot
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.network.ProjectAccessMembershipResponse
import kotlinx.coroutines.launch

@Composable
fun ProjectAccessManagementScreen(
    project: ProjectEntity,
    repository: ProjectAccessAdminRepository,
    canManage: Boolean,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scope = rememberCoroutineScope()
    var snapshot by remember(project.id) { mutableStateOf<ProjectAccessAdminSnapshot?>(null) }
    var selectedMember by remember(project.id) { mutableStateOf<ProjectAccessMembershipResponse?>(null) }
    var roleDraft by remember(project.id) { mutableStateOf<Set<String>>(emptySet()) }
    var loading by remember(project.id) { mutableStateOf(true) }
    var busy by remember(project.id) { mutableStateOf(false) }
    var error by remember(project.id) { mutableStateOf<String?>(null) }
    var message by remember(project.id) { mutableStateOf<String?>(null) }

    suspend fun reload() {
        loading = true
        error = null
        runCatching { repository.snapshot(project.id) }
            .onSuccess { next ->
                snapshot = next
                selectedMember = selectedMember?.let { current ->
                    next.access.firstOrNull { it.id == current.id }
                }
            }
            .onFailure { error = projectAccessError(it) }
        loading = false
    }

    LaunchedEffect(project.id, repository) { reload() }

    if (loading && snapshot == null) {
        Column(
            modifier = modifier.fillMaxSize(),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            CircularProgressIndicator()
            Text("Loading project access…", modifier = Modifier.padding(top = 12.dp))
        }
        return
    }

    val data = snapshot
    if (data == null) {
        ProjectAccessFailure(
            message = error ?: "Unable to load project access.",
            onRetry = { scope.launch { reload() } },
            onBack = onBack,
            modifier = modifier,
        )
        return
    }

    val currentMember = selectedMember
    if (currentMember != null) {
        ProjectMemberRoleEditor(
            member = currentMember,
            snapshot = data,
            roleDraft = roleDraft,
            canManage = canManage,
            busy = busy,
            error = error,
            onRoleChanged = { roleId, checked ->
                roleDraft = roleDraft.toMutableSet().also { values ->
                    if (checked) values.add(roleId) else values.remove(roleId)
                }
            },
            onSave = {
                scope.launch {
                    busy = true
                    error = null
                    runCatching {
                        repository.replaceRoles(
                            projectId = project.id,
                            projectMembershipId = currentMember.id,
                            roleIds = roleDraft,
                        )
                    }.onSuccess { updated ->
                        message = "Project roles updated for ${updated.displayName}."
                        selectedMember = null
                        roleDraft = emptySet()
                        reload()
                    }.onFailure { error = projectAccessError(it) }
                    busy = false
                }
            },
            onStatus = { status ->
                scope.launch {
                    busy = true
                    error = null
                    runCatching {
                        repository.updateStatus(project.id, currentMember.id, status)
                    }.onSuccess {
                        message = "${currentMember.displayName}'s project access is now $status."
                        selectedMember = null
                        roleDraft = emptySet()
                        reload()
                    }.onFailure { error = projectAccessError(it) }
                    busy = false
                }
            },
            onBack = {
                selectedMember = null
                roleDraft = emptySet()
            },
            modifier = modifier,
        )
        return
    }

    val existingCompanyMembershipIds = data.access.map { it.organizationMembershipId }.toSet()
    val availablePeople = data.companyMemberships.filter { membership ->
        membership.status == "active" && membership.id !in existingCompanyMembershipIds
    }

    LazyColumn(modifier = modifier.fillMaxSize()) {
        item {
            ProjectAccessHeader(
                title = "Project access",
                subtitle = "${project.number} · ${project.name}",
                onBack = onBack,
            )
        }
        if (error != null) item { ProjectAccessMessage(error!!, true) }
        if (message != null) item { ProjectAccessMessage(message!!, false) }
        item {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Online authorization", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Project membership and roles are checked by the company server and are not saved in the offline field database.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 4.dp),
                )
                OutlinedButton(
                    onClick = { scope.launch { reload() } },
                    enabled = !busy,
                    modifier = Modifier.padding(top = 10.dp),
                ) {
                    Text("Refresh")
                }
            }
            HorizontalDivider()
        }

        if (canManage) {
            item {
                ProjectAccessSectionTitle(
                    title = "Add company member",
                    subtitle = if (availablePeople.isEmpty()) {
                        "No additional active company members are available"
                    } else {
                        "${availablePeople.size} available"
                    },
                )
            }
            items(availablePeople, key = { "available-${it.id}" }) { membership ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(membership.displayName, style = MaterialTheme.typography.titleSmall)
                        Text(
                            "${membership.primaryEmail} · ${membership.kind}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    TextButton(
                        onClick = {
                            scope.launch {
                                busy = true
                                error = null
                                message = null
                                runCatching {
                                    repository.addMember(
                                        projectId = project.id,
                                        organizationMembershipId = membership.id,
                                        title = null,
                                    )
                                }.onSuccess {
                                    message = "${membership.displayName} added to ${project.name}."
                                    reload()
                                }.onFailure { error = projectAccessError(it) }
                                busy = false
                            }
                        },
                        enabled = !busy,
                    ) {
                        Text("Add")
                    }
                }
                HorizontalDivider()
            }
        }

        item {
            ProjectAccessSectionTitle("Project team", "${data.access.size} members")
        }
        if (data.access.isEmpty()) {
            item {
                Text(
                    "No project memberships yet.",
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        } else {
            items(data.access, key = { "project-member-${it.id}" }) { member ->
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                ) {
                    Text(member.displayName, style = MaterialTheme.typography.titleMedium)
                    Text(member.primaryEmail, style = MaterialTheme.typography.bodySmall)
                    Text(
                        "${member.membershipKind} · ${member.status}${member.title?.let { " · $it" } ?: ""}",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(top = 2.dp),
                    )
                    Text(
                        member.roles.joinToString { it.name }.ifBlank { "No project role" },
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(top = 3.dp),
                    )
                    TextButton(
                        onClick = {
                            selectedMember = member
                            roleDraft = member.roleIds.toSet()
                            error = null
                            message = null
                        },
                        enabled = !busy,
                    ) {
                        Text("Manage")
                    }
                }
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun ProjectMemberRoleEditor(
    member: ProjectAccessMembershipResponse,
    snapshot: ProjectAccessAdminSnapshot,
    roleDraft: Set<String>,
    canManage: Boolean,
    busy: Boolean,
    error: String?,
    onRoleChanged: (String, Boolean) -> Unit,
    onSave: () -> Unit,
    onStatus: (String) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(modifier = modifier.fillMaxSize()) {
        item {
            ProjectAccessHeader(
                title = member.displayName,
                subtitle = "Project roles · ${member.status}",
                onBack = onBack,
            )
        }
        if (error != null) item { ProjectAccessMessage(error, true) }
        if (canManage) {
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (member.status != "active") {
                        Button(onClick = { onStatus("active") }, enabled = !busy) { Text("Activate") }
                    } else {
                        OutlinedButton(
                            onClick = { onStatus("suspended") },
                            enabled = !busy,
                        ) { Text("Suspend") }
                    }
                    if (member.status != "ended") {
                        OutlinedButton(
                            onClick = { onStatus("ended") },
                            enabled = !busy,
                        ) { Text("End") }
                    }
                }
                HorizontalDivider()
            }
        }
        item {
            ProjectAccessSectionTitle(
                title = "Project roles",
                subtitle = "Only project-scoped roles are assignable here",
            )
        }
        items(snapshot.projectRoles, key = { "project-role-${it.id}" }) { role ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Checkbox(
                    checked = role.id in roleDraft,
                    onCheckedChange = { checked -> onRoleChanged(role.id, checked) },
                    enabled = canManage && member.status == "active" && !busy,
                )
                Column(modifier = Modifier.padding(start = 8.dp)) {
                    Text(role.name, style = MaterialTheme.typography.titleSmall)
                    Text(
                        "${role.assignmentScope} · ${if (role.isTemplate) "default" else "custom"}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            HorizontalDivider()
        }
        if (canManage && member.status == "active") {
            item {
                Button(
                    onClick = onSave,
                    enabled = !busy,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                ) {
                    Text("Save project roles")
                }
            }
        }
    }
}

@Composable
private fun ProjectAccessHeader(
    title: String,
    subtitle: String,
    onBack: () -> Unit,
) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
        TextButton(onClick = onBack) { Text("Back") }
        Text(title, style = MaterialTheme.typography.headlineSmall)
        Text(subtitle, style = MaterialTheme.typography.bodyMedium)
    }
    HorizontalDivider()
}

@Composable
private fun ProjectAccessSectionTitle(title: String, subtitle: String) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(subtitle, style = MaterialTheme.typography.bodySmall)
    }
    HorizontalDivider()
}

@Composable
private fun ProjectAccessMessage(message: String, isError: Boolean) {
    Text(
        text = message,
        color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(16.dp),
        style = MaterialTheme.typography.bodyMedium,
    )
    HorizontalDivider()
}

@Composable
private fun ProjectAccessFailure(
    message: String,
    onRetry: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message, color = MaterialTheme.colorScheme.error)
        Button(onClick = onRetry, modifier = Modifier.padding(top = 16.dp)) { Text("Retry") }
        TextButton(onClick = onBack) { Text("Back") }
    }
}

private fun projectAccessError(error: Throwable): String =
    error.message?.takeIf { it.isNotBlank() } ?: "The project access request failed."
