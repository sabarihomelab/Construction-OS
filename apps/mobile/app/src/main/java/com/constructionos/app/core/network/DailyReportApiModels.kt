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

data class DailyReportOfflineMutationRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("client_mutation_id") val clientMutationId: String,
    @SerializedName("entity_id") val entityId: String,
    val operation: String,
    @SerializedName("base_revision") val baseRevision: Int? = null,
    val create: DailyReportCreateRequest? = null,
    val update: DailyReportUpdateRequest? = null,
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
