package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "dpr_photos",
    indices = [
        Index(value = ["report_id", "created_at"]),
        Index(value = ["project_id", "state"]),
        Index(value = ["server_asset_id"], unique = true),
    ],
)
data class DprPhotoEntity(
    @PrimaryKey
    @ColumnInfo(name = "client_photo_id") val clientPhotoId: String,
    @ColumnInfo(name = "report_id") val reportId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "original_path") val originalPath: String?,
    @ColumnInfo(name = "thumbnail_path") val thumbnailPath: String?,
    val filename: String,
    @ColumnInfo(name = "content_type") val contentType: String?,
    @ColumnInfo(name = "size_bytes") val sizeBytes: Long,
    val sha256: String?,
    val caption: String?,
    @ColumnInfo(name = "captured_at") val capturedAt: String?,
    @ColumnInfo(name = "upload_session_id") val uploadSessionId: String?,
    @ColumnInfo(name = "upload_target_url") val uploadTargetUrl: String?,
    @ColumnInfo(name = "uploaded_bytes") val uploadedBytes: Long,
    @ColumnInfo(name = "chunk_size_bytes") val chunkSizeBytes: Int,
    @ColumnInfo(name = "server_asset_id") val serverAssetId: String?,
    @ColumnInfo(name = "server_version") val serverVersion: Int?,
    @ColumnInfo(name = "base_revision") val baseRevision: Int,
    val state: String,
    @ColumnInfo(name = "error_code") val errorCode: String?,
    @ColumnInfo(name = "attempt_count") val attemptCount: Int,
    @ColumnInfo(name = "created_at") val createdAt: Long,
    @ColumnInfo(name = "updated_at") val updatedAt: Long,
)

object DprPhotoState {
    const val SAVED_ON_DEVICE = "saved_on_device"
    const val WAITING_FOR_NETWORK = "waiting_for_network"
    const val UPLOADING = "uploading"
    const val SYNCED = "synced"
    const val NEEDS_ATTENTION = "needs_attention"
}
