package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Path

interface BoqFieldApi {
    @GET("projects/{projectId}/commercial/boqs/field-reference")
    suspend fun fieldReferences(@Path("projectId") projectId: String): List<BoqFieldReferenceResponse>
}

data class BoqFieldReferenceResponse(
    @SerializedName("item_id") val itemId: String,
    @SerializedName("boq_id") val boqId: String,
    @SerializedName("boq_code") val boqCode: String,
    @SerializedName("boq_name") val boqName: String,
    @SerializedName("boq_revision") val boqRevision: Int,
    @SerializedName("wbs_code_id") val wbsCodeId: String?,
    @SerializedName("line_number") val lineNumber: Int,
    @SerializedName("item_code") val itemCode: String,
    val description: String,
    @SerializedName("unit_code") val unitCode: String,
    val quantity: String,
    @SerializedName("item_revision") val itemRevision: Int,
)
