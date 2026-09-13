package com.constructionos.app.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
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
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprLifecycleRepository
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.network.DprGenerationStatusResponse
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
import java.io.File
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

    Column(
        modifier = Modifier
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
                Text("DPR review", style = MaterialTheme.typography.headlineSmall)
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

        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp),
        ) {
            Text(
                "Draft entry stays local-first. Approval, rejection, reopen and void always use the current company-server revision.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(12.dp),
            )
        }

        message?.let {
            Surface(
                color = MaterialTheme.colorScheme.errorContainer,
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) {
                Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(10.dp))
            }
        }

        if (reports.isEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 30.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(
                    Icons.Rounded.Description,
                    contentDescription = null,
                    modifier = Modifier.size(40.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "No saved daily reports yet",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 10.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(top = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(reports, key = { it.id }) { report ->
                    DprReviewCard(
                        report = report,
                        lifecycleRepository = lifecycleRepository,
                        canSubmit = canSubmit,
                        canApprove = canApprove,
                        canReopen = canReopen,
                        canManage = canManage,
                        onActionFinished = { refresh() },
                        onMessage = { message = it },
                    )
                }
            }
        }
    }
}

@Composable
private fun DprReviewCard(
    report: DprReportEntity,
    lifecycleRepository: DprLifecycleRepository,
    canSubmit: Boolean,
    canApprove: Boolean,
    canReopen: Boolean,
    canManage: Boolean,
    onActionFinished: () -> Unit,
    onMessage: (String?) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var actionBusy by remember(report.id) { mutableStateOf(false) }
    var downloadBusy by remember(report.id) { mutableStateOf(false) }
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

    fun downloadIssued(current: DprGenerationStatusResponse) {
        scope.launch {
            downloadBusy = true
            onMessage(null)
            runCatching {
                val file = lifecycleRepository.downloadIssuedReport(report.id, current)
                openIssuedDpr(context, file, current.outputFormat)
            }.onFailure { error ->
                onMessage(
                    if (error is ActivityNotFoundException) {
                        "The issued report was downloaded, but no installed app can open this file type."
                    } else {
                        dprLifecycleErrorMessage(error)
                    },
                )
            }
            downloadBusy = false
        }
    }

    val cleanServerRevision = report.serverId != null &&
        report.revision > 0 &&
        report.syncState == DprSyncState.SYNCED

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.extraLarge,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        runCatching {
                            LocalDate.parse(report.reportDate)
                                .format(DateTimeFormatter.ofPattern("d MMM yyyy"))
                        }.getOrDefault(report.reportDate),
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "${report.shiftCode.replaceFirstChar { it.uppercase() }} shift • Revision ${report.revision}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 3.dp),
                    )
                }
                CosStatusPill(
                    text = report.status.replace('_', ' ').replaceFirstChar { it.uppercase() },
                    tone = dprReviewStatusTone(report.status),
                )
            }

            Row(
                modifier = Modifier.padding(top = 9.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                CosStatusPill(
                    text = dprReviewSyncLabel(report.syncState),
                    tone = dprReviewSyncTone(report.syncState),
                )
                if (report.serverId == null) {
                    CosStatusPill("Local draft", CosStatusTone.WARNING)
                }
            }

            if (report.status == DprLifecycleRepository.STATUS_APPROVED) {
                DprGenerationSummary(
                    generation = generation,
                    failedToLoad = generationError,
                    downloadBusy = downloadBusy,
                    onDownload = ::downloadIssued,
                )
            }

            if (report.syncState == DprSyncState.NEEDS_ATTENTION) {
                Surface(
                    color = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer,
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                ) {
                    Text(
                        "This device copy was preserved because the server rejected or conflicted with a local change. Refresh and reconcile before another governed action.",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(11.dp),
                    )
                }
            }

            if (report.status == DprLifecycleRepository.STATUS_DRAFT && canSubmit) {
                Button(
                    onClick = { runAction { lifecycleRepository.submit(report.id) } },
                    enabled = cleanServerRevision && !actionBusy,
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                ) {
                    Text("Submit report")
                }
                Text(
                    if (cleanServerRevision) {
                        "Submission is idempotent and can complete when connectivity is available."
                    } else {
                        "Finish syncing draft changes before submission."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 5.dp),
                )
            }

            if (report.status == DprLifecycleRepository.STATUS_IN_REVIEW && canApprove) {
                if (confirmAction == ACTION_APPROVE) {
                    Surface(
                        color = MaterialTheme.colorScheme.tertiaryContainer,
                        shape = MaterialTheme.shapes.large,
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("Confirm approval", style = MaterialTheme.typography.titleMedium)
                            Text(
                                "Approve this exact server revision? Approval can trigger official report issuance.",
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(top = 4.dp),
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Button(
                                    onClick = { runAction { lifecycleRepository.approve(report.id) } },
                                    enabled = !actionBusy,
                                    modifier = Modifier.weight(1f),
                                ) { Text("Approve") }
                                OutlinedButton(
                                    onClick = { confirmAction = null },
                                    enabled = !actionBusy,
                                    modifier = Modifier.weight(1f),
                                ) { Text("Cancel") }
                            }
                        }
                    }
                } else {
                    Button(
                        onClick = { confirmAction = ACTION_APPROVE },
                        enabled = cleanServerRevision && !actionBusy,
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    ) { Text("Review approval") }
                }

                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Rejection reason") },
                    minLines = 2,
                    maxLines = 4,
                    shape = MaterialTheme.shapes.large,
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                )
                OutlinedButton(
                    onClick = { runAction { lifecycleRepository.reject(report.id, reason) } },
                    enabled = cleanServerRevision && reason.isNotBlank() && !actionBusy,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                ) { Text("Reject report") }
            }

            if (report.status == DprLifecycleRepository.STATUS_REJECTED && canReopen) {
                Button(
                    onClick = { runAction { lifecycleRepository.reopen(report.id, reason) } },
                    enabled = cleanServerRevision && !actionBusy,
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                ) { Text("Reopen as draft") }
            }

            if (canManage && report.status != DprLifecycleRepository.STATUS_VOID) {
                if (confirmAction == ACTION_VOID) {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        contentColor = MaterialTheme.colorScheme.onErrorContainer,
                        shape = MaterialTheme.shapes.large,
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("Void report", style = MaterialTheme.typography.titleMedium)
                            OutlinedTextField(
                                value = reason,
                                onValueChange = { reason = it },
                                label = { Text("Reason to void") },
                                minLines = 2,
                                maxLines = 4,
                                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
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
                        }
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
}

@Composable
private fun DprGenerationSummary(
    generation: DprGenerationStatusResponse?,
    failedToLoad: Boolean,
    downloadBusy: Boolean,
    onDownload: (DprGenerationStatusResponse) -> Unit,
) {
    Surface(
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
    ) {
        Column(modifier = Modifier.padding(13.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Official report", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                val state = generation?.generationState
                if (state != null) {
                    CosStatusPill(
                        text = state.replace('_', ' ').replaceFirstChar { it.uppercase() },
                        tone = when (state) {
                            "issued" -> CosStatusTone.SUCCESS
                            "failed" -> CosStatusTone.ERROR
                            else -> CosStatusTone.PRIMARY
                        },
                    )
                }
            }
            when {
                failedToLoad -> Text(
                    "Generation status could not be refreshed.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 6.dp),
                )
                generation == null -> Text(
                    "Checking report generation…",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp),
                )
                generation.generationState == "issued" -> {
                    Text(
                        "${generation.outputFormat.uppercase()}${generation.filename?.let { " • $it" }.orEmpty()}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                    Button(
                        onClick = { onDownload(generation) },
                        enabled = !downloadBusy && generation.renderId != null,
                        modifier = Modifier.fillMaxWidth().padding(top = 9.dp),
                    ) {
                        Text(if (downloadBusy) "Downloading…" else "Download & open")
                    }
                }
                generation.generationState == "failed" -> Text(
                    "Generation failed${generation.failureCode?.let { " • $it" }.orEmpty()}",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 6.dp),
                )
                else -> Text(
                    "${generation.generationState.replace('_', ' ')} • ${generation.outputFormat.uppercase()}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
}

private fun openIssuedDpr(context: Context, file: File, outputFormat: String) {
    val uri = FileProvider.getUriForFile(
        context,
        "${context.packageName}.fileprovider",
        file,
    )
    val mimeType = when (outputFormat.lowercase()) {
        "pdf" -> "application/pdf"
        "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else -> "application/octet-stream"
    }
    val viewIntent = Intent(Intent.ACTION_VIEW)
        .setDataAndType(uri, mimeType)
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    val chooser = Intent.createChooser(viewIntent, "Open issued DPR")
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(chooser)
}

private fun dprReviewStatusTone(status: String): CosStatusTone = when (status) {
    DprLifecycleRepository.STATUS_APPROVED -> CosStatusTone.SUCCESS
    DprLifecycleRepository.STATUS_IN_REVIEW -> CosStatusTone.PRIMARY
    DprLifecycleRepository.STATUS_REJECTED -> CosStatusTone.ERROR
    DprLifecycleRepository.STATUS_VOID -> CosStatusTone.ERROR
    DprLifecycleRepository.STATUS_DRAFT -> CosStatusTone.WARNING
    else -> CosStatusTone.NEUTRAL
}

private fun dprReviewSyncTone(state: String): CosStatusTone = when (state) {
    DprSyncState.SYNCED -> CosStatusTone.SUCCESS
    DprSyncState.SYNCING -> CosStatusTone.PRIMARY
    DprSyncState.WAITING_FOR_NETWORK -> CosStatusTone.WARNING
    DprSyncState.NEEDS_ATTENTION -> CosStatusTone.ERROR
    else -> CosStatusTone.NEUTRAL
}

private fun dprReviewSyncLabel(state: String): String = when (state) {
    DprSyncState.SAVED_ON_DEVICE -> "Saved"
    DprSyncState.WAITING_FOR_NETWORK -> "Offline"
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
