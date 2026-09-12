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
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.network.SessionContextResponse
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
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
    var message by remember(project.id) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    val dayFlow = remember(project.id, selectedDate) {
        repository.observeDay(project.id, selectedDate)
    }
    val historyFlow = remember(project.id) {
        repository.observeProjectReports(project.id)
    }
    val dayReports by dayFlow.collectAsState(initial = emptyList())
    val history by historyFlow.collectAsState(initial = emptyList())
    val report = dayReports.firstOrNull { it.shiftCode == "day" } ?: dayReports.firstOrNull()
    val canCreate = context.hasProjectPermission(project.id, "field.daily_report.create")
    val canUpdate = context.hasProjectPermission(project.id, "field.daily_report.update")

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
                                notes = notes,
                            )
                        }.onFailure { error ->
                            message = error.message ?: "Daily report could not be started"
                        }
                    }
                },
                onSave = { reportId ->
                    scope.launch {
                        message = null
                        runCatching {
                            repository.saveDraftHeader(
                                reportId = reportId,
                                weatherCondition = weather,
                                notes = notes,
                            )
                        }.onFailure { error ->
                            message = error.message ?: "Daily report changes could not be saved"
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
                TextButton(
                    onClick = { onSelect(tab) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = tab.label,
                        fontWeight = if (selected == tab) FontWeight.Bold else FontWeight.Normal,
                    )
                }
                HorizontalDivider(
                    thickness = if (selected == tab) 3.dp else 1.dp,
                    color = if (selected == tab) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.outlineVariant
                    },
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
    canCreate: Boolean,
    canUpdate: Boolean,
    onWeatherChange: (String) -> Unit,
    onNotesChange: (String) -> Unit,
    onPreviousDay: () -> Unit,
    onNextDay: () -> Unit,
    onStart: () -> Unit,
    onSave: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val date = LocalDate.parse(selectedDate)

    Column(modifier = modifier) {
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
                if (date == today) {
                    Text("Today", style = MaterialTheme.typography.labelSmall)
                }
            }
            OutlinedButton(
                onClick = onNextDay,
                enabled = date < today,
            ) { Text("›") }
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
                OutlinedTextField(
                    value = weather,
                    onValueChange = onWeatherChange,
                    label = { Text("Weather (optional)") },
                    singleLine = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 16.dp),
                )
                OutlinedTextField(
                    value = notes,
                    onValueChange = onNotesChange,
                    label = { Text("Site note (optional)") },
                    minLines = 3,
                    maxLines = 6,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 10.dp),
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
            OutlinedTextField(
                value = weather,
                onValueChange = onWeatherChange,
                label = { Text("Weather (optional)") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
            )
            OutlinedTextField(
                value = notes,
                onValueChange = onNotesChange,
                label = { Text("Site note (optional)") },
                minLines = 3,
                maxLines = 6,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 10.dp),
            )
            Button(
                onClick = { onSave(report.id) },
                enabled = report.canQueueHeaderEdit(),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 14.dp),
            ) {
                Text("Save changes")
            }
            Text(
                text = when {
                    report.syncState == DprSyncState.NEEDS_ATTENTION ->
                        "This report needs sync attention before another change can be saved."
                    !report.canQueueHeaderEdit() ->
                        "Finish syncing the previous change before saving another one."
                    else ->
                        "Changes are saved on this device first and synced in the background."
                },
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 6.dp),
            )
        } else {
            DailyReportSummary(report)
        }
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
        color = if (report.syncState == DprSyncState.NEEDS_ATTENTION) {
            MaterialTheme.colorScheme.error
        } else {
            MaterialTheme.colorScheme.onSurfaceVariant
        },
        modifier = Modifier.padding(top = 2.dp, bottom = 8.dp),
    )
}

@Composable
private fun DailyReportSummary(report: DprReportEntity) {
    Column(modifier = Modifier.fillMaxWidth()) {
        DprSummaryRow("Shift", report.shiftCode)
        DprSummaryRow("Weather", report.weatherCondition?.takeIf { it.isNotBlank() } ?: "Not recorded")
        if (report.temperatureLow != null || report.temperatureHigh != null) {
            val temperature = listOfNotNull(report.temperatureLow, report.temperatureHigh)
                .joinToString(" – ")
                .plus(report.temperatureUnit?.let { " $it" }.orEmpty())
            DprSummaryRow("Temperature", temperature)
        }
        DprSummaryRow("Site note", report.notes?.takeIf { it.isNotBlank() } ?: "No note")

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
        Text(
            text = label,
            style = MaterialTheme.typography.labelLarge,
            modifier = Modifier.weight(0.34f),
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(0.66f),
        )
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
                        LocalDate.parse(report.reportDate)
                            .format(DateTimeFormatter.ofPattern("EEE, d MMM yyyy")),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        report.status.replace('_', ' '),
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
                val detail = buildList {
                    report.weatherCondition?.takeIf { it.isNotBlank() }?.let(::add)
                    add(dprSyncStateLabel(report.syncState))
                }.joinToString(" • ")
                Text(
                    detail,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 3.dp),
                )
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
