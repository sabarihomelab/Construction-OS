package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Url

interface DprPhotoApi {
    @GET("projects/{projectId}/daily-reports/{reportId}/photos")
    suspend fun photos(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
    ): List<DprPhotoResponse>

    @POST("projects/{projectId}/daily-reports/{reportId}/photos/uploads")
    suspend fun startUpload(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Body request: DprPhotoUploadStartRequest,
    ): DprPhotoUploadSessionResponse

    @PUT
    suspend fun uploadContent(
        @Url relativeUrl: String,
        @Body body: RequestBody,
    ): Response<Unit>

    @POST("projects/{projectId}/daily-reports/{reportId}/photos/uploads/{uploadId}/finalize")
    suspend fun finalizeUpload(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("uploadId") uploadId: String,
        @Body request: DprPhotoFinalizeRequest,
    ): DprPhotoResponse

    @DELETE("projects/{projectId}/daily-reports/{reportId}/photos/uploads/{uploadId}")
    suspend fun cancelUpload(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("uploadId") uploadId: String,
    ): Response<Unit>

    @DELETE("projects/{projectId}/daily-reports/{reportId}/photos/{assetId}")
    suspend fun deletePhoto(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("assetId") assetId: String,
        @Query("expected_revision") expectedRevision: Int,
    ): DprPhotoChangeResponse
}

data class DprPhotoUploadStartRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    @SerializedName("client_photo_id") val clientPhotoId: String,
    @SerializedName("original_filename") val originalFilename: String,
    @SerializedName("content_type") val contentType: String,
    @SerializedName("size_bytes") val sizeBytes: Long,
    val sha256: String,
)

data class DprPhotoUploadTargetResponse(
    val url: String,
    val method: String,
    val headers: Map<String, String> = emptyMap(),
    @SerializedName("expires_at") val expiresAt: String,
)

data class DprPhotoUploadSessionResponse(
    @SerializedName("upload_id") val uploadId: String,
    @SerializedName("client_photo_id") val clientPhotoId: String,
    val target: DprPhotoUploadTargetResponse,
)

data class DprPhotoFinalizeRequest(
    @SerializedName("expected_revision") val expectedRevision: Int,
    @SerializedName("client_photo_id") val clientPhotoId: String,
    val caption: String? = null,
    @SerializedName("captured_at") val capturedAt: String? = null,
)

data class DprPhotoResponse(
    @SerializedName("asset_id") val assetId: String,
    val version: Int,
    val filename: String,
    @SerializedName("content_type") val contentType: String? = null,
    @SerializedName("size_bytes") val sizeBytes: Long,
    @SerializedName("relation_type") val relationType: String,
    @SerializedName("client_photo_id") val clientPhotoId: String? = null,
    val caption: String? = null,
    @SerializedName("captured_at") val capturedAt: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("report_revision") val reportRevision: Int,
)

data class DprPhotoChangeResponse(
    @SerializedName("report_revision") val reportRevision: Int,
)
