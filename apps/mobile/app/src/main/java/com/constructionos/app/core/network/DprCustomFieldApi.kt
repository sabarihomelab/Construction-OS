package com.constructionos.app.core.network

import com.google.gson.JsonElement
import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Path

interface DprCustomFieldApi {
    @GET("projects/{projectId}/daily-reports/custom-fields/definitions")
    suspend fun definitions(
        @Path("projectId") projectId: String,
    ): DprCustomFieldDefinitionsResponse

    @GET("projects/{projectId}/daily-reports/{reportId}/custom-fields")
    suspend fun values(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
    ): DprCustomFieldValuesResponse
}

data class DprCustomFieldOptionResponse(
    val key: String,
    val label: String,
)

data class DprCustomFieldDefinitionResponse(
    @SerializedName("definition_id") val definitionId: String,
    val key: String,
    val label: String,
    val description: String? = null,
    @SerializedName("field_type") val fieldType: String,
    val required: Boolean,
    val editable: Boolean,
    @SerializedName("display_order") val displayOrder: Int,
    @SerializedName("default_value") val defaultValue: JsonElement? = null,
    val options: List<DprCustomFieldOptionResponse> = emptyList(),
)

data class DprCustomFieldDefinitionsResponse(
    @SerializedName("project_id") val projectId: String,
    val fields: List<DprCustomFieldDefinitionResponse> = emptyList(),
)

data class DprCustomFieldValueResponse(
    @SerializedName("definition_id") val definitionId: String,
    val value: JsonElement? = null,
)

data class DprCustomFieldValuesResponse(
    @SerializedName("report_id") val reportId: String,
    @SerializedName("report_revision") val reportRevision: Int,
    val values: List<DprCustomFieldValueResponse> = emptyList(),
)

data class DprCustomFieldValueWriteRequest(
    @SerializedName("definition_id") val definitionId: String,
    val value: JsonElement? = null,
)

data class DprCustomFieldReplaceRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    val values: List<DprCustomFieldValueWriteRequest>,
    val reason: String? = null,
)
