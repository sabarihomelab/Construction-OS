package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
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

    @POST("projects/{projectId}/daily-reports/{reportId}/photos/resumable")
    suspend fun startResumableUpload(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Body request: DprPhotoUploadStartRequest,
    ): DprPhotoResumableSessionResponse

    @GET("projects/{projectId}/daily-reports/{reportId}/photos/uploads/{uploadId}/status")
    suspend fun resumableStatus(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("uploadId") uploadId: String,
    ): DprPhotoResumableSessionResponse

    @PATCH("projects/{projectId}/daily-reports/{reportId}/photos/uploads/{uploadId}/chunk")
    suspend fun uploadChunk(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("uploadId") uploadId: String,
        @Header("Upload-Offset") uploadOffset: Long,
        @Header("X-Chunk-SHA256") chunkSha256: String,
        @Body body: RequestBody,
    ): DprPhotoChunkResponse

    @POST(
        "projects/{projectId}/daily-reports/{reportId}/photos/uploads/" +
            "{uploadId}/resumable-finalize",
    )
    suspend fun finalizeResumableUpload(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("uploadId") uploadId: String,
        @Body request: DprPhotoFinalizeRequest,
    ): DprPhotoResponse

    @DELETE(
        "projects/{projectId}/daily-reports/{reportId}/photos/uploads/" +
            "{uploadId}/resumable",
    )
    suspend fun cancelResumableUpload(
        @Path("projectId") projectId: String,
        @Path("reportId") reportId: String,
        @Path("uploadId") uploadId: String,
    ): Response<Unit>

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

data class DprPhotoResumableSessionResponse(
    @SerializedName("upload_id") val uploadId: String,
    @SerializedName("client_photo_id") val clientPhotoId: String,
    val status: String,
    @SerializedName("uploaded_bytes") val uploadedBytes: Long,
    @SerializedName("size_bytes") val sizeBytes: Long,
    @SerializedName("chunk_size_bytes") val chunkSizeBytes: Int,
    @SerializedName("content_already_present") val contentAlreadyPresent: Boolean,
    @SerializedName("expires_at") val expiresAt: String,
    @SerializedName("finalized_asset_id") val finalizedAssetId: String? = null,
    @SerializedName("finalized_version") val finalizedVersion: Int? = null,
)

data class DprPhotoChunkResponse(
    @SerializedName("upload_id") val uploadId: String,
    val status: String,
    @SerializedName("uploaded_bytes") val uploadedBytes: Long,
    @SerializedName("size_bytes") val sizeBytes: Long,
    val complete: Boolean,
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
