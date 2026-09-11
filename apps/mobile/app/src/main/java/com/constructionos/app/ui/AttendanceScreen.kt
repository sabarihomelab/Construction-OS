package com.constructionos.app.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.attendance.AttendanceRepository
import com.constructionos.app.core.authorization.hasProjectPermission
import com.constructionos.app.core.database.AttendanceEntryEntity
import com.constructionos.app.core.database.AttendanceRegisterEntity
import com.constructionos.app.core.database.AttendanceSyncState
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.network.SessionContextResponse
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.launch

private enum class AttendanceTab(val label: String, val markStatus: String?) {
    PRESENT("Present", AttendanceRepository.MARK_PRESENT),
    ABSENT("Absent", AttendanceRepository.MARK_ABSENT),
    HALF_DAY("Half day", AttendanceRepository.MARK_HALF_DAY),
    MORE("More", null),
}

private enum class AttendanceMoreStatus(val label: String, val markStatus: String) {
    LEAVE("Leave", AttendanceRepository.MARK_LEAVE),
    WEEKLY_OFF("Weekly off", AttendanceRepository.MARK_WEEKLY_OFF),
}

@Composable
fun AttendanceScreen(
    project: ProjectEntity,
    context: SessionContextResponse,
    repository: AttendanceRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val today = remember(project.id, project.timezone) { todayFor(project) }
    var selectedDate by rememberSaveable(project.id) { mutableStateOf(today.toString()) }
    var selectedTab by rememberSaveable(project.id) { mutableStateOf(AttendanceTab.PRESENT.name) }
    var selectedMoreStatus by rememberSaveable(project.id) {
        mutableStateOf(AttendanceMoreStatus.LEAVE.name)
    }
    var search by rememberSaveable(project.id) { mutableStateOf("") }
    var message by remember(project.id) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    val registersFlow = remember(project.id, selectedDate) {
        repository.observeRegisters(project.id, selectedDate)
    }
    val rosterFlow = remember(project.id, selectedDate) {
        repository.observeRoster(project.id, selectedDate)
    }

    val registers by registersFlow.collectAsState(initial = emptyList())
    val roster by rosterFlow.collectAsState(initial = emptyList())
    val register = registers.firstOrNull { it.shiftCode == "day" } ?: registers.firstOrNull()

    val canCreate = context.hasProjectPermission(project.id, "workforce.attendance.create")
    val canUpdate = context.hasProjectPermission(project.id, "workforce.attendance.update")
    val selectedLocalDate = LocalDate.parse(selectedDate)

    LaunchedEffect(selectedDate) {
        selectedTab = AttendanceTab.PRESENT.name
        selectedMoreStatus = AttendanceMoreStatus.LEAVE.name
        search = ""
        message = null
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Column(modifier = Modifier.weight(1f)) {
                Text("Attendance", style = MaterialTheme.typography.headlineSmall)
                Text(project.name, style = MaterialTheme.typography.bodyMedium)
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedButton(
                onClick = { selectedDate = selectedLocalDate.minusDays(1).toString() },
            ) { Text("‹") }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    selectedLocalDate.format(DateTimeFormatter.ofPattern("EEE, d MMM")),
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(selectedDate, style = MaterialTheme.typography.labelSmall)
            }
            OutlinedButton(
                onClick = { selectedDate = selectedLocalDate.plusDays(1).toString() },
                enabled = selectedLocalDate < today,
            ) { Text("›") }
        }

        if (register != null) {
            Text(
                text = syncStateLabel(register.syncState),
                color = if (register.syncState == AttendanceSyncState.NEEDS_ATTENTION) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
                style = MaterialTheme.typography.labelLarge,
                modifier = Modifier.padding(top = 10.dp),
            )
        }

        if (message != null) {
            Text(
                message.orEmpty(),
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        if (register == null) {
            AttendanceNotStarted(
                workerCount = roster.size,
                canCreate = canCreate,
                onStart = {
                    scope.launch {
                        message = null
                        runCatching {
                            repository.createLocalRegister(
                                organizationId = context.organizationId,
                                projectId = project.id,
                                attendanceDate = selectedDate,
                            )
                        }.onFailure { error ->
                            message = error.message ?: "Attendance could not be started"
                        }
                    }
                },
            )
            return
        }

        AttendanceRegisterBoard(
            register = register,
            repository = repository,
            canUpdate = canUpdate,
            selectedTab = AttendanceTab.valueOf(selectedTab),
            selectedMoreStatus = AttendanceMoreStatus.valueOf(selectedMoreStatus),
            search = search,
            onTabChange = { selectedTab = it.name },
            onMoreStatusChange = { selectedMoreStatus = it.name },
            onSearchChange = { search = it },
            onError = { message = it },
        )
    }
}

@Composable
private fun AttendanceNotStarted(
    workerCount: Int,
    canCreate: Boolean,
    onStart: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 20.dp),
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Text("Attendance not started", style = MaterialTheme.typography.titleMedium)
            Text(
                if (workerCount > 0) {
                    "$workerCount active workers are saved for this date."
                } else {
                    "No cached workers are available for this date yet."
                },
                modifier = Modifier.padding(top = 6.dp),
            )
            if (canCreate) {
                Button(
                    onClick = onStart,
                    enabled = workerCount > 0,
                    modifier = Modifier.padding(top = 16.dp),
                ) {
                    Text("Start attendance")
                }
            } else {
                Text(
                    "You have read-only access for attendance.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }
    }
}

@Composable
private fun AttendanceRegisterBoard(
    register: AttendanceRegisterEntity,
    repository: AttendanceRepository,
    canUpdate: Boolean,
    selectedTab: AttendanceTab,
    selectedMoreStatus: AttendanceMoreStatus,
    search: String,
    onTabChange: (AttendanceTab) -> Unit,
    onMoreStatusChange: (AttendanceMoreStatus) -> Unit,
    onSearchChange: (String) -> Unit,
    onError: (String?) -> Unit,
) {
    val entriesFlow = remember(register.id) { repository.observeEntries(register.id) }
    val entries by entriesFlow.collectAsState(initial = emptyList())
    val scope = rememberCoroutineScope()
    val editable = canUpdate && register.status in setOf(
        AttendanceRepository.STATUS_DRAFT,
        AttendanceRepository.STATUS_REJECTED,
    )

    val marked = entries.count { it.markStatus != AttendanceRepository.MARK_NOT_MARKED }
    val present = entries.count { it.markStatus == AttendanceRepository.MARK_PRESENT }
    val absent = entries.count { it.markStatus == AttendanceRepository.MARK_ABSENT }
    val halfDay = entries.count { it.markStatus == AttendanceRepository.MARK_HALF_DAY }
    val remaining = entries.size - marked

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        AttendanceCountCard("Total", entries.size, Modifier.weight(1f))
        AttendanceCountCard("Marked", marked, Modifier.weight(1f))
        AttendanceCountCard("Remaining", remaining, Modifier.weight(1f))
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(top = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        AttendanceTab.entries.forEach { tab ->
            val count = when (tab) {
                AttendanceTab.PRESENT -> present
                AttendanceTab.ABSENT -> absent
                AttendanceTab.HALF_DAY -> halfDay
                AttendanceTab.MORE -> entries.count {
                    it.markStatus == AttendanceRepository.MARK_LEAVE ||
                        it.markStatus == AttendanceRepository.MARK_WEEKLY_OFF
                }
            }
            if (tab == selectedTab) {
                Button(onClick = { onTabChange(tab) }) { Text("${tab.label} $count") }
            } else {
                OutlinedButton(onClick = { onTabChange(tab) }) { Text("${tab.label} $count") }
            }
        }
    }

    if (selectedTab == AttendanceTab.MORE) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(top = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            AttendanceMoreStatus.entries.forEach { status ->
                if (status == selectedMoreStatus) {
                    Button(onClick = { onMoreStatusChange(status) }) { Text(status.label) }
                } else {
                    OutlinedButton(onClick = { onMoreStatusChange(status) }) { Text(status.label) }
                }
            }
        }
    }

    OutlinedTextField(
        value = search,
        onValueChange = onSearchChange,
        label = { Text("Search worker") },
        singleLine = true,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 12.dp),
    )

    if (editable && remaining > 0) {
        Button(
            onClick = {
                scope.launch {
                    onError(null)
                    runCatching { repository.markRemainingPresent(register.id) }
                        .onFailure { onError(it.message ?: "Attendance could not be updated") }
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 10.dp),
        ) {
            Text("Mark remaining $remaining as Present")
        }
    }

    if (!editable) {
        Text(
            if (register.status in setOf("submitted", "in_review", "approved")) {
                "${register.status.replace('_', ' ')} • read only until an authorized user reopens it"
            } else {
                "Read-only attendance"
            },
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 10.dp),
        )
    }

    val targetStatus = selectedTab.markStatus ?: selectedMoreStatus.markStatus
    val normalizedSearch = search.trim()
    val visibleEntries = entries.filter { entry ->
        val belongsToBucket = entry.markStatus == targetStatus ||
            entry.markStatus == AttendanceRepository.MARK_NOT_MARKED
        val matchesSearch = normalizedSearch.isBlank() ||
            entry.workerName.contains(normalizedSearch, ignoreCase = true) ||
            entry.workerNumber.contains(normalizedSearch, ignoreCase = true) ||
            entry.trade.orEmpty().contains(normalizedSearch, ignoreCase = true)
        belongsToBucket && matchesSearch
    }

    Text(
        "${selectedTab.label} • ${visibleEntries.size} available",
        style = MaterialTheme.typography.titleSmall,
        modifier = Modifier.padding(top = 14.dp, bottom = 8.dp),
    )

    LazyColumn(
        modifier = Modifier.weight(1f),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(
            items = visibleEntries.chunked(2),
            key = { row -> row.joinToString("|") { it.assignmentId } },
        ) { row ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                row.forEach { entry ->
                    WorkerAttendanceButton(
                        entry = entry,
                        targetStatus = targetStatus,
                        editable = editable,
                        modifier = Modifier.weight(1f),
                        onClick = {
                            scope.launch {
                                onError(null)
                                val nextStatus = if (entry.markStatus == targetStatus) {
                                    AttendanceRepository.MARK_NOT_MARKED
                                } else {
                                    targetStatus
                                }
                                runCatching {
                                    repository.markWorker(
                                        registerId = register.id,
                                        assignmentId = entry.assignmentId,
                                        markStatus = nextStatus,
                                    )
                                }.onFailure {
                                    onError(it.message ?: "Attendance could not be updated")
                                }
                            }
                        },
                    )
                }
                if (row.size == 1) Spacer(modifier = Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun AttendanceCountCard(label: String, count: Int, modifier: Modifier = Modifier) {
    Card(modifier = modifier) {
        Column(
            modifier = Modifier.padding(vertical = 10.dp, horizontal = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(count.toString(), style = MaterialTheme.typography.titleLarge)
            Text(label, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun WorkerAttendanceButton(
    entry: AttendanceEntryEntity,
    targetStatus: String,
    editable: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val selected = entry.markStatus == targetStatus
    if (selected) {
        Button(
            onClick = onClick,
            enabled = editable,
            modifier = modifier,
        ) {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text("✓ ${entry.workerName}")
                if (!entry.trade.isNullOrBlank()) {
                    Text(entry.trade, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    } else {
        OutlinedButton(
            onClick = onClick,
            enabled = editable,
            modifier = modifier,
        ) {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(entry.workerName)
                if (!entry.trade.isNullOrBlank()) {
                    Text(entry.trade, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

private fun syncStateLabel(syncState: String): String = when (syncState) {
    AttendanceSyncState.SAVED_ON_DEVICE -> "Saved on device"
    AttendanceSyncState.WAITING_FOR_NETWORK -> "Waiting for network"
    AttendanceSyncState.SYNCING -> "Syncing"
    AttendanceSyncState.NEEDS_ATTENTION -> "Needs attention"
    AttendanceSyncState.SYNCED -> "Synced"
    else -> "Saved on device"
}

private fun todayFor(project: ProjectEntity): LocalDate {
    val zone = project.timezone
        ?.let { runCatching { ZoneId.of(it) }.getOrNull() }
        ?: ZoneId.systemDefault()
    return LocalDate.now(zone)
}
