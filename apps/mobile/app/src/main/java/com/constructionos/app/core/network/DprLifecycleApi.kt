package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Streaming

interface DprLifecycleApi {
    @POST("projects/{projectId}/daily-reports/{reportId}/approve")
    suspend fun approve(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Body request: DailyReportVersionActionRequest,
    ): DailyReportResponse

    @POST("projects/{projectId}/daily-reports/{reportId}/reject")
    suspend fun reject(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Body request: DailyReportRequiredReasonActionRequest,
    ): DailyReportResponse

    @POST("projects/{projectId}/daily-reports/{reportId}/reopen")
    suspend fun reopen(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Body request: DailyReportVersionActionRequest,
    ): DailyReportResponse

    @POST("projects/{projectId}/daily-reports/{reportId}/void")
    suspend fun voidReport(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Body request: DailyReportRequiredReasonActionRequest,
    ): DailyReportResponse

    @GET("projects/{projectId}/daily-reports/{reportId}/report-generation")
    suspend fun reportGeneration(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
    ): DprGenerationStatusResponse

    @Streaming
    @GET("projects/{projectId}/daily-reports/{reportId}/render-history/{renderId}/download")
    suspend fun downloadIssuedReport(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("renderId") renderId: String,
    ): Response<ResponseBody>
}

data class DailyReportRequiredReasonActionRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    val reason: String,
)

data class DprGenerationStatusResponse(
    @SerializedName("report_id") val reportId: String,
    @SerializedName("source_revision") val sourceRevision: Int,
    @SerializedName("report_status") val reportStatus: String,
    @SerializedName("generation_state") val generationState: String,
    @SerializedName("output_format") val outputFormat: String,
    @SerializedName("job_id") val jobId: String? = null,
    @SerializedName("job_status") val jobStatus: String? = null,
    @SerializedName("failure_code") val failureCode: String? = null,
    @SerializedName("render_id") val renderId: String? = null,
    val filename: String? = null,
    @SerializedName("issued_at") val issuedAt: String? = null,
    @SerializedName("download_path") val downloadPath: String? = null,
)
