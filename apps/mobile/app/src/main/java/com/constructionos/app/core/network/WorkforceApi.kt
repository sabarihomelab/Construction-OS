package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Path

interface WorkforceApi {
    @GET("workforce/workers")
    suspend fun workers(): List<WorkforceWorkerResponse>

    @GET("workforce/crews")
    suspend fun crews(): List<WorkforceCrewResponse>

    @GET("projects/{projectId}/workforce/assignments")
    suspend fun assignments(@Path("projectId") projectId: String): List<WorkforceAssignmentResponse>
}

data class WorkforceWorkerResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("worker_number") val workerNumber: String,
    @SerializedName("first_name") val firstName: String,
    @SerializedName("last_name") val lastName: String,
    @SerializedName("preferred_name") val preferredName: String?,
    @SerializedName("job_title") val jobTitle: String?,
    val trade: String?,
    val status: String,
    val revision: Int,
)

data class WorkforceCrewResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    val name: String,
    @SerializedName("supervisor_worker_id") val supervisorWorkerId: String?,
    val status: String,
    val revision: Int,
)

data class WorkforceAssignmentResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("worker_id") val workerId: String,
    @SerializedName("crew_id") val crewId: String?,
    @SerializedName("employer_party_id") val employerPartyId: String?,
    @SerializedName("engagement_type") val engagementType: String?,
    val status: String,
    @SerializedName("project_role") val projectRole: String?,
    val trade: String?,
    @SerializedName("default_cost_code") val defaultCostCode: String?,
    @SerializedName("start_date") val startDate: String?,
    @SerializedName("end_date") val endDate: String?,
    val revision: Int,
)
