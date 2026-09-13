package com.constructionos.app.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.ChevronLeft
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.attendance.AttendanceRepository
import com.constructionos.app.core.authorization.hasProjectPermission
import com.constructionos.app.core.database.AttendanceEntryEntity
import com.constructionos.app.core.database.AttendanceRegisterEntity
import com.constructionos.app.core.database.AttendanceSyncState
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.ui.design.CosMetricCard
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
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
    val canSubmit = context.hasProjectPermission(project.id, "workforce.attendance.submit")
    val canApprove = context.hasProjectPermission(project.id, "workforce.attendance.approve")
    val canReopen = context.hasProjectPermission(project.id, "workforce.attendance.reopen")
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
                Text("Attendance", style = MaterialTheme.typography.headlineSmall)
                Text(
                    project.name,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (register != null) {
                CosStatusPill(
                    text = syncStateLabel(register.syncState),
                    tone = attendanceSyncTone(register.syncState),
                )
            }
        }

        AttendanceDatePicker(
            date = selectedLocalDate,
            today = today,
            onPrevious = { selectedDate = selectedLocalDate.minusDays(1).toString() },
            onNext = { selectedDate = selectedLocalDate.plusDays(1).toString() },
            modifier = Modifier.padding(top = 8.dp),
        )

        if (register != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CosStatusPill(
                    text = register.status.replace('_', ' ').replaceFirstChar { it.uppercase() },
                    tone = attendanceStatusTone(register.status),
                )
                if (register.syncState == AttendanceSyncState.NEEDS_ATTENTION) {
                    CosStatusPill("Needs attention", tone = CosStatusTone.ERROR)
                }
            }
        }

        message?.let {
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 10.dp),
            ) {
                Text(it, modifier = Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
            }
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
            canSubmit = canSubmit,
            canApprove = canApprove,
            canReopen = canReopen,
            selectedTab = AttendanceTab.valueOf(selectedTab),
            selectedMoreStatus = AttendanceMoreStatus.valueOf(selectedMoreStatus),
            search = search,
            onTabChange = { selectedTab = it.name },
            onMoreStatusChange = { selectedMoreStatus = it.name },
            onSearchChange = { search = it },
            onError = { message = it },
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun AttendanceDatePicker(
    date: LocalDate,
    today: LocalDate,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onPrevious) {
                Icon(Icons.Rounded.ChevronLeft, contentDescription = "Previous day")
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    date.format(DateTimeFormatter.ofPattern("EEE, d MMM")),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    if (date == today) "Today" else date.toString(),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onNext, enabled = date < today) {
                Icon(Icons.Rounded.ChevronRight, contentDescription = "Next day")
            }
        }
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
            .padding(top = 18.dp),
        shape = MaterialTheme.shapes.extraLarge,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Surface(
                shape = MaterialTheme.shapes.large,
                color = MaterialTheme.colorScheme.primaryContainer,
                modifier = Modifier.size(52.dp),
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Rounded.Groups, contentDescription = null)
                }
            }
            Text(
                "Attendance not started",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(top = 16.dp),
            )
            Text(
                if (workerCount > 0) {
                    "$workerCount active workers are ready for this date."
                } else {
                    "No cached workers are available for this date yet."
                },
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp),
            )
            if (canCreate) {
                Button(
                    onClick = onStart,
                    enabled = workerCount > 0,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 18.dp),
                ) {
                    Text("Start attendance")
                }
            } else {
                Text(
                    "You have read-only access for attendance.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 14.dp),
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
    canSubmit: Boolean,
    canApprove: Boolean,
    canReopen: Boolean,
    selectedTab: AttendanceTab,
    selectedMoreStatus: AttendanceMoreStatus,
    search: String,
    onTabChange: (AttendanceTab) -> Unit,
    onMoreStatusChange: (AttendanceMoreStatus) -> Unit,
    onSearchChange: (String) -> Unit,
    onError: (String?) -> Unit,
    modifier: Modifier = Modifier,
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

    Column(modifier = modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            CosMetricCard(entries.size.toString(), "Total", Modifier.weight(1f))
            CosMetricCard(marked.toString(), "Marked", Modifier.weight(1f), CosStatusTone.SUCCESS)
            CosMetricCard(
                remaining.toString(),
                "Remaining",
                Modifier.weight(1f),
                if (remaining == 0) CosStatusTone.SUCCESS else CosStatusTone.WARNING,
            )
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
                FilterChip(
                    selected = tab == selectedTab,
                    onClick = { onTabChange(tab) },
                    label = { Text("${tab.label} $count") },
                )
            }
        }

        if (selectedTab == AttendanceTab.MORE) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                AttendanceMoreStatus.entries.forEach { status ->
                    FilterChip(
                        selected = status == selectedMoreStatus,
                        onClick = { onMoreStatusChange(status) },
                        label = { Text(status.label) },
                    )
                }
            }
        }

        OutlinedTextField(
            value = search,
            onValueChange = onSearchChange,
            placeholder = { Text("Search worker, number or trade") },
            leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
            singleLine = true,
            shape = MaterialTheme.shapes.large,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp),
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

        if (!editable && register.status in setOf(
                AttendanceRepository.STATUS_SUBMITTED,
                AttendanceRepository.STATUS_IN_REVIEW,
                AttendanceRepository.STATUS_APPROVED,
            )
        ) {
            Text(
                "Read only unless an authorized user reopens this register.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
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

        Row(
            modifier = Modifier.padding(top = 12.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                selectedTab.label,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            CosStatusPill("${visibleEntries.size} available")
        }

        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            items(
                items = visibleEntries.chunked(2),
                key = { row -> row.joinToString("|") { it.assignmentId } },
            ) { row ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(9.dp),
                ) {
                    if (row.isNotEmpty()) {
                        val entry = row[0]
                        WorkerAttendanceCard(
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
                    if (row.size > 1) {
                        val entry = row[1]
                        WorkerAttendanceCard(
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
                    } else {
                        Spacer(modifier = Modifier.weight(1f))
                    }
                }
            }
        }

        AttendanceWorkflowActions(
            register = register,
            repository = repository,
            remaining = remaining,
            canSubmit = canSubmit,
            canApprove = canApprove,
            canReopen = canReopen,
            onError = onError,
        )
    }
}

@Composable
private fun AttendanceWorkflowActions(
    register: AttendanceRegisterEntity,
    repository: AttendanceRepository,
    remaining: Int,
    canSubmit: Boolean,
    canApprove: Boolean,
    canReopen: Boolean,
    onError: (String?) -> Unit,
) {
    val canShowSubmit = canSubmit && register.status in setOf(
        AttendanceRepository.STATUS_DRAFT,
        AttendanceRepository.STATUS_REJECTED,
    )
    val canShowReview = canApprove && register.status == AttendanceRepository.STATUS_IN_REVIEW
    val canShowReopen = canReopen && register.status in AttendanceRepository.REOPENABLE_STATUSES
    if (!canShowSubmit && !canShowReview && !canShowReopen) return

    var reason by rememberSaveable(register.id) { mutableStateOf("") }
    var busy by remember(register.id) { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val serverReady = register.revision > 0 && register.syncState == AttendanceSyncState.SYNCED

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 10.dp),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            if (canShowSubmit) {
                Button(
                    onClick = {
                        scope.launch {
                            busy = true
                            onError(null)
                            runCatching {
                                repository.submitRegister(register.projectId, register.id)
                            }.onFailure {
                                onError(it.message ?: "Attendance could not be submitted")
                            }
                            busy = false
                        }
                    },
                    enabled = remaining == 0 && serverReady && !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Submit attendance")
                }
                when {
                    remaining > 0 -> Text(
                        "$remaining worker${if (remaining == 1) " is" else "s are"} still unmarked.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 5.dp),
                    )
                    !serverReady -> Text(
                        "Saved locally. Submit unlocks after sync completes.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 5.dp),
                    )
                }
            }

            if (canShowReview || canShowReopen) {
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text(if (canShowReview) "Review note / reason" else "Reason for reopening") },
                    shape = MaterialTheme.shapes.large,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                )
            }

            if (canShowReview) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                busy = true
                                onError(null)
                                runCatching {
                                    repository.rejectRegister(register.projectId, register.id, reason)
                                }.onSuccess { reason = "" }
                                    .onFailure { onError(it.message ?: "Attendance could not be rejected") }
                                busy = false
                            }
                        },
                        enabled = serverReady && reason.isNotBlank() && !busy,
                        modifier = Modifier.weight(1f),
                    ) { Text("Reject") }
                    Button(
                        onClick = {
                            scope.launch {
                                busy = true
                                onError(null)
                                runCatching {
                                    repository.approveRegister(register.projectId, register.id, reason)
                                }.onSuccess { reason = "" }
                                    .onFailure { onError(it.message ?: "Attendance could not be approved") }
                                busy = false
                            }
                        },
                        enabled = serverReady && !busy,
                        modifier = Modifier.weight(1f),
                    ) { Text("Approve") }
                }
            }

            if (canShowReopen) {
                TextButton(
                    onClick = {
                        scope.launch {
                            busy = true
                            onError(null)
                            runCatching {
                                repository.reopenRegister(register.projectId, register.id, reason)
                            }.onSuccess { reason = "" }
                                .onFailure { onError(it.message ?: "Attendance could not be reopened") }
                            busy = false
                        }
                    },
                    enabled = serverReady && reason.isNotBlank() && !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Reopen for correction")
                }
            }
        }
    }
}

@Composable
private fun WorkerAttendanceCard(
    entry: AttendanceEntryEntity,
    targetStatus: String,
    editable: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val selected = entry.markStatus == targetStatus
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed && editable) 0.97f else 1f,
        animationSpec = spring(stiffness = 700f, dampingRatio = 0.82f),
        label = "attendance-worker-scale",
    )

    Card(
        modifier = modifier
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .then(
                if (editable) {
                    Modifier.clickable(
                        interactionSource = interactionSource,
                        indication = null,
                        onClick = onClick,
                    )
                } else {
                    Modifier
                },
            ),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = if (selected) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)
            },
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(
                text = if (selected) "✓ ${entry.workerName}" else entry.workerName,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                maxLines = 2,
            )
            val secondary = listOfNotNull(
                entry.workerNumber.takeIf { it.isNotBlank() },
                entry.trade?.takeIf { it.isNotBlank() },
            ).joinToString(" • ")
            if (secondary.isNotBlank()) {
                Text(
                    secondary,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp),
                    maxLines = 1,
                )
            }
        }
    }
}

private fun attendanceSyncTone(syncState: String): CosStatusTone = when (syncState) {
    AttendanceSyncState.SYNCED -> CosStatusTone.SUCCESS
    AttendanceSyncState.NEEDS_ATTENTION -> CosStatusTone.ERROR
    AttendanceSyncState.SYNCING -> CosStatusTone.PRIMARY
    AttendanceSyncState.WAITING_FOR_NETWORK -> CosStatusTone.WARNING
    else -> CosStatusTone.NEUTRAL
}

private fun attendanceStatusTone(status: String): CosStatusTone = when (status) {
    AttendanceRepository.STATUS_APPROVED -> CosStatusTone.SUCCESS
    AttendanceRepository.STATUS_REJECTED -> CosStatusTone.ERROR
    AttendanceRepository.STATUS_IN_REVIEW,
    AttendanceRepository.STATUS_SUBMITTED -> CosStatusTone.PRIMARY
    else -> CosStatusTone.NEUTRAL
}

private fun syncStateLabel(syncState: String): String = when (syncState) {
    AttendanceSyncState.SAVED_ON_DEVICE -> "Saved"
    AttendanceSyncState.WAITING_FOR_NETWORK -> "Offline"
    AttendanceSyncState.SYNCING -> "Syncing"
    AttendanceSyncState.NEEDS_ATTENTION -> "Attention"
    AttendanceSyncState.SYNCED -> "Synced"
    else -> "Saved"
}

private fun todayFor(project: ProjectEntity): LocalDate {
    val zone = project.timezone
        ?.let { runCatching { ZoneId.of(it) }.getOrNull() }
        ?: ZoneId.systemDefault()
    return LocalDate.now(zone)
}
