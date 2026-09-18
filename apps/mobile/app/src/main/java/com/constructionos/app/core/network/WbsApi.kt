package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Path

interface WbsApi {
    @GET("projects/{projectId}/commercial/wbs/tree")
    suspend fun wbsTree(@Path("projectId") projectId: String): List<WbsTreeResponse>
}

data class WbsTreeResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("parent_id") val parentId: String?,
    val code: String,
    val name: String,
    val kind: String,
    val status: String,
    val description: String? = null,
    val revision: Int,
    val depth: Int,
    @SerializedName("path_codes") val pathCodes: List<String> = emptyList(),
    @SerializedName("child_count") val childCount: Int,
)
