package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName

data class AttendanceRosterResponse(
    @SerializedName("assignment_id") val assignmentId: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("worker_id") val workerId: String,
    @SerializedName("worker_number") val workerNumber: String,
    @SerializedName("worker_name") val workerName: String,
    @SerializedName("crew_id") val crewId: String? = null,
    @SerializedName("employer_party_id") val employerPartyId: String? = null,
    @SerializedName("engagement_type") val engagementType: String? = null,
    val status: String,
    @SerializedName("project_role") val projectRole: String? = null,
    val trade: String? = null,
    @SerializedName("default_cost_code") val defaultCostCode: String? = null,
    @SerializedName("start_date") val startDate: String? = null,
    @SerializedName("end_date") val endDate: String? = null,
    val revision: Int,
)

data class AttendanceRegisterResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("attendance_date") val attendanceDate: String,
    @SerializedName("shift_code") val shiftCode: String,
    val status: String,
    val revision: Int,
    @SerializedName("prepared_by_membership_id") val preparedByMembershipId: String,
    @SerializedName("approved_by_membership_id") val approvedByMembershipId: String? = null,
    @SerializedName("workflow_instance_id") val workflowInstanceId: String? = null,
    @SerializedName("configuration_context") val configurationContext: Map<String, Any?> = emptyMap(),
    val notes: String? = null,
    @SerializedName("submitted_at") val submittedAt: String? = null,
    @SerializedName("approved_at") val approvedAt: String? = null,
    @SerializedName("rejected_at") val rejectedAt: String? = null,
    @SerializedName("voided_at") val voidedAt: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
)

data class AttendanceEntryResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("register_id") val registerId: String,
    @SerializedName("assignment_id") val assignmentId: String,
    @SerializedName("worker_id") val workerId: String,
    @SerializedName("crew_id") val crewId: String? = null,
    @SerializedName("employer_party_id") val employerPartyId: String? = null,
    @SerializedName("wbs_code_id") val wbsCodeId: String? = null,
    @SerializedName("engagement_type") val engagementType: String? = null,
    val trade: String? = null,
    @SerializedName("mark_status") val markStatus: String,
    @SerializedName("regular_hours") val regularHours: String,
    @SerializedName("overtime_hours") val overtimeHours: String,
    val location: String? = null,
    val notes: String? = null,
    @SerializedName("source_type") val sourceType: String,
    @SerializedName("source_id") val sourceId: String? = null,
    @SerializedName("context_snapshot") val contextSnapshot: Map<String, Any?> = emptyMap(),
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
)

data class AttendanceRegisterDetailResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("attendance_date") val attendanceDate: String,
    @SerializedName("shift_code") val shiftCode: String,
    val status: String,
    val revision: Int,
    @SerializedName("prepared_by_membership_id") val preparedByMembershipId: String,
    @SerializedName("approved_by_membership_id") val approvedByMembershipId: String? = null,
    @SerializedName("workflow_instance_id") val workflowInstanceId: String? = null,
    @SerializedName("configuration_context") val configurationContext: Map<String, Any?> = emptyMap(),
    val notes: String? = null,
    @SerializedName("submitted_at") val submittedAt: String? = null,
    @SerializedName("approved_at") val approvedAt: String? = null,
    @SerializedName("rejected_at") val rejectedAt: String? = null,
    @SerializedName("voided_at") val voidedAt: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
    val entries: List<AttendanceEntryResponse> = emptyList(),
)

data class AttendanceRegisterCreateRequest(
    @SerializedName("attendance_date") val attendanceDate: String,
    @SerializedName("shift_code") val shiftCode: String = "day",
    val notes: String? = null,
    @SerializedName("populate_active_workers") val populateActiveWorkers: Boolean = true,
)

data class AttendanceEntryWriteRequest(
    @SerializedName("assignment_id") val assignmentId: String,
    @SerializedName("mark_status") val markStatus: String,
    @SerializedName("regular_hours") val regularHours: String = "0",
    @SerializedName("overtime_hours") val overtimeHours: String = "0",
    @SerializedName("wbs_code_id") val wbsCodeId: String? = null,
    val location: String? = null,
    val notes: String? = null,
)

data class AttendanceEntriesWriteRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    val entries: List<AttendanceEntryWriteRequest>,
    val reason: String? = null,
)

data class AttendanceVersionActionRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    val reason: String? = null,
)

data class AttendanceOfflineMutationRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("client_mutation_id") val clientMutationId: String,
    @SerializedName("entity_id") val entityId: String,
    val operation: String,
    @SerializedName("base_revision") val baseRevision: Int? = null,
    val create: AttendanceRegisterCreateRequest? = null,
    val entries: AttendanceEntriesWriteRequest? = null,
    val action: AttendanceVersionActionRequest? = null,
)

data class AttendanceOfflineMutationResponse(
    @SerializedName("client_mutation_id") val clientMutationId: String,
    @SerializedName("entity_id") val entityId: String,
    val status: String,
    val replayed: Boolean,
    @SerializedName("server_revision") val serverRevision: Int? = null,
    val result: Map<String, Any?> = emptyMap(),
    @SerializedName("error_code") val errorCode: String? = null,
)
