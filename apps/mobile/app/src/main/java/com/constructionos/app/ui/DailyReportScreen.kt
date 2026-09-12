package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
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
import com.constructionos.app.core.authorization.hasProjectPermission
import com.constructionos.app.core.database.DprBoqReferenceEntity
import com.constructionos.app.core.database.DprDelayEntity
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.database.DprWbsReferenceEntity
import com.constructionos.app.core.database.DprWorkProgressEntity
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprDelayDraft
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.dpr.DprWorkProgressDraft
import com.constructionos.app.core.network.SessionContextResponse
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch

private enum class DprTab(val label: String) {
    TODAY("Today"),
    HISTORY("History"),
}

@Composable
fun DailyReportScreen(
    project: ProjectEntity,
    context: SessionContextResponse,
    repository: DprRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val today = remember(project.id, project.timezone) { dprTodayFor(project) }
    var selectedDate by rememberSaveable(project.id) { mutableStateOf(today.toString()) }
    var selectedTab by rememberSaveable(project.id) { mutableStateOf(DprTab.TODAY.name) }
    var weather by rememberSaveable(project.id, selectedDate) { mutableStateOf("") }
    var notes by rememberSaveable(project.id, selectedDate) { mutableStateOf("") }
    var enabledSections by remember(project.id) { mutableStateOf(DprRepository.DEFAULT_ENABLED_SECTIONS) }
    var message by remember(project.id) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    val dayFlow = remember(project.id, selectedDate) { repository.observeDay(project.id, selectedDate) }
    val historyFlow = remember(project.id) { repository.observeProjectReports(project.id) }
    val wbsFlow = remember(project.id) { repository.observeWbsReferences(project.id) }
    val boqFlow = remember(project.id) { repository.observeBoqReferences(project.id) }
    val dayReports by dayFlow.collectAsState(initial = emptyList())
    val history by historyFlow.collectAsState(initial = emptyList())
    val wbsReferences by wbsFlow.collectAsState(initial = emptyList())
    val boqReferences by boqFlow.collectAsState(initial = emptyList())
    val report = dayReports.firstOrNull { it.shiftCode == "day" } ?: dayReports.firstOrNull()
    val workProgressFlow = remember(report?.id) {
        report?.id?.let(repository::observeWorkProgress) ?: flowOf(emptyList())
    }
    val delaysFlow = remember(report?.id) {
        report?.id?.let(repository::observeDelays) ?: flowOf(emptyList())
    }
    val workProgress by workProgressFlow.collectAsState(initial = emptyList())
    val delays by delaysFlow.collectAsState(initial = emptyList())
    val canCreate = context.hasProjectPermission(project.id, "field.daily_report.create")
    val canUpdate = context.hasProjectPermission(project.id, "field.daily_report.update")

    LaunchedEffect(project.id, context.configurationRevision) {
        runCatching { repository.enabledSections(project.id) }
            .onSuccess { enabledSections = it }
    }

    LaunchedEffect(report?.id, report?.localUpdatedAt) {
        if (report != null) {
            weather = report.weatherCondition.orEmpty()
            notes = report.notes.orEmpty()
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Column(modifier = Modifier.weight(1f)) {
                Text("Daily report", style = MaterialTheme.typography.titleLarge)
                Text(project.name, style = MaterialTheme.typography.bodySmall)
            }
        }

        DprTabs(
            selected = DprTab.valueOf(selectedTab),
            onSelect = { selectedTab = it.name },
        )

        if (message != null) {
            Text(
                text = message.orEmpty(),
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        when (DprTab.valueOf(selectedTab)) {
            DprTab.TODAY -> DailyReportTodayContent(
                report = report,
                selectedDate = selectedDate,
                today = today,
                weather = weather,
                notes = notes,
                workProgress = workProgress,
                delays = delays,
                wbsReferences = wbsReferences,
                boqReferences = boqReferences,
                showWork = "work" in enabledSections,
                showNotes = "notes" in enabledSections,
                showDelays = "delays" in enabledSections,
                canCreate = canCreate,
                canUpdate = canUpdate,
                onWeatherChange = { weather = it },
                onNotesChange = { notes = it },
                onPreviousDay = {
                    selectedDate = LocalDate.parse(selectedDate).minusDays(1).toString()
                    message = null
                },
                onNextDay = {
                    selectedDate = LocalDate.parse(selectedDate).plusDays(1).toString()
                    message = null
                },
                onStart = {
                    scope.launch {
                        message = null
                        runCatching {
                            repository.startLocalDraft(
                                organizationId = context.organizationId,
                                projectId = project.id,
                                reportDate = selectedDate,
                                weatherCondition = weather,
                                notes = if ("notes" in enabledSections) notes else null,
                            )
                        }.onFailure { error ->
                            message = error.message ?: "Daily report could not be started"
                        }
                    }
                },
                onSaveDetails = { reportId ->
                    scope.launch {
                        message = null
                        runCatching {
                            repository.saveDraftHeader(
                                reportId = reportId,
                                weatherCondition = weather,
                                notes = if ("notes" in enabledSections) notes else report?.notes,
                            )
                        }.onFailure { error ->
                            message = error.message ?: "Daily report details could not be saved"
                        }
                    }
                },
                onSaveWorkProgress = { reportId, rows ->
                    scope.launch {
                        message = null
                        runCatching { repository.saveWorkProgress(reportId, rows) }
                            .onFailure { error ->
                                message = error.message ?: "Work progress could not be saved"
                            }
                    }
                },
                onSaveDelays = { reportId, rows ->
                    scope.launch {
                        message = null
                        runCatching { repository.saveDelays(reportId, rows) }
                            .onFailure { error ->
                                message = error.message ?: "Delay / blocker could not be saved"
                            }
                    }
                },
                modifier = Modifier.weight(1f),
            )

            DprTab.HISTORY -> DailyReportHistoryContent(
                reports = history,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun DprTabs(
    selected: DprTab,
    onSelect: (DprTab) -> Unit,
) {
    Row(modifier = Modifier.fillMaxWidth()) {
        DprTab.entries.forEach { tab ->
            Column(modifier = Modifier.weight(1f)) {
                TextButton(onClick = { onSelect(tab) }, modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = tab.label,
                        fontWeight = if (selected == tab) FontWeight.Bold else FontWeight.Normal,
                    )
                }
                HorizontalDivider(
                    thickness = if (selected == tab) 3.dp else 1.dp,
                    color = if (selected == tab) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
                )
            }
        }
    }
}

@Composable
private fun DailyReportTodayContent(
    report: DprReportEntity?,
    selectedDate: String,
    today: LocalDate,
    weather: String,
    notes: String,
    workProgress: List<DprWorkProgressEntity>,
    delays: List<DprDelayEntity>,
    wbsReferences: List<DprWbsReferenceEntity>,
    boqReferences: List<DprBoqReferenceEntity>,
    showWork: Boolean,
    showNotes: Boolean,
    showDelays: Boolean,
    canCreate: Boolean,
    canUpdate: Boolean,
    onWeatherChange: (String) -> Unit,
    onNotesChange: (String) -> Unit,
    onPreviousDay: () -> Unit,
    onNextDay: () -> Unit,
    onStart: () -> Unit,
    onSaveDetails: (String) -> Unit,
    onSaveWorkProgress: (String, List<DprWorkProgressDraft>) -> Unit,
    onSaveDelays: (String, List<DprDelayDraft>) -> Unit,
    modifier: Modifier = Modifier,
) {
    val date = LocalDate.parse(selectedDate)

    Column(modifier = modifier.verticalScroll(rememberScrollState())) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedButton(onClick = onPreviousDay) { Text("‹") }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = date.format(DateTimeFormatter.ofPattern("EEE, d MMM")),
                    style = MaterialTheme.typography.titleMedium,
                )
                if (date == today) Text("Today", style = MaterialTheme.typography.labelSmall)
            }
            OutlinedButton(onClick = onNextDay, enabled = date < today) { Text("›") }
        }

        HorizontalDivider()

        if (report == null) {
            Text(
                "No daily report yet",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 18.dp),
            )
            Text(
                "Start with the minimum site information. The draft is saved on this device first.",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 4.dp),
            )
            if (canCreate) {
                DprReportDetailsFields(
                    weather = weather,
                    notes = notes,
                    showNotes = showNotes,
                    onWeatherChange = onWeatherChange,
                    onNotesChange = onNotesChange,
                )
                Button(
                    onClick = onStart,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 14.dp),
                ) {
                    Text("Start report")
                }
            } else {
                Text(
                    "You have view-only access for daily reports.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 14.dp),
                )
            }
            return
        }

        DailyReportStatus(report)

        if (report.status == DprRepository.STATUS_DRAFT && canUpdate) {
            DprReportDetailsFields(
                weather = weather,
                notes = notes,
                showNotes = showNotes,
                onWeatherChange = onWeatherChange,
                onNotesChange = onNotesChange,
            )
            Button(
                onClick = { onSaveDetails(report.id) },
                enabled = report.canQueueHeaderEdit(),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 14.dp),
            ) {
                Text("Save report details")
            }
            Text(
                text = when {
                    report.syncState == DprSyncState.NEEDS_ATTENTION ->
                        "This report needs sync attention before another details change can be saved."
                    !report.canQueueHeaderEdit() ->
                        "Finish syncing the previous report change before saving details again."
                    else ->
                        "Report details are saved on this device first and synced in the background."
                },
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 6.dp),
            )
        } else {
            DailyReportSummary(report, showNotes)
        }

        if (showWork) {
            DprWorkProgressSection(
                report = report,
                rows = workProgress,
                wbsReferences = wbsReferences,
                boqReferences = boqReferences,
                editable = report.status == DprRepository.STATUS_DRAFT && canUpdate,
                onSave = { drafts -> onSaveWorkProgress(report.id, drafts) },
            )
        }

        if (showDelays) {
            DprDelaysSection(
                report = report,
                rows = delays,
                editable = report.status == DprRepository.STATUS_DRAFT && canUpdate,
                onSave = { drafts -> onSaveDelays(report.id, drafts) },
            )
        }
    }
}

@Composable
private fun DprReportDetailsFields(
    weather: String,
    notes: String,
    showNotes: Boolean,
    onWeatherChange: (String) -> Unit,
    onNotesChange: (String) -> Unit,
) {
    Text(
        "Report details",
        style = MaterialTheme.typography.titleSmall,
        modifier = Modifier.padding(top = 12.dp),
    )
    OutlinedTextField(
        value = weather,
        onValueChange = onWeatherChange,
        label = { Text("Weather (optional)") },
        singleLine = true,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    if (showNotes) {
        Text(
            "Notes",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(top = 14.dp),
        )
        OutlinedTextField(
            value = notes,
            onValueChange = onNotesChange,
            label = { Text("Site notes (optional)") },
            minLines = 3,
            maxLines = 6,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 6.dp),
        )
    }
}

@Composable
private fun DprWorkProgressSection(
    report: DprReportEntity,
    rows: List<DprWorkProgressEntity>,
    wbsReferences: List<DprWbsReferenceEntity>,
    boqReferences: List<DprBoqReferenceEntity>,
    editable: Boolean,
    onSave: (List<DprWorkProgressDraft>) -> Unit,
) {
    var search by rememberSaveable(report.id) { mutableStateOf("") }
    var selectedWbsId by rememberSaveable(report.id) { mutableStateOf<String?>(null) }
    var selectedBoqId by rememberSaveable(report.id) { mutableStateOf<String?>(null) }
    var description by rememberSaveable(report.id) { mutableStateOf("") }
    var location by rememberSaveable(report.id) { mutableStateOf("") }
    var quantity by rememberSaveable(report.id) { mutableStateOf("") }
    var unitCode by rememberSaveable(report.id) { mutableStateOf("") }
    var progress by rememberSaveable(report.id) { mutableStateOf("") }
    var remarks by rememberSaveable(report.id) { mutableStateOf("") }

    HorizontalDivider(modifier = Modifier.padding(top = 22.dp))
    Text(
        "Work progress",
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(top = 16.dp),
    )
    Text(
        if (rows.isEmpty()) "No work progress recorded yet" else "${rows.size} work item${if (rows.size == 1) "" else "s"} recorded",
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier.padding(top = 3.dp, bottom = 8.dp),
    )

    rows.forEach { row ->
        val reference = when {
            row.boqItemId != null -> boqReferences.firstOrNull { it.id == row.boqItemId }
                ?.let { "${it.boqCode} • ${it.itemCode}" }
            row.wbsCodeId != null -> wbsReferences.firstOrNull { it.id == row.wbsCodeId }
                ?.let { "${it.code} • ${it.name}" }
            else -> null
        } ?: "Linked work item"
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 10.dp),
        ) {
            Text(reference, style = MaterialTheme.typography.labelLarge)
            Text(row.description, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 2.dp))
            val details = buildList {
                row.quantity?.let { value -> add(value + row.unitCode?.let { " $it" }.orEmpty()) }
                row.progressPercent?.let { add("$it%") }
                row.location?.takeIf { it.isNotBlank() }?.let(::add)
            }.joinToString(" • ")
            if (details.isNotBlank()) {
                Text(details, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
            }
            row.remarks?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
            }
            if (editable) {
                TextButton(
                    onClick = { onSave(rows.filterNot { it.id == row.id }.map(DprWorkProgressEntity::toDraft)) },
                ) {
                    Text("Remove")
                }
            }
        }
        HorizontalDivider()
    }

    if (!editable) return

    Text(
        "Add work",
        style = MaterialTheme.typography.titleSmall,
        modifier = Modifier.padding(top = 18.dp),
    )
    OutlinedTextField(
        value = search,
        onValueChange = { search = it },
        label = { Text("Find WBS or approved BOQ item") },
        singleLine = true,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )

    val normalizedSearch = search.trim().lowercase()
    val matchingWbs = wbsReferences.asSequence()
        .filter {
            normalizedSearch.isEmpty() ||
                it.code.lowercase().contains(normalizedSearch) ||
                it.name.lowercase().contains(normalizedSearch)
        }
        .take(4)
        .toList()
    val matchingBoq = boqReferences.asSequence()
        .filter {
            normalizedSearch.isEmpty() ||
                it.boqCode.lowercase().contains(normalizedSearch) ||
                it.itemCode.lowercase().contains(normalizedSearch) ||
                it.description.lowercase().contains(normalizedSearch)
        }
        .take(4)
        .toList()

    if (matchingWbs.isNotEmpty()) {
        Text("WBS / Cost Codes", style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(top = 10.dp))
        matchingWbs.forEach { item ->
            TextButton(
                onClick = {
                    selectedWbsId = item.id
                    selectedBoqId = null
                    search = "${item.code} • ${item.name}"
                    if (description.isBlank()) description = item.name
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("${item.code} • ${item.name}", modifier = Modifier.fillMaxWidth())
            }
        }
    }

    if (matchingBoq.isNotEmpty()) {
        Text("Approved BOQ", style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(top = 8.dp))
        matchingBoq.forEach { item ->
            TextButton(
                onClick = {
                    selectedBoqId = item.id
                    selectedWbsId = item.wbsCodeId
                    search = "${item.boqCode} • ${item.itemCode}"
                    description = item.description
                    unitCode = item.unitCode
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("${item.boqCode} • ${item.itemCode} — ${item.description}", modifier = Modifier.fillMaxWidth())
            }
        }
    }

    OutlinedTextField(
        value = description,
        onValueChange = { description = it },
        label = { Text("Work description") },
        minLines = 2,
        maxLines = 4,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    OutlinedTextField(
        value = location,
        onValueChange = { location = it },
        label = { Text("Location (optional)") },
        singleLine = true,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        OutlinedTextField(
            value = quantity,
            onValueChange = { quantity = it },
            label = { Text("Quantity") },
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
        OutlinedTextField(
            value = unitCode,
            onValueChange = { unitCode = it },
            label = { Text("Unit") },
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
    }
    OutlinedTextField(
        value = progress,
        onValueChange = { progress = it },
        label = { Text("Progress % (optional)") },
        singleLine = true,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    OutlinedTextField(
        value = remarks,
        onValueChange = { remarks = it },
        label = { Text("Remarks (optional)") },
        minLines = 2,
        maxLines = 4,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    Button(
        onClick = {
            val next = rows.map(DprWorkProgressEntity::toDraft) + DprWorkProgressDraft(
                wbsCodeId = selectedWbsId,
                boqItemId = selectedBoqId,
                description = description,
                location = location,
                quantity = quantity,
                unitCode = unitCode,
                progressPercent = progress,
                remarks = remarks,
            )
            onSave(next)
            selectedWbsId = null
            selectedBoqId = null
            search = ""
            description = ""
            location = ""
            quantity = ""
            unitCode = ""
            progress = ""
            remarks = ""
        },
        enabled = (selectedWbsId != null || selectedBoqId != null) && description.isNotBlank(),
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 12.dp, bottom = 24.dp),
    ) {
        Text("Add work progress")
    }
}

@Composable
private fun DailyReportStatus(report: DprReportEntity) {
    Text(
        text = report.status.replace('_', ' ').replaceFirstChar { it.uppercase() },
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(top = 18.dp),
    )
    Text(
        text = dprSyncStateLabel(report.syncState),
        style = MaterialTheme.typography.labelMedium,
        color = if (report.syncState == DprSyncState.NEEDS_ATTENTION) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 2.dp, bottom = 8.dp),
    )
}

@Composable
private fun DailyReportSummary(report: DprReportEntity, showNotes: Boolean) {
    Column(modifier = Modifier.fillMaxWidth()) {
        DprSummaryRow("Shift", report.shiftCode)
        DprSummaryRow("Weather", report.weatherCondition?.takeIf { it.isNotBlank() } ?: "Not recorded")
        if (report.temperatureLow != null || report.temperatureHigh != null) {
            val temperature = listOfNotNull(report.temperatureLow, report.temperatureHigh)
                .joinToString(" – ")
                .plus(report.temperatureUnit?.let { " $it" }.orEmpty())
            DprSummaryRow("Temperature", temperature)
        }
        if (showNotes) {
            DprSummaryRow("Notes", report.notes?.takeIf { it.isNotBlank() } ?: "No notes")
        }

        if (report.serverId == null) {
            Text(
                "Saved locally. Server creation will retry automatically when a connection is available.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 14.dp),
            )
        }
    }
}

@Composable
private fun DprSummaryRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(text = label, style = MaterialTheme.typography.labelLarge, modifier = Modifier.weight(0.34f))
        Text(text = value, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(0.66f))
    }
    HorizontalDivider()
}

@Composable
private fun DailyReportHistoryContent(
    reports: List<DprReportEntity>,
    modifier: Modifier = Modifier,
) {
    if (reports.isEmpty()) {
        Column(
            modifier = modifier
                .fillMaxWidth()
                .padding(top = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("No saved daily reports yet")
        }
        return
    }

    LazyColumn(modifier = modifier) {
        items(reports, key = { it.id }) { report ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 12.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        LocalDate.parse(report.reportDate).format(DateTimeFormatter.ofPattern("EEE, d MMM yyyy")),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(report.status.replace('_', ' '), style = MaterialTheme.typography.labelMedium)
                }
                val detail = buildList {
                    report.weatherCondition?.takeIf { it.isNotBlank() }?.let(::add)
                    add(dprSyncStateLabel(report.syncState))
                }.joinToString(" • ")
                Text(detail, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
                report.notes?.takeIf { it.isNotBlank() }?.let { note ->
                    Text(
                        note,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 2,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
            }
            HorizontalDivider()
        }
    }
}

private fun DprWorkProgressEntity.toDraft(): DprWorkProgressDraft = DprWorkProgressDraft(
    id = id,
    wbsCodeId = wbsCodeId,
    boqItemId = boqItemId,
    description = description,
    location = location,
    quantity = quantity,
    unitCode = unitCode,
    progressPercent = progressPercent,
    remarks = remarks,
)

private fun DprReportEntity.canQueueHeaderEdit(): Boolean = when {
    syncState == DprSyncState.NEEDS_ATTENTION -> false
    serverId == null -> syncState != DprSyncState.SYNCING
    else -> syncState == DprSyncState.SYNCED
}

private fun dprSyncStateLabel(syncState: String): String = when (syncState) {
    DprSyncState.SAVED_ON_DEVICE -> "Saved on device"
    DprSyncState.WAITING_FOR_NETWORK -> "Waiting for network"
    DprSyncState.SYNCING -> "Syncing"
    DprSyncState.SYNCED -> "Synced"
    DprSyncState.NEEDS_ATTENTION -> "Needs attention"
    else -> "Saved on device"
}

private fun dprTodayFor(project: ProjectEntity): LocalDate {
    val zone = project.timezone
        ?.let { runCatching { ZoneId.of(it) }.getOrNull() }
        ?: ZoneId.systemDefault()
    return LocalDate.now(zone)
}
