package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprPhotoDao
import com.constructionos.app.core.database.DprPhotoEntity
import com.constructionos.app.core.database.DprPhotoState
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.network.DprPhotoApi
import com.constructionos.app.core.network.DprPhotoFinalizeRequest
import com.constructionos.app.core.network.DprPhotoResumableSessionResponse
import com.constructionos.app.core.network.DprPhotoUploadStartRequest
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile
import java.security.MessageDigest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException

class DprPhotoSyncService(
    private val api: DprPhotoApi,
    private val photoDao: DprPhotoDao,
    private val dprDao: DprDao,
    private val dprRepository: DprRepository,
) {
    suspend fun drain() {
        while (true) {
            val photo = photoDao.pendingPhotos(limit = 1).firstOrNull() ?: return
            if (photo.state == DprPhotoState.CANCEL_REQUESTED) {
                if (!cancelPhoto(photo)) return
            } else if (!syncPhoto(photo)) {
                return
            }
        }
    }

    private suspend fun cancelPhoto(photo: DprPhotoEntity): Boolean {
        val uploadId = photo.uploadSessionId
        if (uploadId == null) {
            deleteLocalPhoto(photo)
            return true
        }
        val report = dprDao.reportById(photo.reportId)
        val serverId = report?.serverId
        if (report == null || serverId == null) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "cancel_report_not_found", now())
            return false
        }
        return try {
            val response = api.cancelResumableUpload(report.projectId, serverId, uploadId)
            if (!response.isSuccessful) throw HttpException(response)
            deleteLocalPhoto(photo)
            true
        } catch (error: HttpException) {
            when {
                error.code() == 401 -> throw error
                error.code() == 408 || error.code() == 429 || error.code() in 500..599 -> throw error
                error.code() == 409 -> {
                    photoDao.markNeedsAttention(
                        photo.clientPhotoId,
                        "cancel_raced_with_finalize",
                        now(),
                    )
                    runCatching { dprRepository.refreshProject(report.projectId) }
                    false
                }
                else -> {
                    photoDao.markNeedsAttention(
                        photo.clientPhotoId,
                        "cancel_http_${error.code()}",
                        now(),
                    )
                    false
                }
            }
        } catch (error: IOException) {
            throw error
        }
    }

    private suspend fun syncPhoto(initial: DprPhotoEntity): Boolean {
        var photo = photoDao.photo(initial.clientPhotoId) ?: return true
        var report = dprDao.reportById(photo.reportId)
        if (report == null) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "report_not_found", now())
            return false
        }
        if (report.status != DprRepository.STATUS_DRAFT) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "report_not_draft", now())
            return false
        }
        if (report.syncState == DprSyncState.NEEDS_ATTENTION) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "report_needs_attention", now())
            return false
        }
        if (
            report.serverId == null ||
            report.revision < 1 ||
            report.syncState != DprSyncState.SYNCED ||
            dprDao.activeMutationCount(report.id) > 0
        ) {
            markWaiting(photo)
            return false
        }

        val originalPath = photo.originalPath
        val sha256 = photo.sha256
        val contentType = photo.contentType
        if (originalPath.isNullOrBlank() || sha256.isNullOrBlank() || contentType.isNullOrBlank()) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "local_file_metadata_missing", now())
            return false
        }
        val original = File(originalPath)
        if (!original.isFile || original.length() != photo.sizeBytes) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "local_file_missing", now())
            return false
        }

        try {
            val session = establishSession(photo, report.projectId, requireNotNull(report.serverId), report.revision)
            photoDao.updateResumableState(
                clientPhotoId = photo.clientPhotoId,
                state = DprPhotoState.UPLOADING,
                uploadSessionId = session.uploadId,
                uploadedBytes = session.uploadedBytes,
                chunkSizeBytes = session.chunkSizeBytes,
                errorCode = null,
                attemptCount = photo.attemptCount + 1,
                updatedAt = now(),
            )
            photo = requireNotNull(photoDao.photo(photo.clientPhotoId))

            if (session.status != "finalized") {
                uploadMissingChunks(
                    photo = photo,
                    original = original,
                    reportServerId = requireNotNull(report.serverId),
                )
            }

            report = requireNotNull(dprDao.reportById(photo.reportId))
            val finalized = api.finalizeResumableUpload(
                projectId = report.projectId,
                reportId = requireNotNull(report.serverId),
                uploadId = session.uploadId,
                request = DprPhotoFinalizeRequest(
                    expectedRevision = report.revision,
                    clientPhotoId = photo.clientPhotoId,
                    caption = photo.caption,
                    capturedAt = photo.capturedAt,
                ),
            )
            original.delete()
            photoDao.markSynced(
                clientPhotoId = photo.clientPhotoId,
                uploadSessionId = session.uploadId,
                serverAssetId = finalized.assetId,
                serverVersion = finalized.version,
                reportRevision = finalized.reportRevision,
                updatedAt = now(),
            )
            dprRepository.refreshProject(report.projectId)
            return true
        } catch (error: HttpException) {
            return handleHttpFailure(photo, error)
        } catch (error: IOException) {
            markWaiting(photoDao.photo(photo.clientPhotoId) ?: photo)
            throw error
        } catch (error: IllegalArgumentException) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "invalid_upload_state", now())
            return false
        } catch (error: IllegalStateException) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "invalid_upload_state", now())
            return false
        }
    }

    private suspend fun establishSession(
        photo: DprPhotoEntity,
        projectId: String,
        reportServerId: String,
        revision: Int,
    ): DprPhotoResumableSessionResponse {
        val existingId = photo.uploadSessionId
        if (existingId != null) {
            try {
                return validateSession(
                    photo,
                    api.resumableStatus(projectId, reportServerId, existingId),
                )
            } catch (error: HttpException) {
                if (error.code() != 404) throw error
                photoDao.resetUploadSession(photo.clientPhotoId, now())
            }
        }
        return validateSession(
            photo,
            api.startResumableUpload(
                projectId = projectId,
                reportId = reportServerId,
                request = DprPhotoUploadStartRequest(
                    expectedRevision = revision,
                    clientPhotoId = photo.clientPhotoId,
                    originalFilename = photo.filename,
                    contentType = requireNotNull(photo.contentType),
                    sizeBytes = photo.sizeBytes,
                    sha256 = requireNotNull(photo.sha256),
                ),
            ),
        )
    }

    private fun validateSession(
        photo: DprPhotoEntity,
        session: DprPhotoResumableSessionResponse,
    ): DprPhotoResumableSessionResponse {
        require(session.clientPhotoId == photo.clientPhotoId) {
            "Company server returned the wrong photo identity."
        }
        require(session.sizeBytes == photo.sizeBytes) {
            "Company server returned the wrong photo size."
        }
        require(session.uploadedBytes in 0..photo.sizeBytes) {
            "Company server returned an invalid upload offset."
        }
        require(session.chunkSizeBytes > 0) {
            "Company server returned an invalid chunk size."
        }
        return session
    }

    private suspend fun uploadMissingChunks(
        photo: DprPhotoEntity,
        original: File,
        reportServerId: String,
    ) {
        var current = requireNotNull(photoDao.photo(photo.clientPhotoId))
        var offset = current.uploadedBytes
        while (offset < current.sizeBytes) {
            val chunkSize = minOf(current.chunkSizeBytes.toLong(), current.sizeBytes - offset).toInt()
            val bytes = readChunk(original, offset, chunkSize)
            val digest = sha256(bytes)
            try {
                val response = api.uploadChunk(
                    projectId = current.projectId,
                    reportId = reportServerId,
                    uploadId = requireNotNull(current.uploadSessionId),
                    uploadOffset = offset,
                    chunkSha256 = digest,
                    body = bytes.toRequestBody("application/octet-stream".toMediaType()),
                )
                offset = response.uploadedBytes
                require(offset in 0..current.sizeBytes) { "Server returned an invalid upload offset." }
                photoDao.updateResumableState(
                    clientPhotoId = current.clientPhotoId,
                    state = DprPhotoState.UPLOADING,
                    uploadSessionId = current.uploadSessionId,
                    uploadedBytes = offset,
                    chunkSizeBytes = current.chunkSizeBytes,
                    errorCode = null,
                    attemptCount = current.attemptCount,
                    updatedAt = now(),
                )
                current = requireNotNull(photoDao.photo(current.clientPhotoId))
            } catch (error: HttpException) {
                if (error.code() != 409) throw error
                val status = validateSession(
                    current,
                    api.resumableStatus(
                        current.projectId,
                        reportServerId,
                        requireNotNull(current.uploadSessionId),
                    ),
                )
                offset = status.uploadedBytes
                photoDao.updateResumableState(
                    clientPhotoId = current.clientPhotoId,
                    state = DprPhotoState.UPLOADING,
                    uploadSessionId = status.uploadId,
                    uploadedBytes = status.uploadedBytes,
                    chunkSizeBytes = status.chunkSizeBytes,
                    errorCode = null,
                    attemptCount = current.attemptCount,
                    updatedAt = now(),
                )
                current = requireNotNull(photoDao.photo(current.clientPhotoId))
            }
        }
    }

    private suspend fun handleHttpFailure(photo: DprPhotoEntity, error: HttpException): Boolean {
        return when {
            error.code() == 401 -> throw error
            error.code() == 408 || error.code() == 429 || error.code() in 500..599 -> {
                markWaiting(photoDao.photo(photo.clientPhotoId) ?: photo)
                throw error
            }
            error.code() == 409 -> {
                photoDao.markNeedsAttention(photo.clientPhotoId, "revision_conflict", now())
                dprDao.updateReportSyncState(
                    photo.reportId,
                    DprSyncState.NEEDS_ATTENTION,
                    now(),
                )
                false
            }
            error.code() == 403 -> {
                photoDao.markNeedsAttention(photo.clientPhotoId, "permission_denied", now())
                false
            }
            error.code() == 422 -> {
                photoDao.markNeedsAttention(photo.clientPhotoId, "validation_rejected", now())
                false
            }
            error.code() == 404 -> {
                photoDao.markNeedsAttention(photo.clientPhotoId, "server_report_not_found", now())
                false
            }
            else -> {
                photoDao.markNeedsAttention(photo.clientPhotoId, "http_${error.code()}", now())
                false
            }
        }
    }

    private suspend fun markWaiting(photo: DprPhotoEntity) {
        photoDao.updateResumableState(
            clientPhotoId = photo.clientPhotoId,
            state = DprPhotoState.WAITING_FOR_NETWORK,
            uploadSessionId = photo.uploadSessionId,
            uploadedBytes = photo.uploadedBytes,
            chunkSizeBytes = photo.chunkSizeBytes,
            errorCode = null,
            attemptCount = photo.attemptCount,
            updatedAt = now(),
        )
    }

    private suspend fun deleteLocalPhoto(photo: DprPhotoEntity) {
        photo.originalPath?.let { File(it).parentFile?.deleteRecursively() }
        photoDao.delete(photo.clientPhotoId)
    }

    private fun readChunk(file: File, offset: Long, size: Int): ByteArray {
        val buffer = ByteArray(size)
        RandomAccessFile(file, "r").use { handle ->
            handle.seek(offset)
            handle.readFully(buffer)
        }
        return buffer
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }

    private fun now(): Long = System.currentTimeMillis()
}
