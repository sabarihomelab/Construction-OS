package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Business
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
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

    LaunchedEffect(organizationId, project.id) { refresh() }

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

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Rounded.ArrowBack, contentDescription = "Back")
            }
            Column(modifier = Modifier.weight(1f)) {
                Text("Party directory", style = MaterialTheme.typography.headlineSmall)
                Text(
                    project.name,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (refreshing) {
                CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                IconButton(onClick = ::refresh) {
                    Icon(Icons.Rounded.Refresh, contentDescription = "Refresh")
                }
            }
        }

        OutlinedTextField(
            value = search,
            onValueChange = { search = it },
            placeholder = { Text("Search company, code or role") },
            leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
            singleLine = true,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 10.dp),
        )

        refreshError?.let { message ->
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) {
                Text(message, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(10.dp))
            }
        }

        if (visibleParties.isEmpty() && !refreshing) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 30.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(
                    Icons.Rounded.Business,
                    contentDescription = null,
                    modifier = Modifier.size(38.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    if (search.isBlank()) "No parties available" else "No matching parties",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 10.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .padding(top = 10.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(visibleParties, key = PartyEntity::id) { party ->
                    PartyDirectoryCard(
                        party = party,
                        projectRoles = rolesByParty[party.id].orEmpty(),
                    )
                }
            }
        }
    }
}

@Composable
private fun PartyDirectoryCard(
    party: PartyEntity,
    projectRoles: List<String>,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(15.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        party.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "${party.code} • ${party.partyType.toDisplayLabel()}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 2.dp),
                    )
                }
                CosStatusPill(
                    party.status.toDisplayLabel(),
                    tone = if (party.status.lowercase() == "active") CosStatusTone.SUCCESS else CosStatusTone.NEUTRAL,
                )
            }

            party.legalName?.takeIf { it.isNotBlank() && it != party.name }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 5.dp),
                )
            }

            Row(
                modifier = Modifier.padding(top = 9.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                if (projectRoles.isEmpty()) {
                    CosStatusPill("Company directory")
                } else {
                    projectRoles.take(3).forEach { role ->
                        CosStatusPill(role.toDisplayLabel(), tone = CosStatusTone.PRIMARY)
                    }
                }
            }

            val contacts = listOfNotNull(
                party.phone?.takeIf(String::isNotBlank),
                party.email?.takeIf(String::isNotBlank),
            )
            if (contacts.isNotEmpty()) {
                Text(
                    contacts.joinToString(" • "),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 9.dp),
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
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
}

private fun String.toDisplayLabel(): String =
    lowercase().split('_').joinToString(" ") { token -> token.replaceFirstChar { it.uppercase() } }
