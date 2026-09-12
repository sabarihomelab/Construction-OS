package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.PartyEntity
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.database.ProjectPartyAssignmentEntity
import com.constructionos.app.core.parties.PartyRepository
import kotlinx.coroutines.launch

@Composable
fun PartyDirectoryScreen(
    organizationId: String,
    project: ProjectEntity,
    repository: PartyRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val partiesFlow = remember(organizationId) { repository.observeParties(organizationId) }
    val assignmentsFlow = remember(project.id) { repository.observeAssignments(project.id) }
    val parties by partiesFlow.collectAsState(initial = emptyList())
    val assignments by assignmentsFlow.collectAsState(initial = emptyList())
    var search by rememberSaveable(project.id) { mutableStateOf("") }
    var refreshError by remember(project.id) { mutableStateOf<String?>(null) }
    var refreshing by remember(project.id) { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            refreshing = true
            refreshError = null
            runCatching { repository.refresh(organizationId, project.id) }
                .onFailure {
                    refreshError = if (parties.isEmpty()) {
                        "Directory could not be loaded. Check the connection and try again."
                    } else {
                        "Showing saved directory. Latest server data could not be refreshed."
                    }
                }
            refreshing = false
        }
    }

    LaunchedEffect(organizationId, project.id) {
        refreshing = true
        refreshError = null
        runCatching { repository.refresh(organizationId, project.id) }
            .onFailure {
                refreshError = if (parties.isEmpty()) {
                    "Directory could not be loaded. Check the connection and try again."
                } else {
                    "Showing saved directory. Latest server data could not be refreshed."
                }
            }
        refreshing = false
    }

    val rolesByParty = remember(assignments) {
        assignments.groupBy(ProjectPartyAssignmentEntity::partyId)
            .mapValues { (_, rows) -> rows.map { it.role }.distinct() }
    }
    val query = search.trim().lowercase()
    val visibleParties = remember(parties, rolesByParty, query) {
        parties.filter { party ->
            if (query.isEmpty()) return@filter true
            val roles = rolesByParty[party.id].orEmpty().joinToString(" ")
            listOf(
                party.name,
                party.code,
                party.legalName.orEmpty(),
                party.partyType,
                party.locality.orEmpty(),
                roles,
            ).any { it.lowercase().contains(query) }
        }
    }

    Column(modifier = modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Column(modifier = Modifier.weight(1f)) {
                Text("Party directory", style = MaterialTheme.typography.titleLarge)
                Text(project.name, style = MaterialTheme.typography.bodySmall)
            }
            if (refreshing) {
                CircularProgressIndicator(modifier = Modifier.padding(8.dp))
            }
        }
        HorizontalDivider()

        OutlinedTextField(
            value = search,
            onValueChange = { search = it },
            label = { Text("Search company, code or role") },
            singleLine = true,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
        )

        refreshError?.let { message ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    message,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.weight(1f),
                )
                OutlinedButton(onClick = ::refresh, enabled = !refreshing) {
                    Text("Retry")
                }
            }
        }

        if (visibleParties.isEmpty() && !refreshing) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(if (search.isBlank()) "No parties available" else "No matching parties")
            }
            return
        }

        LazyColumn(modifier = Modifier.weight(1f)) {
            items(visibleParties, key = PartyEntity::id) { party ->
                PartyDirectoryRow(
                    party = party,
                    projectRoles = rolesByParty[party.id].orEmpty(),
                )
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun PartyDirectoryRow(
    party: PartyEntity,
    projectRoles: List<String>,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 14.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                party.name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
            Text(
                party.status.toDisplayLabel(),
                style = MaterialTheme.typography.labelMedium,
            )
        }
        Text(
            "${party.code} • ${party.partyType.toDisplayLabel()}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 2.dp),
        )
        party.legalName?.takeIf { it.isNotBlank() && it != party.name }?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 2.dp))
        }

        Text(
            if (projectRoles.isEmpty()) {
                "Company directory"
            } else {
                "Project role: ${projectRoles.joinToString { it.toDisplayLabel() }}"
            },
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(top = 8.dp),
        )

        val contacts = listOfNotNull(
            party.phone?.takeIf(String::isNotBlank),
            party.email?.takeIf(String::isNotBlank),
        )
        if (contacts.isNotEmpty()) {
            Text(
                contacts.joinToString(" • "),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 6.dp),
            )
        }

        val address = listOfNotNull(
            party.addressLine1?.takeIf(String::isNotBlank),
            party.addressLine2?.takeIf(String::isNotBlank),
            party.locality?.takeIf(String::isNotBlank),
            party.stateName?.takeIf(String::isNotBlank),
            party.postalCode?.takeIf(String::isNotBlank),
        ).joinToString(", ")
        if (address.isNotBlank()) {
            Text(
                address,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}

private fun String.toDisplayLabel(): String =
    lowercase().split('_').joinToString(" ") { token -> token.replaceFirstChar { it.uppercase() } }
