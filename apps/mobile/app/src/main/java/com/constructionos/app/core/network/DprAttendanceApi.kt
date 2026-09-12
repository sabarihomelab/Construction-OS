package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Path

interface DprAttendanceApi {
    @GET("projects/{projectId}/workforce/attendance")
    suspend fun attendanceRegisters(
        @Path("projectId") projectId: String,
    ): List<AttendanceRegisterResponse>

    @GET("projects/{projectId}/workforce/attendance/{registerId}/dpr-summary")
    suspend fun dprSummary(
        @Path("projectId") projectId: String,
        @Path("registerId") registerId: String,
    ): AttendanceDprSummaryResponse
}

data class AttendanceDprSummaryResponse(
    @SerializedName("register_id") val registerId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("attendance_date") val attendanceDate: String,
    @SerializedName("shift_code") val shiftCode: String,
    val rows: List<AttendanceDprSummaryRowResponse> = emptyList(),
)

data class AttendanceDprSummaryRowResponse(
    @SerializedName("employer_party_id") val employerPartyId: String? = null,
    @SerializedName("crew_id") val crewId: String? = null,
    val trade: String? = null,
    @SerializedName("worker_count") val workerCount: Int,
    @SerializedName("present_count") val presentCount: Int,
    @SerializedName("absent_count") val absentCount: Int,
    @SerializedName("regular_hours") val regularHours: String,
    @SerializedName("overtime_hours") val overtimeHours: String,
)
