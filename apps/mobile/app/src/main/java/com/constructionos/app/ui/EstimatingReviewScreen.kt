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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.estimating.EstimatingReviewRepository
import com.constructionos.app.core.estimating.EstimatingReviewSnapshot
import com.constructionos.app.core.network.BudgetSummaryResponse
import com.constructionos.app.core.network.EstimateSummaryResponse
import kotlinx.coroutines.launch
import retrofit2.HttpException

private enum class ApprovalTargetKind {
    ESTIMATE,
    BUDGET,
}

private data class PendingApproval(
    val kind: ApprovalTargetKind,
    val id: String,
    val code: String,
    val name: String,
    val revision: Int,
)

@Composable
fun EstimatingReviewScreen(
    project: ProjectEntity,
    repository: EstimatingReviewRepository,
    canViewEstimates: Boolean,
    canApproveEstimates: Boolean,
    canViewBudgets: Boolean,
    canApproveBudgets: Boolean,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val scope = rememberCoroutineScope()
    var snapshot by remember(project.id) { mutableStateOf<EstimatingReviewSnapshot?>(null) }
    var loading by remember(project.id) { mutableStateOf(true) }
    var busy by remember(project.id) { mutableStateOf(false) }
    var pendingApproval by remember(project.id) { mutableStateOf<PendingApproval?>(null) }
    var error by remember(project.id) { mutableStateOf<String?>(null) }
    var message by remember(project.id) { mutableStateOf<String?>(null) }

    suspend fun reload() {
        loading = snapshot == null
        error = null
        runCatching {
            repository.snapshot(
                projectId = project.id,
                canViewEstimates = canViewEstimates,
                canViewBudgets = canViewBudgets,
            )
        }.onSuccess { snapshot = it }
            .onFailure { error = estimatingReviewError(it) }
        loading = false
    }

    LaunchedEffect(project.id, repository, canViewEstimates, canViewBudgets) {
        reload()
    }

    if (loading && snapshot == null) {
        Column(
            modifier = modifier.fillMaxSize(),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            CircularProgressIndicator()
            Text("Loading estimating review…", modifier = Modifier.padding(top = 12.dp))
        }
        return
    }

    val data = snapshot
    if (data == null) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(error ?: "Unable to load estimating data.", color = MaterialTheme.colorScheme.error)
            Button(onClick = { scope.launch { reload() } }, modifier = Modifier.padding(top = 12.dp)) {
                Text("Retry")
            }
            TextButton(onClick = onBack) { Text("Back") }
        }
        return
    }

    LazyColumn(modifier = modifier.fillMaxSize()) {
        item {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                TextButton(onClick = onBack) { Text("Back") }
                Text("Estimating & Budget", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "${project.number} · ${project.name}",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 3.dp),
                )
                Text(
                    "Online management review only. Financial approval remains server-authoritative and is never queued offline.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 6.dp),
                )
                OutlinedButton(
                    onClick = { scope.launch { reload() } },
                    enabled = !busy,
                    modifier = Modifier.padding(top = 10.dp),
                ) {
                    Text("Refresh")
                }
            }
            HorizontalDivider()
        }

        if (error != null) {
            item {
                Text(
                    error!!,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(16.dp),
                )
                HorizontalDivider()
            }
        }
        if (message != null) {
            item {
                Text(
                    message!!,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(16.dp),
                )
                HorizontalDivider()
            }
        }

        pendingApproval?.let { pending ->
            item {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Confirm approval", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Approve ${pending.code} · ${pending.name}? This changes governed financial state on the company server.",
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(top = 5.dp),
                    )
                    Row(
                        modifier = Modifier.padding(top = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Button(
                            enabled = !busy,
                            onClick = {
                                scope.launch {
                                    busy = true
                                    error = null
                                    message = null
                                    runCatching {
                                        when (pending.kind) {
                                            ApprovalTargetKind.ESTIMATE -> repository.approveEstimate(
                                                projectId = project.id,
                                                estimateId = pending.id,
                                                expectedRevision = pending.revision,
                                            )
                                            ApprovalTargetKind.BUDGET -> repository.approveBudget(
                                                projectId = project.id,
                                                budgetId = pending.id,
                                                expectedRevision = pending.revision,
                                            )
                                        }
                                    }.onSuccess {
                                        message = "${pending.code} approved."
                                        pendingApproval = null
                                        reload()
                                    }.onFailure { error = estimatingReviewError(it) }
                                    busy = false
                                }
                            },
                        ) {
                            Text(if (busy) "Approving…" else "Confirm approval")
                        }
                        OutlinedButton(
                            onClick = { pendingApproval = null },
                            enabled = !busy,
                        ) {
                            Text("Cancel")
                        }
                    }
                }
                HorizontalDivider()
            }
        }

        if (canViewEstimates) {
            item {
                ReviewSectionTitle("Estimates", "${data.estimates.size} records")
            }
            if (data.estimates.isEmpty()) {
                item { ReviewEmptyRow("No estimates are available for this project.") }
            } else {
                items(data.estimates, key = { "estimate-${it.id}" }) { estimate ->
                    EstimateReviewRow(
                        estimate = estimate,
                        canApprove = canApproveEstimates && estimate.status == "submitted",
                        busy = busy,
                        onApprove = {
                            pendingApproval = PendingApproval(
                                kind = ApprovalTargetKind.ESTIMATE,
                                id = estimate.id,
                                code = estimate.code,
                                name = estimate.name,
                                revision = estimate.revision,
                            )
                            error = null
                            message = null
                        },
                    )
                    HorizontalDivider()
                }
            }
        }

        if (canViewBudgets) {
            item {
                ReviewSectionTitle("Budgets", "${data.budgets.size} records")
            }
            if (data.budgets.isEmpty()) {
                item { ReviewEmptyRow("No budgets are available for this project.") }
            } else {
                items(data.budgets, key = { "budget-${it.id}" }) { budget ->
                    BudgetReviewRow(
                        budget = budget,
                        canApprove = canApproveBudgets && budget.status == "draft",
                        busy = busy,
                        onApprove = {
                            pendingApproval = PendingApproval(
                                kind = ApprovalTargetKind.BUDGET,
                                id = budget.id,
                                code = budget.code,
                                name = budget.name,
                                revision = budget.revision,
                            )
                            error = null
                            message = null
                        },
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun ReviewSectionTitle(title: String, detail: String) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge)
        Text(detail, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 2.dp))
    }
    HorizontalDivider()
}

@Composable
private fun ReviewEmptyRow(message: String) {
    Text(message, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
    HorizontalDivider()
}

@Composable
private fun EstimateReviewRow(
    estimate: EstimateSummaryResponse,
    canApprove: Boolean,
    busy: Boolean,
    onApprove: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp)) {
        Text("${estimate.code} · ${estimate.name}", style = MaterialTheme.typography.titleMedium)
        Text(
            "${estimate.status.replaceFirstChar { it.uppercase() }} · ${estimate.currencyCode} · revision ${estimate.revision}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 3.dp),
        )
        estimate.description?.takeIf { it.isNotBlank() }?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 3.dp))
        }
        if (canApprove) {
            TextButton(onClick = onApprove, enabled = !busy) { Text("Review approval") }
        }
    }
}

@Composable
private fun BudgetReviewRow(
    budget: BudgetSummaryResponse,
    canApprove: Boolean,
    busy: Boolean,
    onApprove: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp)) {
        Text("${budget.code} · ${budget.name}", style = MaterialTheme.typography.titleMedium)
        Text(
            "${budget.status.replaceFirstChar { it.uppercase() }} · ${budget.currencyCode} · revision ${budget.revision}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 3.dp),
        )
        if (canApprove) {
            TextButton(onClick = onApprove, enabled = !busy) { Text("Review approval") }
        }
    }
}

private fun estimatingReviewError(error: Throwable): String = when (error) {
    is HttpException -> when (error.code()) {
        401 -> "Your session expired. Sign in again before reviewing financial records."
        403 -> "Your estimating or budget permission changed. Refresh your access before retrying."
        404 -> "This estimate or budget is no longer available. Refresh the list."
        409 -> "The record changed on the server. Refresh before approving it."
        422 -> "The server rejected this approval because its business requirements are not satisfied."
        else -> "The company server could not complete this estimating request."
    }
    else -> "Estimating review requires a live connection to the company server."
}
