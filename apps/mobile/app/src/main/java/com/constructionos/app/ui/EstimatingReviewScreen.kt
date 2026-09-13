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
import androidx.compose.material.icons.rounded.Calculate
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.estimating.EstimatingReviewRepository
import com.constructionos.app.core.estimating.EstimatingReviewSnapshot
import com.constructionos.app.core.network.BudgetSummaryResponse
import com.constructionos.app.core.network.EstimateSummaryResponse
import com.constructionos.app.ui.design.CosSectionHeader
import com.constructionos.app.ui.design.CosStatusPill
import com.constructionos.app.ui.design.CosStatusTone
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
            Icon(Icons.Rounded.Calculate, contentDescription = null, modifier = Modifier.size(42.dp))
            Text(
                error ?: "Unable to load estimating data.",
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 12.dp),
            )
            Button(onClick = { scope.launch { reload() } }, modifier = Modifier.padding(top = 12.dp)) {
                Text("Retry")
            }
            TextButton(onClick = onBack) { Text("Back") }
        }
        return
    }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = 10.dp,
            bottom = 18.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.Rounded.ArrowBack, contentDescription = "Back")
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text("Estimating & Budget", style = MaterialTheme.typography.headlineSmall)
                    Text(
                        "${project.number} · ${project.name}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                IconButton(onClick = { scope.launch { reload() } }, enabled = !busy) {
                    Icon(Icons.Rounded.Refresh, contentDescription = "Refresh")
                }
            }
        }

        item {
            Surface(
                shape = MaterialTheme.shapes.large,
                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    "Online management review only. Financial approval remains server-authoritative and is never queued offline.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(12.dp),
                )
            }
        }

        error?.let { currentError ->
            item {
                Surface(
                    color = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer,
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(currentError, modifier = Modifier.padding(12.dp))
                }
            }
        }

        message?.let { currentMessage ->
            item {
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(currentMessage, modifier = Modifier.padding(12.dp))
                }
            }
        }

        pendingApproval?.let { pending ->
            item {
                Card(
                    shape = MaterialTheme.shapes.extraLarge,
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                    ),
                ) {
                    Column(modifier = Modifier.padding(18.dp)) {
                        Text("Confirm approval", style = MaterialTheme.typography.titleLarge)
                        Text(
                            "Approve ${pending.code} · ${pending.name}? This changes governed financial state on the company server.",
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(top = 6.dp),
                        )
                        Row(
                            modifier = Modifier.padding(top = 14.dp),
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
                }
            }
        }

        if (canViewEstimates) {
            item {
                CosSectionHeader(
                    title = "Estimates",
                    subtitle = "${data.estimates.size} records",
                )
            }
            if (data.estimates.isEmpty()) {
                item { ReviewEmptyCard("No estimates are available for this project.") }
            } else {
                items(data.estimates, key = { "estimate-${it.id}" }) { estimate ->
                    EstimateReviewCard(
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
                }
            }
        }

        if (canViewBudgets) {
            item {
                CosSectionHeader(
                    title = "Budgets",
                    subtitle = "${data.budgets.size} records",
                )
            }
            if (data.budgets.isEmpty()) {
                item { ReviewEmptyCard("No budgets are available for this project.") }
            } else {
                items(data.budgets, key = { "budget-${it.id}" }) { budget ->
                    BudgetReviewCard(
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
                }
            }
        }
    }
}

@Composable
private fun ReviewEmptyCard(message: String) {
    Card(
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Text(message, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun EstimateReviewCard(
    estimate: EstimateSummaryResponse,
    canApprove: Boolean,
    busy: Boolean,
    onApprove: () -> Unit,
) {
    FinancialReviewCard(
        code = estimate.code,
        name = estimate.name,
        status = estimate.status,
        currencyCode = estimate.currencyCode,
        revision = estimate.revision,
        description = estimate.description,
        canApprove = canApprove,
        busy = busy,
        onApprove = onApprove,
    )
}

@Composable
private fun BudgetReviewCard(
    budget: BudgetSummaryResponse,
    canApprove: Boolean,
    busy: Boolean,
    onApprove: () -> Unit,
) {
    FinancialReviewCard(
        code = budget.code,
        name = budget.name,
        status = budget.status,
        currencyCode = budget.currencyCode,
        revision = budget.revision,
        description = null,
        canApprove = canApprove,
        busy = busy,
        onApprove = onApprove,
    )
}

@Composable
private fun FinancialReviewCard(
    code: String,
    name: String,
    status: String,
    currencyCode: String,
    revision: Int,
    description: String?,
    canApprove: Boolean,
    busy: Boolean,
    onApprove: () -> Unit,
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
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    code,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                CosStatusPill(
                    text = status.replaceFirstChar { it.uppercase() },
                    tone = financialStatusTone(status),
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            Text(
                name,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 7.dp),
            )
            Row(
                modifier = Modifier.padding(top = 7.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                CosStatusPill(currencyCode)
                CosStatusPill("Revision $revision")
            }
            description?.takeIf { it.isNotBlank() }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 7.dp),
                )
            }
            if (canApprove) {
                Button(
                    onClick = onApprove,
                    enabled = !busy,
                    modifier = Modifier.padding(top = 10.dp),
                ) {
                    Text("Review approval")
                }
            }
        }
    }
}

private fun financialStatusTone(status: String): CosStatusTone = when (status.lowercase()) {
    "approved" -> CosStatusTone.SUCCESS
    "submitted", "in_review" -> CosStatusTone.PRIMARY
    "rejected" -> CosStatusTone.ERROR
    "draft" -> CosStatusTone.WARNING
    else -> CosStatusTone.NEUTRAL
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
