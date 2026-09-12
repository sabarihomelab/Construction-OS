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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprLifecycleRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.network.DprGenerationStatusResponse
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import retrofit2.HttpException

@Composable
fun DprReviewScreen(
    project: ProjectEntity,
    dprRepository: DprRepository,
    lifecycleRepository: DprLifecycleRepository,
    canSubmit: Boolean,
    canApprove: Boolean,
    canReopen: Boolean,
    canManage: Boolean,
    onBack: () -> Unit,
) {
    val reports by remember(project.id) {
        dprRepository.observeProjectReports(project.id)
    }.collectAsState(initial = emptyList())
    val scope = rememberCoroutineScope()
    var refreshing by remember(project.id) { mutableStateOf(false) }
    var message by remember(project.id) { mutableStateOf<String?>(null) }

    fun refresh() {
        scope.launch {
            refreshing = true
            message = null
            runCatching { dprRepository.refreshProject(project.id) }
                .onFailure {
                    message = "Could not refresh daily reports. Saved device data is still shown."
                }
            refreshing = false
        }
    }

    LaunchedEffect(project.id) { refresh() }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Column(modifier = Modifier.weight(1f).padding(start = 4.dp)) {
                Text("DPR review", style = MaterialTheme.typography.titleLarge)
                Text(project.name, style = MaterialTheme.typography.bodySmall)
            }
            OutlinedButton(onClick = { refresh() }, enabled = !refreshing) {
                Text(if (refreshing) "Refreshing" else "Refresh")
            }
        }
        HorizontalDivider()

        Text(
            "Draft entry stays local-first. Approval, rejection, reopen and void actions always use the current company-server revision.",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
        )

        message?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
        }

        if (reports.isEmpty()) {
            Text(
                "No saved daily reports are available for this project yet.",
                modifier = Modifier.padding(16.dp),
            )
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(reports, key = { it.id }) { report ->
                    DprReviewRow(
                        report = report,
                        lifecycleRepository = lifecycleRepository,
                        canSubmit = canSubmit,
                        canApprove = canApprove,
                        canReopen = canReopen,
                        canManage = canManage,
                        onActionFinished = { refresh() },
                        onMessage = { message = it },
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun DprReviewRow(
    report: DprReportEntity,
    lifecycleRepository: DprLifecycleRepository,
    canSubmit: Boolean,
    canApprove: Boolean,
    canReopen: Boolean,
    canManage: Boolean,
    onActionFinished: () -> Unit,
    onMessage: (String?) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var actionBusy by remember(report.id) { mutableStateOf(false) }
    var confirmAction by remember(report.id) { mutableStateOf<String?>(null) }
    var reason by remember(report.id) { mutableStateOf("") }
    var generation by remember(report.id, report.revision) { mutableStateOf<DprGenerationStatusResponse?>(null) }
    var generationError by remember(report.id, report.revision) { mutableStateOf(false) }

    LaunchedEffect(report.id, report.revision, report.status, report.syncState) {
        generation = null
        generationError = false
        if (
            report.status == DprLifecycleRepository.STATUS_APPROVED &&
            report.serverId != null &&
            report.syncState == DprSyncState.SYNCED
        ) {
            while (isActive) {
                val result = runCatching { lifecycleRepository.generationStatus(report.id) }
                result.onSuccess { generation = it }
                    .onFailure { generationError = true }
                val state = generation?.generationState
                if (state == "issued" || state == "failed" || generationError) break
                delay(5_000)
            }
        }
    }

    fun runAction(block: suspend () -> Unit) {
        scope.launch {
            actionBusy = true
            onMessage(null)
            runCatching { block() }
                .onSuccess {
                    confirmAction = null
                    reason = ""
                    onActionFinished()
                }
                .onFailure { error -> onMessage(dprLifecycleErrorMessage(error)) }
            actionBusy = false
        }
    }

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                runCatching {
                    LocalDate.parse(report.reportDate).format(DateTimeFormatter.ofPattern("d MMM yyyy"))
                }.getOrDefault(report.reportDate),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                report.status.replace('_', ' ').replaceFirstChar { it.uppercase() },
                style = MaterialTheme.typography.labelLarge,
            )
        }
        Text(
            "${report.shiftCode} shift • revision ${report.revision}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 3.dp),
        )
        Text(
            dprReviewSyncLabel(report.syncState),
            style = MaterialTheme.typography.bodySmall,
            color = if (report.syncState == DprSyncState.NEEDS_ATTENTION) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
            modifier = Modifier.padding(top = 2.dp),
        )

        if (report.status == DprLifecycleRepository.STATUS_APPROVED) {
            DprGenerationSummary(generation, generationError)
        }

        if (report.syncState == DprSyncState.NEEDS_ATTENTION) {
            Text(
                "This device copy was preserved because the server rejected or conflicted with a local change. Refresh/reconcile before another governed action.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        val cleanServerRevision = report.serverId != null &&
            report.revision > 0 &&
            report.syncState == DprSyncState.SYNCED

        if (report.status == DprLifecycleRepository.STATUS_DRAFT && canSubmit) {
            Button(
                onClick = { runAction { lifecycleRepository.submit(report.id) } },
                enabled = cleanServerRevision && !actionBusy,
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
            ) {
                Text("Submit report")
            }
            Text(
                if (cleanServerRevision) {
                    "Submit is queued idempotently and can complete when connectivity is available."
                } else {
                    "Finish syncing draft changes before submission."
                },
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 4.dp),
            )
        }

        if (report.status == DprLifecycleRepository.STATUS_IN_REVIEW && canApprove) {
            if (confirmAction == ACTION_APPROVE) {
                Text(
                    "Approve this exact server revision? Approval can trigger official report issuance.",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 10.dp),
                )
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Button(
                        onClick = { runAction { lifecycleRepository.approve(report.id) } },
                        enabled = !actionBusy,
                        modifier = Modifier.weight(1f),
                    ) { Text("Confirm approval") }
                    OutlinedButton(
                        onClick = { confirmAction = null },
                        enabled = !actionBusy,
                        modifier = Modifier.weight(1f),
                    ) { Text("Cancel") }
                }
            } else {
                Button(
                    onClick = { confirmAction = ACTION_APPROVE },
                    enabled = cleanServerRevision && !actionBusy,
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                ) { Text("Approve") }
            }

            OutlinedTextField(
                value = reason,
                onValueChange = { reason = it },
                label = { Text("Rejection reason") },
                minLines = 2,
                maxLines = 4,
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
            )
            OutlinedButton(
                onClick = { runAction { lifecycleRepository.reject(report.id, reason) } },
                enabled = cleanServerRevision && reason.isNotBlank() && !actionBusy,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) { Text("Reject") }
        }

        if (report.status == DprLifecycleRepository.STATUS_REJECTED && canReopen) {
            Button(
                onClick = { runAction { lifecycleRepository.reopen(report.id, reason) } },
                enabled = cleanServerRevision && !actionBusy,
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
            ) { Text("Reopen as draft") }
        }

        if (canManage && report.status != DprLifecycleRepository.STATUS_VOID) {
            if (confirmAction == ACTION_VOID) {
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Reason to void") },
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                )
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Button(
                        onClick = { runAction { lifecycleRepository.voidReport(report.id, reason) } },
                        enabled = reason.isNotBlank() && !actionBusy,
                        modifier = Modifier.weight(1f),
                    ) { Text("Confirm void") }
                    OutlinedButton(
                        onClick = { confirmAction = null },
                        enabled = !actionBusy,
                        modifier = Modifier.weight(1f),
                    ) { Text("Cancel") }
                }
            } else {
                TextButton(
                    onClick = { confirmAction = ACTION_VOID },
                    enabled = cleanServerRevision && !actionBusy,
                    modifier = Modifier.padding(top = 6.dp),
                ) { Text("Void report") }
            }
        }
    }
}

@Composable
private fun DprGenerationSummary(
    generation: DprGenerationStatusResponse?,
    failedToLoad: Boolean,
) {
    Column(modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) {
        Text("Official report", style = MaterialTheme.typography.labelLarge)
        when {
            failedToLoad -> Text(
                "Generation status could not be refreshed.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 2.dp),
            )
            generation == null -> Text(
                "Checking report generation…",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 2.dp),
            )
            generation.generationState == "issued" -> {
                Text(
                    "Issued • ${generation.outputFormat.uppercase()}",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 2.dp),
                )
                generation.filename?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 2.dp))
                }
            }
            generation.generationState == "failed" -> Text(
                "Generation failed${generation.failureCode?.let { " • $it" }.orEmpty()}",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 2.dp),
            )
            else -> Text(
                "${generation.generationState.replace('_', ' ')} • ${generation.outputFormat.uppercase()}",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 2.dp),
            )
        }
    }
}

private fun dprReviewSyncLabel(state: String): String = when (state) {
    DprSyncState.SAVED_ON_DEVICE -> "Saved on device"
    DprSyncState.WAITING_FOR_NETWORK -> "Waiting for network"
    DprSyncState.SYNCING -> "Syncing"
    DprSyncState.SYNCED -> "Synced"
    DprSyncState.NEEDS_ATTENTION -> "Needs attention"
    else -> state.replace('_', ' ')
}

private fun dprLifecycleErrorMessage(error: Throwable): String = when (error) {
    is IllegalArgumentException -> error.message ?: "The daily report action is not valid."
    is IllegalStateException -> error.message ?: "The daily report is not ready for this action."
    is HttpException -> when (error.code()) {
        403 -> "Your current project permissions no longer allow this action. Refresh your access and try again."
        404 -> "This daily report is no longer available on the company server."
        409 -> "The server has a newer daily report revision. The device copy was preserved and now needs attention."
        422 -> "The server rejected this workflow action. Check required report sections or the current report status."
        else -> "The company server could not complete this daily report action."
    }
    else -> "The daily report action could not be completed. Check the connection and try again."
}

private const val ACTION_APPROVE = "approve"
private const val ACTION_VOID = "void"
