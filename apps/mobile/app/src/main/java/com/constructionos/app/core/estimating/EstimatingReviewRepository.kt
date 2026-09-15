package com.constructionos.app.core.estimating

import com.constructionos.app.core.network.BudgetSummaryResponse
import com.constructionos.app.core.network.EstimateSummaryResponse
import com.constructionos.app.core.network.EstimatingApi
import com.constructionos.app.core.network.EstimatingRevisionActionRequest

/**
 * Estimating and budget approval are intentionally online-only.
 * Financial/governed state is never treated as an offline-authoritative cache.
 */
class EstimatingReviewRepository(
    private val api: EstimatingApi,
) {
    suspend fun snapshot(
        projectId: String,
        canViewEstimates: Boolean,
        canViewBudgets: Boolean,
    ): EstimatingReviewSnapshot = EstimatingReviewSnapshot(
        estimates = if (canViewEstimates) api.estimates(projectId) else emptyList(),
        budgets = if (canViewBudgets) api.budgets(projectId) else emptyList(),
    )

    suspend fun approveEstimate(
        projectId: String,
        estimateId: String,
        expectedRevision: Int,
    ): EstimateSummaryResponse = api.approveEstimate(
        projectId = projectId,
        estimateId = estimateId,
        request = EstimatingRevisionActionRequest(expectedRevision = expectedRevision),
    )

    suspend fun approveBudget(
        projectId: String,
        budgetId: String,
        expectedRevision: Int,
    ): BudgetSummaryResponse = api.approveBudget(
        projectId = projectId,
        budgetId = budgetId,
        request = EstimatingRevisionActionRequest(expectedRevision = expectedRevision),
    )
}

data class EstimatingReviewSnapshot(
    val estimates: List<EstimateSummaryResponse>,
    val budgets: List<BudgetSummaryResponse>,
)
