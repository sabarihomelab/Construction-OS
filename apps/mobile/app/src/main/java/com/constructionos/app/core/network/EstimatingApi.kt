package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface EstimatingApi {
    @GET("projects/{projectId}/estimating/estimates")
    suspend fun estimates(@Path("projectId") projectId: String): List<EstimateSummaryResponse>

    @POST("projects/{projectId}/estimating/estimates/{estimateId}/approve")
    suspend fun approveEstimate(
        @Path("projectId") projectId: String,
        @Path("estimateId") estimateId: String,
        @Body request: EstimatingRevisionActionRequest,
    ): EstimateSummaryResponse

    @GET("projects/{projectId}/estimating/budgets")
    suspend fun budgets(@Path("projectId") projectId: String): List<BudgetSummaryResponse>

    @POST("projects/{projectId}/estimating/budgets/{budgetId}/approve")
    suspend fun approveBudget(
        @Path("projectId") projectId: String,
        @Path("budgetId") budgetId: String,
        @Body request: EstimatingRevisionActionRequest,
    ): BudgetSummaryResponse
}

data class EstimateSummaryResponse(
    val id: String,
    @SerializedName("source_boq_id") val sourceBoqId: String? = null,
    val code: String,
    val name: String,
    val description: String? = null,
    @SerializedName("currency_code") val currencyCode: String,
    val status: String,
    val revision: Int,
    @SerializedName("approved_at") val approvedAt: String? = null,
)

data class BudgetSummaryResponse(
    val id: String,
    @SerializedName("estimate_id") val estimateId: String? = null,
    val code: String,
    val name: String,
    @SerializedName("currency_code") val currencyCode: String,
    val status: String,
    val revision: Int,
    @SerializedName("approved_at") val approvedAt: String? = null,
)

data class EstimatingRevisionActionRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    val reason: String? = null,
)
