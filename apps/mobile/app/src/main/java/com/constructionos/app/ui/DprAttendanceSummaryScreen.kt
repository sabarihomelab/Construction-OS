package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.DprAttendanceSummaryEntity
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprAttendanceRefreshResult
import com.constructionos.app.core.dpr.DprAttendanceSummaryRepository
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.launch
import retrofit2.HttpException

@Composable
fun DprAttendanceSummaryScreen(
    project: ProjectEntity,
    repository: DprAttendanceSummaryRepository,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val today = remember(project.id, project.timezone) { attendanceSummaryToday(project) }
    var selectedDate by rememberSaveable(project.id) { mutableStateOf(today.toString()) }
    var refreshing by remember(project.id) { mutableStateOf(false) }
    var message by remember(project.id) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val summaryFlow = remember(project.id, selectedDate) {
        repository.observe(project.id, selectedDate, DEFAULT_SHIFT)
    }
    val rows by summaryFlow.collectAsState(initial = emptyList())

    fun refresh() {
        scope.launch {
            refreshing = true
            message = null
            runCatching {
                repository.refresh(project.id, selectedDate, DEFAULT_SHIFT)
            }.onSuccess { result ->
                if (result == DprAttendanceRefreshResult.NO_APPROVED_ATTENDANCE) {
                    message = "No approved attendance is available for this date and shift."
                }
            }.onFailure { error ->
                message = attendanceSummaryError(error, rows.isNotEmpty())
            }
            refreshing = false
        }
    }

    LaunchedEffect(project.id, selectedDate) { refresh() }

    Column(modifier = modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Column(modifier = Modifier.weight(1f).padding(start = 4.dp)) {
                Text("DPR crew", style = MaterialTheme.typography.titleLarge)
                Text(project.name, style = MaterialTheme.typography.bodySmall)
            }
            OutlinedButton(onClick = { refresh() }, enabled = !refreshing) {
                Text(if (refreshing) "Refreshing" else "Refresh")
            }
        }
        HorizontalDivider()

        val date = LocalDate.parse(selectedDate)
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedButton(
                onClick = {
                    selectedDate = date.minusDays(1).toString()
                    message = null
                },
            ) { Text("‹") }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    date.format(DateTimeFormatter.ofPattern("EEE, d MMM")),
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    if (date == today) "Today • Day shift" else "Day shift",
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            OutlinedButton(
                onClick = {
                    selectedDate = date.plusDays(1).toString()
                    message = null
                },
                enabled = date < today,
            ) { Text("›") }
        }

        message?.let { text ->
            Text(
                text = text,
                color = if (rows.isEmpty()) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.error
                },
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
        }

        if (rows.isEmpty()) {
            Text(
                if (refreshing) {
                    "Checking the company server for approved attendance…"
                } else {
                    "No approved attendance summary is cached on this device for this date."
                },
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(16.dp),
            )
        } else {
            val totals = remember(rows) { DprAttendanceTotals.from(rows) }
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                item(key = "summary") {
                    DprAttendanceTotalsCard(totals)
                    Text(
                        "This is a read-only projection of approved attendance. The server owns approval status and crew-hour calculations; this device only caches the returned summary.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                    )
                    HorizontalDivider()
                }
                items(
                    items = rows,
                    key = { "${it.registerId}:${it.groupKey}" },
                ) { row ->
                    DprAttendanceGroupRow(row)
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun DprAttendanceTotalsCard(totals: DprAttendanceTotals) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text("Approved attendance", style = MaterialTheme.typography.titleMedium)
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            SummaryMetric("Workers", totals.workerCount.toString(), Modifier.weight(1f))
            SummaryMetric("Present", totals.presentCount.toString(), Modifier.weight(1f))
            SummaryMetric("Absent", totals.absentCount.toString(), Modifier.weight(1f))
            SummaryMetric("Other", totals.otherCount.toString(), Modifier.weight(1f))
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            SummaryMetric("Regular", "${formatHours(totals.regularHours)} h", Modifier.weight(1f))
            SummaryMetric("Overtime", "${formatHours(totals.overtimeHours)} h", Modifier.weight(1f))
        }
    }
}

@Composable
private fun SummaryMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(label, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun DprAttendanceGroupRow(row: DprAttendanceSummaryEntity) {
    val groupLabel = buildList {
        row.trade?.takeIf { it.isNotBlank() }?.let { add(it) }
        if (row.crewId != null) add("Crew")
        if (row.employerPartyId != null) add("Employer")
    }.joinToString(" • ").ifBlank { "General crew" }

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(groupLabel, style = MaterialTheme.typography.titleSmall)
        Text(
            "${row.workerCount} workers • ${row.presentCount} present • ${row.absentCount} absent",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 3.dp),
        )
        Text(
            "${formatHours(row.regularHours.toBigDecimalOrNull() ?: BigDecimal.ZERO)} regular h • " +
                "${formatHours(row.overtimeHours.toBigDecimalOrNull() ?: BigDecimal.ZERO)} OT h",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 2.dp),
        )
    }
}

private data class DprAttendanceTotals(
    val workerCount: Int,
    val presentCount: Int,
    val absentCount: Int,
    val otherCount: Int,
    val regularHours: BigDecimal,
    val overtimeHours: BigDecimal,
) {
    companion object {
        fun from(rows: List<DprAttendanceSummaryEntity>): DprAttendanceTotals {
            val workers = rows.sumOf { it.workerCount }
            val present = rows.sumOf { it.presentCount }
            val absent = rows.sumOf { it.absentCount }
            return DprAttendanceTotals(
                workerCount = workers,
                presentCount = present,
                absentCount = absent,
                otherCount = (workers - present - absent).coerceAtLeast(0),
                regularHours = rows.fold(BigDecimal.ZERO) { total, row ->
                    total + (row.regularHours.toBigDecimalOrNull() ?: BigDecimal.ZERO)
                },
                overtimeHours = rows.fold(BigDecimal.ZERO) { total, row ->
                    total + (row.overtimeHours.toBigDecimalOrNull() ?: BigDecimal.ZERO)
                },
            )
        }
    }
}

private fun formatHours(value: BigDecimal): String = value.stripTrailingZeros().toPlainString()

private fun attendanceSummaryToday(project: ProjectEntity): LocalDate {
    val zone = project.timezone
        ?.let { runCatching { ZoneId.of(it) }.getOrNull() }
        ?: ZoneId.systemDefault()
    return LocalDate.now(zone)
}

private fun attendanceSummaryError(error: Throwable, hasCache: Boolean): String = when (error) {
    is HttpException -> when (error.code()) {
        401 -> "Session expired while refreshing approved attendance."
        403 -> "The server no longer allows attendance summary access for this project."
        404 -> "The approved attendance register is no longer available."
        422 -> "Attendance is no longer approved for DPR use."
        429 -> "The server is busy. The saved attendance summary is still available."
        else -> if (hasCache) {
            "Could not refresh approved attendance. The saved summary is still shown."
        } else {
            "Could not load approved attendance from the company server."
        }
    }
    else -> if (hasCache) {
        "Could not refresh approved attendance. The saved summary is still shown."
    } else {
        "No approved attendance summary is available offline on this device yet."
    }
}

private const val DEFAULT_SHIFT = "day"
