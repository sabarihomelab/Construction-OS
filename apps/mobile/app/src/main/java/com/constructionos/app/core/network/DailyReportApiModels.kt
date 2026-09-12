package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName

data class DailyReportResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("report_date") val reportDate: String,
    @SerializedName("shift_code") val shiftCode: String,
    val status: String,
    val revision: Int,
    @SerializedName("prepared_by_membership_id") val preparedByMembershipId: String,
    @SerializedName("weather_condition") val weatherCondition: String? = null,
    @SerializedName("temperature_low") val temperatureLow: String? = null,
    @SerializedName("temperature_high") val temperatureHigh: String? = null,
    @SerializedName("temperature_unit") val temperatureUnit: String? = null,
    val notes: String? = null,
    @SerializedName("workflow_instance_id") val workflowInstanceId: String? = null,
    @SerializedName("submitted_at") val submittedAt: String? = null,
    @SerializedName("approved_at") val approvedAt: String? = null,
    @SerializedName("rejected_at") val rejectedAt: String? = null,
    @SerializedName("voided_at") val voidedAt: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
)

data class DailyReportCreateRequest(
    @SerializedName("report_date") val reportDate: String,
    @SerializedName("shift_code") val shiftCode: String = "day",
    @SerializedName("weather_condition") val weatherCondition: String? = null,
    @SerializedName("temperature_low") val temperatureLow: String? = null,
    @SerializedName("temperature_high") val temperatureHigh: String? = null,
    @SerializedName("temperature_unit") val temperatureUnit: String? = null,
    val notes: String? = null,
)

data class DailyReportUpdateRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    @SerializedName("shift_code") val shiftCode: String? = null,
    @SerializedName("weather_condition") val weatherCondition: String? = null,
    @SerializedName("temperature_low") val temperatureLow: String? = null,
    @SerializedName("temperature_high") val temperatureHigh: String? = null,
    @SerializedName("temperature_unit") val temperatureUnit: String? = null,
    val notes: String? = null,
    val reason: String? = null,
)

data class DailyReportVersionActionRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    val reason: String? = null,
)

data class DprWorkProgressWriteRequest(
    @SerializedName("wbs_code_id") val wbsCodeId: String? = null,
    @SerializedName("boq_item_id") val boqItemId: String? = null,
    val description: String,
    val location: String? = null,
    val quantity: String? = null,
    @SerializedName("unit_code") val unitCode: String? = null,
    @SerializedName("progress_percent") val progressPercent: String? = null,
    @SerializedName("source_type") val sourceType: String = "manual",
    @SerializedName("source_id") val sourceId: String? = null,
    @SerializedName("source_revision") val sourceRevision: Int? = null,
    val remarks: String? = null,
)

data class DprWorkProgressReplaceRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    val rows: List<DprWorkProgressWriteRequest>,
    val reason: String? = null,
)

data class DprWorkProgressResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("daily_report_id") val dailyReportId: String,
    @SerializedName("wbs_code_id") val wbsCodeId: String? = null,
    @SerializedName("boq_item_id") val boqItemId: String? = null,
    val description: String,
    val location: String? = null,
    val quantity: String? = null,
    @SerializedName("unit_code") val unitCode: String? = null,
    @SerializedName("progress_percent") val progressPercent: String? = null,
    @SerializedName("source_type") val sourceType: String,
    @SerializedName("source_id") val sourceId: String? = null,
    @SerializedName("source_revision") val sourceRevision: Int? = null,
    val remarks: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
)

data class DprWorkProgressWbsReferenceResponse(
    val id: String,
    val code: String,
    val name: String,
    val kind: String,
    @SerializedName("parent_id") val parentId: String? = null,
)

data class DprWorkProgressBoqReferenceResponse(
    val id: String,
    @SerializedName("boq_id") val boqId: String,
    @SerializedName("boq_code") val boqCode: String,
    @SerializedName("boq_name") val boqName: String,
    @SerializedName("wbs_code_id") val wbsCodeId: String? = null,
    @SerializedName("item_code") val itemCode: String,
    val description: String,
    @SerializedName("unit_code") val unitCode: String,
)

data class DprWorkProgressReferenceResponse(
    @SerializedName("wbs_codes") val wbsCodes: List<DprWorkProgressWbsReferenceResponse> = emptyList(),
    @SerializedName("boq_items") val boqItems: List<DprWorkProgressBoqReferenceResponse> = emptyList(),
)

data class DailyReportOfflineMutationRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("client_mutation_id") val clientMutationId: String,
    @SerializedName("entity_id") val entityId: String,
    val operation: String,
    @SerializedName("base_revision") val baseRevision: Int? = null,
    val create: DailyReportCreateRequest? = null,
    val update: DailyReportUpdateRequest? = null,
    @SerializedName("work_progress") val workProgress: DprWorkProgressReplaceRequest? = null,
    val action: DailyReportVersionActionRequest? = null,
)

data class DailyReportOfflineMutationResponse(
    @SerializedName("client_mutation_id") val clientMutationId: String,
    @SerializedName("entity_id") val entityId: String,
    val status: String,
    val replayed: Boolean,
    @SerializedName("server_revision") val serverRevision: Int? = null,
    val result: Map<String, Any?> = emptyMap(),
    @SerializedName("error_code") val errorCode: String? = null,
)
