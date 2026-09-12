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
import androidx.compose.material3.OutlinedTextField
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
import com.constructionos.app.core.authorization.AccessAdminRepository
import com.constructionos.app.core.authorization.AccessAdminSnapshot
import com.constructionos.app.core.network.SecurityMembershipResponse
import com.constructionos.app.core.network.SecurityPartyReferenceResponse
import com.constructionos.app.core.network.SecurityPermissionResponse
import com.constructionos.app.core.network.SecurityRoleResponse
import com.constructionos.app.core.network.SecurityRoleTemplateResponse
import kotlinx.coroutines.launch

private enum class AccessAdminView {
    OVERVIEW,
    ROLE,
    MEMBER,
    ADD_PERSON,
    CREATE_ROLE,
}

@Composable
fun AccessManagementScreen(
    repository: AccessAdminRepository,
    canManage: Boolean,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scope = rememberCoroutineScope()
    var snapshot by remember { mutableStateOf<AccessAdminSnapshot?>(null) }
    var view by remember { mutableStateOf(AccessAdminView.OVERVIEW) }
    var selectedRole by remember { mutableStateOf<SecurityRoleResponse?>(null) }
    var selectedMembership by remember { mutableStateOf<SecurityMembershipResponse?>(null) }
    var selectedPermissions by remember { mutableStateOf<Set<String>>(emptySet()) }
    var selectedPermissionVersion by remember { mutableStateOf<Int?>(null) }
    var selectedMemberRoles by remember { mutableStateOf<Set<String>>(emptySet()) }
    var selectedPartyId by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }

    suspend fun reload() {
        loading = true
        error = null
        runCatching { repository.snapshot() }
            .onSuccess { next ->
                snapshot = next
                selectedRole = selectedRole?.let { current -> next.roles.firstOrNull { it.id == current.id } }
                selectedMembership = selectedMembership?.let { current -> next.memberships.firstOrNull { it.id == current.id } }
            }
            .onFailure { error = accessAdminError(it) }
        loading = false
    }

    LaunchedEffect(repository) { reload() }

    when {
        loading && snapshot == null -> AccessAdminLoading(modifier)
        snapshot == null -> AccessAdminFailure(
            message = error ?: "Unable to load company access.",
            onRetry = { scope.launch { reload() } },
            onBack = onBack,
            modifier = modifier,
        )
        else -> {
            val data = snapshot!!
            val companyRoles = data.roles.filter { role ->
                role.isActive && role.assignmentScope in setOf("company", "both")
            }
            when (view) {
                AccessAdminView.OVERVIEW -> AccessOverview(
                    snapshot = data,
                    canManage = canManage,
                    busy = busy,
                    error = error,
                    message = message,
                    onBack = onBack,
                    onRefresh = { scope.launch { reload() } },
                    onInstallDefaults = {
                        scope.launch {
                            busy = true
                            error = null
                            message = null
                            runCatching { repository.installDefaults() }
                                .onSuccess { installed ->
                                    message = if (installed.isEmpty()) {
                                        "All recommended India roles are already installed."
                                    } else {
                                        "Installed ${installed.size} recommended role${if (installed.size == 1) "" else "s"}."
                                    }
                                    reload()
                                }
                                .onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onCreateRole = {
                        error = null
                        message = null
                        view = AccessAdminView.CREATE_ROLE
                    },
                    onAddPerson = {
                        error = null
                        message = null
                        view = AccessAdminView.ADD_PERSON
                    },
                    onOpenRole = { role ->
                        scope.launch {
                            selectedRole = role
                            busy = true
                            error = null
                            message = null
                            runCatching { repository.rolePermissions(role.id) }
                                .onSuccess { permissionSet ->
                                    selectedPermissions = permissionSet.permissionKeys.toSet()
                                    selectedPermissionVersion = permissionSet.expectedVersion
                                    view = AccessAdminView.ROLE
                                }
                                .onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onOpenMember = { member ->
                        selectedMembership = member
                        selectedMemberRoles = member.roleIds.toSet()
                        selectedPartyId = member.representedPartyId
                        error = null
                        message = null
                        view = AccessAdminView.MEMBER
                    },
                    modifier = modifier,
                )

                AccessAdminView.ROLE -> RolePermissionEditor(
                    role = selectedRole,
                    permissions = data.permissions,
                    selectedPermissions = selectedPermissions,
                    canManage = canManage,
                    busy = busy,
                    error = error,
                    onPermissionChanged = { key, checked ->
                        selectedPermissions = selectedPermissions.toMutableSet().also { values ->
                            if (checked) values.add(key) else values.remove(key)
                        }
                    },
                    onSave = {
                        val role = selectedRole ?: return@RolePermissionEditor
                        scope.launch {
                            busy = true
                            error = null
                            runCatching {
                                repository.replaceRolePermissions(
                                    roleId = role.id,
                                    expectedVersion = selectedPermissionVersion,
                                    permissionKeys = selectedPermissions,
                                )
                            }.onSuccess { updated ->
                                val permissionSet = repository.rolePermissions(updated.id)
                                selectedRole = updated
                                selectedPermissions = permissionSet.permissionKeys.toSet()
                                selectedPermissionVersion = permissionSet.expectedVersion
                                message = "Permissions saved for ${updated.name}."
                                reload()
                            }.onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onBack = {
                        selectedRole = null
                        selectedPermissions = emptySet()
                        selectedPermissionVersion = null
                        view = AccessAdminView.OVERVIEW
                    },
                    modifier = modifier,
                )

                AccessAdminView.MEMBER -> MembershipRoleEditor(
                    membership = selectedMembership,
                    roles = companyRoles,
                    parties = data.partyReferences,
                    selectedRoleIds = selectedMemberRoles,
                    selectedPartyId = selectedPartyId,
                    canManage = canManage,
                    busy = busy,
                    error = error,
                    onRoleChanged = { roleId, checked ->
                        selectedMemberRoles = selectedMemberRoles.toMutableSet().also { values ->
                            if (checked) values.add(roleId) else values.remove(roleId)
                        }
                    },
                    onPartyChanged = { selectedPartyId = it },
                    onSaveRoles = {
                        val membership = selectedMembership ?: return@MembershipRoleEditor
                        scope.launch {
                            busy = true
                            error = null
                            runCatching {
                                repository.replaceMembershipRoles(
                                    membershipId = membership.id,
                                    roleIds = selectedMemberRoles,
                                )
                            }.onSuccess { updated ->
                                selectedMembership = updated
                                selectedMemberRoles = updated.roleIds.toSet()
                                message = "Roles updated for ${updated.displayName}."
                                reload()
                            }.onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onSaveParty = {
                        val membership = selectedMembership ?: return@MembershipRoleEditor
                        scope.launch {
                            busy = true
                            error = null
                            runCatching {
                                repository.updateMembershipParty(membership.id, selectedPartyId)
                            }.onSuccess { updated ->
                                selectedMembership = updated
                                selectedPartyId = updated.representedPartyId
                                message = updated.representedPartyName?.let { party ->
                                    "${updated.displayName} now represents $party."
                                } ?: "Represented party cleared for ${updated.displayName}."
                                reload()
                            }.onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onStatus = { status ->
                        val membership = selectedMembership ?: return@MembershipRoleEditor
                        scope.launch {
                            busy = true
                            error = null
                            runCatching {
                                repository.updateMembershipStatus(membership.id, status)
                            }.onSuccess { updated ->
                                selectedMembership = updated
                                message = "${updated.displayName} is now ${updated.status}."
                                reload()
                            }.onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onBack = {
                        selectedMembership = null
                        selectedMemberRoles = emptySet()
                        selectedPartyId = null
                        view = AccessAdminView.OVERVIEW
                    },
                    modifier = modifier,
                )

                AccessAdminView.ADD_PERSON -> AddPersonForm(
                    roles = companyRoles,
                    parties = data.partyReferences,
                    busy = busy,
                    error = error,
                    onSave = { email, name, kind, roleId, partyId ->
                        scope.launch {
                            busy = true
                            error = null
                            runCatching {
                                repository.addPerson(
                                    email = email.trim(),
                                    displayName = name.trim(),
                                    kind = kind,
                                    status = "invited",
                                    roleIds = roleId?.let(::setOf) ?: emptySet(),
                                    representedPartyId = if (kind == "external") partyId else null,
                                )
                            }.onSuccess {
                                message = "${it.displayName} was added as an invited company member."
                                reload()
                                view = AccessAdminView.OVERVIEW
                            }.onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onBack = { view = AccessAdminView.OVERVIEW },
                    modifier = modifier,
                )

                AccessAdminView.CREATE_ROLE -> CreateRoleForm(
                    templates = data.templates,
                    busy = busy,
                    error = error,
                    onSave = { name, key, templateKey ->
                        scope.launch {
                            busy = true
                            error = null
                            runCatching {
                                if (templateKey == null) {
                                    repository.createBlankRole(
                                        key = normalizeRoleKey(key.ifBlank { name }),
                                        name = name.trim(),
                                        description = null,
                                    )
                                } else {
                                    repository.createFromTemplate(
                                        templateKey = templateKey,
                                        key = normalizeRoleKey(key.ifBlank { name }),
                                        name = name.trim(),
                                    )
                                }
                            }.onSuccess {
                                message = "Role ${it.name} created."
                                reload()
                                view = AccessAdminView.OVERVIEW
                            }.onFailure { error = accessAdminError(it) }
                            busy = false
                        }
                    },
                    onBack = { view = AccessAdminView.OVERVIEW },
                    modifier = modifier,
                )
            }
        }
    }
}

@Composable
private fun AccessOverview(
    snapshot: AccessAdminSnapshot,
    canManage: Boolean,
    busy: Boolean,
    error: String?,
    message: String?,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onInstallDefaults: () -> Unit,
    onCreateRole: () -> Unit,
    onAddPerson: () -> Unit,
    onOpenRole: (SecurityRoleResponse) -> Unit,
    onOpenMember: (SecurityMembershipResponse) -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(modifier = modifier.fillMaxSize()) {
        item { AccessAdminHeader("People & access", "Server-authoritative company roles, permissions and memberships.", onBack) }
        if (error != null) item { AccessAdminMessage(error, true) }
        if (message != null) item { AccessAdminMessage(message, false) }
        item {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Online security administration", style = MaterialTheme.typography.titleMedium)
                Text(
                    "This data is not stored in the offline site database. Changes are checked by the company server.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 4.dp),
                )
                Row(modifier = Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = onRefresh, enabled = !busy) { Text("Refresh") }
                    if (canManage) Button(onClick = onInstallDefaults, enabled = !busy) { Text("Install defaults") }
                }
            }
            HorizontalDivider()
        }
        item { AccessSectionTitle("Recommended India roles", "${snapshot.templates.size} templates available") }
        items(snapshot.templates, key = { "template-${it.key}" }) { TemplateRow(it) }
        item {
            AccessSectionTitle("Roles", "${snapshot.roles.size} installed")
            if (canManage) TextButton(onClick = onCreateRole, enabled = !busy) { Text("Create custom role") }
        }
        items(snapshot.roles, key = { "role-${it.id}" }) { role ->
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp)) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(role.name, style = MaterialTheme.typography.titleMedium)
                        Text(
                            "${role.key} · ${role.assignmentScope} · ${if (role.isProtected) "protected" else if (role.isTemplate) "default" else "custom"}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    TextButton(onClick = { onOpenRole(role) }, enabled = !busy) { Text("Permissions") }
                }
            }
            HorizontalDivider()
        }
        item {
            AccessSectionTitle("Company people", "${snapshot.memberships.size} memberships")
            if (canManage) TextButton(onClick = onAddPerson, enabled = !busy) { Text("Add person") }
        }
        items(snapshot.memberships, key = { "member-${it.id}" }) { member ->
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp)) {
                Text(member.displayName, style = MaterialTheme.typography.titleMedium)
                Text(member.primaryEmail, style = MaterialTheme.typography.bodySmall)
                Text(
                    "${member.kind} · ${member.status} · ${member.roles.joinToString { role -> role.name }.ifBlank { "no company role" }}",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 3.dp),
                )
                member.representedPartyName?.let { party ->
                    Text("Represents: $party", style = MaterialTheme.typography.bodySmall)
                }
                TextButton(onClick = { onOpenMember(member) }, enabled = !busy) { Text("Manage") }
            }
            HorizontalDivider()
        }
    }
}

@Composable
private fun RolePermissionEditor(
    role: SecurityRoleResponse?,
    permissions: List<SecurityPermissionResponse>,
    selectedPermissions: Set<String>,
    canManage: Boolean,
    busy: Boolean,
    error: String?,
    onPermissionChanged: (String, Boolean) -> Unit,
    onSave: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (role == null) {
        AccessAdminFailure("Role is no longer available.", {}, onBack, modifier)
        return
    }
    val grouped = permissions.groupBy { it.module }.toSortedMap()
    LazyColumn(modifier = modifier.fillMaxSize()) {
        item {
            AccessAdminHeader(
                role.name,
                if (role.isProtected) "Protected administrator role. Permissions are read-only." else "${role.assignmentScope} · ${selectedPermissions.size} permissions selected.",
                onBack,
            )
        }
        if (error != null) item { AccessAdminMessage(error, true) }
        grouped.forEach { (module, modulePermissions) ->
            item { AccessSectionTitle(module.replace('_', ' ').uppercase(), "${modulePermissions.count { it.key in selectedPermissions }}/${modulePermissions.size} enabled") }
            items(modulePermissions, key = { "permission-${it.key}" }) { permission ->
                Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.Top) {
                    Checkbox(
                        checked = permission.key in selectedPermissions,
                        onCheckedChange = { checked -> onPermissionChanged(permission.key, checked) },
                        enabled = canManage && !role.isProtected && !busy,
                    )
                    Column(modifier = Modifier.weight(1f).padding(start = 8.dp)) {
                        Text("${permission.resource.replace('_', ' ')} · ${permission.action.replace('_', ' ')}", style = MaterialTheme.typography.titleSmall)
                        Text(permission.description, style = MaterialTheme.typography.bodySmall)
                        Text("Risk: ${permission.risk}", style = MaterialTheme.typography.labelSmall)
                    }
                }
                HorizontalDivider()
            }
        }
        if (canManage && !role.isProtected) {
            item {
                Button(onClick = onSave, enabled = !busy, modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                    Text(if (busy) "Saving…" else "Save permissions")
                }
            }
        }
    }
}

@Composable
private fun MembershipRoleEditor(
    membership: SecurityMembershipResponse?,
    roles: List<SecurityRoleResponse>,
    parties: List<SecurityPartyReferenceResponse>,
    selectedRoleIds: Set<String>,
    selectedPartyId: String?,
    canManage: Boolean,
    busy: Boolean,
    error: String?,
    onRoleChanged: (String, Boolean) -> Unit,
    onPartyChanged: (String?) -> Unit,
    onSaveRoles: () -> Unit,
    onSaveParty: () -> Unit,
    onStatus: (String) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (membership == null) {
        AccessAdminFailure("Membership is no longer available.", {}, onBack, modifier)
        return
    }
    LazyColumn(modifier = modifier.fillMaxSize()) {
        item { AccessAdminHeader(membership.displayName, "${membership.kind} · ${membership.status} · ${membership.primaryEmail}", onBack) }
        if (error != null) item { AccessAdminMessage(error, true) }
        if (membership.kind == "external") {
            item {
                AccessSectionTitle("Represented party", "Required before an external membership can be active.")
                Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    OutlinedButton(onClick = { onPartyChanged(null) }, enabled = canManage && !busy) {
                        Text(if (selectedPartyId == null) "✓ No represented party" else "No represented party")
                    }
                    parties.forEach { party ->
                        TextButton(onClick = { onPartyChanged(party.id) }, enabled = canManage && !busy) {
                            Text(if (selectedPartyId == party.id) "✓ ${party.name}" else "${party.name} · ${party.partyType}")
                        }
                    }
                    if (canManage) {
                        Button(onClick = onSaveParty, enabled = !busy, modifier = Modifier.padding(top = 8.dp)) {
                            Text("Save represented party")
                        }
                    }
                }
                HorizontalDivider()
            }
        }
        if (canManage) {
            item {
                AccessSectionTitle("Membership status", "Activation is enforced by the company server.")
                Row(modifier = Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (membership.status != "active") Button(onClick = { onStatus("active") }, enabled = !busy) { Text("Activate") }
                    if (membership.status == "active") OutlinedButton(onClick = { onStatus("suspended") }, enabled = !busy) { Text("Suspend") }
                    if (membership.status != "ended") OutlinedButton(onClick = { onStatus("ended") }, enabled = !busy) { Text("End") }
                }
                HorizontalDivider()
            }
        }
        item { AccessSectionTitle("Company roles", "Project roles are assigned separately from each project team.") }
        items(roles, key = { "member-role-${it.id}" }) { role ->
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Checkbox(
                    checked = role.id in selectedRoleIds,
                    onCheckedChange = { checked -> onRoleChanged(role.id, checked) },
                    enabled = canManage && !busy,
                )
                Column(modifier = Modifier.padding(start = 8.dp)) {
                    Text(role.name, style = MaterialTheme.typography.titleSmall)
                    Text("${role.assignmentScope} · ${if (role.isProtected) "protected" else if (role.isTemplate) "default" else "custom"}", style = MaterialTheme.typography.bodySmall)
                }
            }
            HorizontalDivider()
        }
        if (canManage) {
            item {
                Button(onClick = onSaveRoles, enabled = !busy, modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                    Text(if (busy) "Saving…" else "Save company roles")
                }
            }
        }
    }
}

@Composable
private fun AddPersonForm(
    roles: List<SecurityRoleResponse>,
    parties: List<SecurityPartyReferenceResponse>,
    busy: Boolean,
    error: String?,
    onSave: (String, String, String, String?, String?) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var email by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("internal") }
    var roleId by remember { mutableStateOf<String?>(null) }
    var partyId by remember { mutableStateOf<String?>(null) }
    LazyColumn(modifier = modifier.fillMaxSize()) {
        item { AccessAdminHeader("Add company person", "Workers and crews do not need app membership by default.", onBack) }
        if (error != null) item { AccessAdminMessage(error, true) }
        item {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Display name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = email, onValueChange = { email = it }, label = { Text("Email") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Text("Membership type", style = MaterialTheme.typography.titleSmall)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { kind = "internal"; partyId = null }, enabled = !busy) { Text(if (kind == "internal") "✓ Internal" else "Internal") }
                    OutlinedButton(onClick = { kind = "external" }, enabled = !busy) { Text(if (kind == "external") "✓ External" else "External") }
                }
                if (kind == "external") {
                    Text("Represented party", style = MaterialTheme.typography.titleSmall)
                    Text("Can be set now or before activation.", style = MaterialTheme.typography.bodySmall)
                    OutlinedButton(onClick = { partyId = null }, enabled = !busy) { Text(if (partyId == null) "✓ Set later" else "Set later") }
                    parties.forEach { party ->
                        TextButton(onClick = { partyId = party.id }, enabled = !busy) {
                            Text(if (partyId == party.id) "✓ ${party.name}" else "${party.name} · ${party.partyType}")
                        }
                    }
                }
                Text("Initial company role", style = MaterialTheme.typography.titleSmall)
                OutlinedButton(onClick = { roleId = null }, enabled = !busy) { Text(if (roleId == null) "✓ No company role" else "No company role") }
                roles.forEach { role ->
                    TextButton(onClick = { roleId = role.id }, enabled = !busy) { Text(if (roleId == role.id) "✓ ${role.name}" else role.name) }
                }
                Button(
                    onClick = { onSave(email, name, kind, roleId, partyId) },
                    enabled = !busy && email.isNotBlank() && name.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) "Adding…" else "Add as invited member") }
            }
        }
    }
}

@Composable
private fun CreateRoleForm(
    templates: List<SecurityRoleTemplateResponse>,
    busy: Boolean,
    error: String?,
    onSave: (String, String, String?) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var name by remember { mutableStateOf("") }
    var key by remember { mutableStateOf("") }
    var templateKey by remember { mutableStateOf<String?>(null) }
    LazyColumn(modifier = modifier.fillMaxSize()) {
        item { AccessAdminHeader("Create role", "Start blank or copy an India role template.", onBack) }
        if (error != null) item { AccessAdminMessage(error, true) }
        item {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Role name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = key, onValueChange = { key = it }, label = { Text("Role key (optional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Text("Starting point", style = MaterialTheme.typography.titleSmall)
                OutlinedButton(onClick = { templateKey = null }, enabled = !busy) { Text(if (templateKey == null) "✓ Blank role" else "Blank role") }
                templates.forEach { template ->
                    TextButton(onClick = { templateKey = template.key }, enabled = !busy) { Text(if (templateKey == template.key) "✓ ${template.name}" else template.name) }
                }
                Button(onClick = { onSave(name, key, templateKey) }, enabled = !busy && name.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                    Text(if (busy) "Creating…" else "Create role")
                }
            }
        }
    }
}

@Composable
private fun AccessAdminHeader(title: String, subtitle: String, onBack: () -> Unit) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
        TextButton(onClick = onBack) { Text("Back") }
        Text(title, style = MaterialTheme.typography.headlineSmall)
        Text(subtitle, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 4.dp))
    }
    HorizontalDivider()
}

@Composable
private fun AccessSectionTitle(title: String, detail: String) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge)
        Text(detail, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
    }
    HorizontalDivider()
}

@Composable
private fun TemplateRow(template: SecurityRoleTemplateResponse) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        Text(template.name, style = MaterialTheme.typography.titleSmall)
        Text("${template.membershipKindHint} · ${template.scopeHint.replace('_', ' ')} · ${template.permissionKeys.size} permissions", style = MaterialTheme.typography.bodySmall)
    }
    HorizontalDivider()
}

@Composable
private fun AccessAdminMessage(message: String, isError: Boolean) {
    Text(message, color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary, modifier = Modifier.padding(16.dp))
    HorizontalDivider()
}

@Composable
private fun AccessAdminLoading(modifier: Modifier = Modifier) {
    Column(modifier = modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        CircularProgressIndicator()
        Text("Loading company access…", modifier = Modifier.padding(top = 16.dp))
    }
}

@Composable
private fun AccessAdminFailure(message: String, onRetry: () -> Unit, onBack: () -> Unit, modifier: Modifier = Modifier) {
    Column(modifier = modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(message, color = MaterialTheme.colorScheme.error)
        Button(onClick = onRetry, modifier = Modifier.padding(top = 16.dp)) { Text("Retry") }
        TextButton(onClick = onBack) { Text("Back") }
    }
}

private fun normalizeRoleKey(value: String): String = value
    .trim()
    .lowercase()
    .replace(Regex("[^a-z0-9_]+"), "-")
    .trim('-')
    .replace(Regex("-+"), "-")

private fun accessAdminError(error: Throwable): String =
    error.message?.takeIf { it.isNotBlank() }
        ?: "The company server could not complete this access-management request."
