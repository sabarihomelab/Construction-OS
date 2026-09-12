package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface DprPhotoDao {
    @Query(
        """
        SELECT * FROM dpr_photos
        WHERE report_id = :reportId
        ORDER BY created_at, client_photo_id
        """,
    )
    fun observeReportPhotos(reportId: String): Flow<List<DprPhotoEntity>>

    @Query("SELECT * FROM dpr_photos WHERE client_photo_id = :clientPhotoId LIMIT 1")
    suspend fun photo(clientPhotoId: String): DprPhotoEntity?

    @Query("SELECT * FROM dpr_photos WHERE server_asset_id = :assetId LIMIT 1")
    suspend fun photoByServerAssetId(assetId: String): DprPhotoEntity?

    @Query(
        """
        SELECT * FROM dpr_photos
        WHERE state IN ('saved_on_device', 'waiting_for_network', 'uploading')
        ORDER BY created_at, client_photo_id
        LIMIT :limit
        """,
    )
    suspend fun pendingPhotos(limit: Int = 20): List<DprPhotoEntity>

    @Upsert
    suspend fun upsert(photo: DprPhotoEntity)

    @Upsert
    suspend fun upsertAll(photos: List<DprPhotoEntity>)

    @Query(
        """
        UPDATE dpr_photos
        SET state = :state,
            upload_session_id = :uploadSessionId,
            upload_target_url = :uploadTargetUrl,
            error_code = :errorCode,
            attempt_count = :attemptCount,
            updated_at = :updatedAt
        WHERE client_photo_id = :clientPhotoId
        """,
    )
    suspend fun updateUploadState(
        clientPhotoId: String,
        state: String,
        uploadSessionId: String?,
        uploadTargetUrl: String?,
        errorCode: String?,
        attemptCount: Int,
        updatedAt: Long,
    )

    @Query(
        """
        UPDATE dpr_photos
        SET state = :state,
            upload_session_id = :uploadSessionId,
            uploaded_bytes = :uploadedBytes,
            chunk_size_bytes = :chunkSizeBytes,
            error_code = :errorCode,
            attempt_count = :attemptCount,
            updated_at = :updatedAt
        WHERE client_photo_id = :clientPhotoId
        """,
    )
    suspend fun updateResumableState(
        clientPhotoId: String,
        state: String,
        uploadSessionId: String?,
        uploadedBytes: Long,
        chunkSizeBytes: Int,
        errorCode: String?,
        attemptCount: Int,
        updatedAt: Long,
    )

    @Query(
        """
        UPDATE dpr_photos
        SET state = 'waiting_for_network',
            upload_session_id = NULL,
            upload_target_url = NULL,
            uploaded_bytes = 0,
            chunk_size_bytes = 5242880,
            error_code = NULL,
            updated_at = :updatedAt
        WHERE client_photo_id = :clientPhotoId
        """,
    )
    suspend fun resetUploadSession(clientPhotoId: String, updatedAt: Long)

    @Query(
        """
        UPDATE dpr_photos
        SET state = 'synced',
            upload_session_id = :uploadSessionId,
            upload_target_url = NULL,
            uploaded_bytes = size_bytes,
            server_asset_id = :serverAssetId,
            server_version = :serverVersion,
            base_revision = :reportRevision,
            original_path = NULL,
            error_code = NULL,
            updated_at = :updatedAt
        WHERE client_photo_id = :clientPhotoId
        """,
    )
    suspend fun markSynced(
        clientPhotoId: String,
        uploadSessionId: String?,
        serverAssetId: String,
        serverVersion: Int,
        reportRevision: Int,
        updatedAt: Long,
    )

    @Query(
        """
        UPDATE dpr_photos
        SET state = 'needs_attention',
            error_code = :errorCode,
            updated_at = :updatedAt
        WHERE client_photo_id = :clientPhotoId
        """,
    )
    suspend fun markNeedsAttention(clientPhotoId: String, errorCode: String?, updatedAt: Long)

    @Query("DELETE FROM dpr_photos WHERE client_photo_id = :clientPhotoId")
    suspend fun delete(clientPhotoId: String)
}
