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
import androidx.compose.material.icons.rounded.ChevronLeft
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.DprAttendanceSummaryEntity
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprAttendanceRefreshResult
import com.constructionos.app.core.dpr.DprAttendanceSummaryRepository
import com.constructionos.app.ui.design.CosMetricCard
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
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

    val date = LocalDate.parse(selectedDate)

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
                Text("DPR crew", style = MaterialTheme.typography.headlineSmall)
                Text(
                    project.name,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = ::refresh, enabled = !refreshing) {
                Icon(Icons.Rounded.Refresh, contentDescription = "Refresh")
            }
        }

        Card(
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            shape = MaterialTheme.shapes.large,
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(
                    onClick = {
                        selectedDate = date.minusDays(1).toString()
                        message = null
                    },
                ) {
                    Icon(Icons.Rounded.ChevronLeft, contentDescription = "Previous day")
                }
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        date.format(DateTimeFormatter.ofPattern("EEE, d MMM")),
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        if (date == today) "Today • Day shift" else "Day shift",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                IconButton(
                    onClick = {
                        selectedDate = date.plusDays(1).toString()
                        message = null
                    },
                    enabled = date < today,
                ) {
                    Icon(Icons.Rounded.ChevronRight, contentDescription = "Next day")
                }
            }
        }

        message?.let { text ->
            Surface(
                color = if (rows.isEmpty()) {
                    MaterialTheme.colorScheme.surfaceVariant
                } else {
                    MaterialTheme.colorScheme.errorContainer
                },
                contentColor = if (rows.isEmpty()) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onErrorContainer
                },
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                Text(text, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(10.dp))
            }
        }

        if (rows.isEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 30.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                if (refreshing) {
                    CircularProgressIndicator(modifier = Modifier.size(30.dp))
                } else {
                    Icon(
                        Icons.Rounded.Groups,
                        contentDescription = null,
                        modifier = Modifier.size(40.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    if (refreshing) {
                        "Checking approved attendance…"
                    } else {
                        "No approved crew summary cached"
                    },
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 10.dp),
                )
            }
        } else {
            val totals = remember(rows) { DprAttendanceTotals.from(rows) }
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(top = 10.dp),
                verticalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                item(key = "summary") {
                    DprAttendanceTotalsCard(totals)
                    Surface(
                        shape = MaterialTheme.shapes.medium,
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.42f),
                        modifier = Modifier.fillMaxWidth().padding(top = 9.dp),
                    ) {
                        Text(
                            "Read-only projection of approved attendance. The server owns approval status and crew-hour calculations.",
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(11.dp),
                        )
                    }
                }
                items(
                    items = rows,
                    key = { "${it.registerId}:${it.groupKey}" },
                ) { row ->
                    DprAttendanceGroupCard(row)
                }
            }
        }
    }
}

@Composable
private fun DprAttendanceTotalsCard(totals: DprAttendanceTotals) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.extraLarge,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Approved attendance", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                CosStatusPill("Approved", CosStatusTone.SUCCESS)
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CosMetricCard(totals.workerCount.toString(), "Workers", Modifier.weight(1f))
                CosMetricCard(totals.presentCount.toString(), "Present", Modifier.weight(1f), CosStatusTone.SUCCESS)
                CosMetricCard(totals.absentCount.toString(), "Absent", Modifier.weight(1f), CosStatusTone.ERROR)
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CosMetricCard("${formatHours(totals.regularHours)} h", "Regular", Modifier.weight(1f))
                CosMetricCard("${formatHours(totals.overtimeHours)} h", "Overtime", Modifier.weight(1f), CosStatusTone.WARNING)
            }
        }
    }
}

@Composable
private fun DprAttendanceGroupCard(row: DprAttendanceSummaryEntity) {
    val groupLabel = buildList {
        row.trade?.takeIf { it.isNotBlank() }?.let { add(it) }
        if (row.crewId != null) add("Crew")
        if (row.employerPartyId != null) add("Employer")
    }.joinToString(" • ").ifBlank { "General crew" }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(groupLabel, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                CosStatusPill("${row.workerCount} workers")
            }
            Text(
                "${row.presentCount} present • ${row.absentCount} absent",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 7.dp),
            )
            Text(
                "${formatHours(row.regularHours.toBigDecimalOrNull() ?: BigDecimal.ZERO)} regular h • " +
                    "${formatHours(row.overtimeHours.toBigDecimalOrNull() ?: BigDecimal.ZERO)} OT h",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 3.dp),
            )
        }
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
