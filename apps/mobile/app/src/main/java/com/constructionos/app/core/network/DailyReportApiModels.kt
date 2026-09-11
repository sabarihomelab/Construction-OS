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
