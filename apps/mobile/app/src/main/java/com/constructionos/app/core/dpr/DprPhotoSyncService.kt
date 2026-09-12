package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprPhotoDao
import com.constructionos.app.core.database.DprPhotoEntity
import com.constructionos.app.core.database.DprPhotoState
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.network.DprPhotoApi
import com.constructionos.app.core.network.DprPhotoFinalizeRequest
import com.constructionos.app.core.network.DprPhotoUploadStartRequest
import java.io.File
import java.io.IOException
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
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
            if (!syncPhoto(photo)) return
        }
    }

    private suspend fun syncPhoto(initial: DprPhotoEntity): Boolean {
        var photo = photoDao.photo(initial.clientPhotoId) ?: return true
        val report = dprDao.reportById(photo.reportId)
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
            photoDao.updateUploadState(
                clientPhotoId = photo.clientPhotoId,
                state = DprPhotoState.WAITING_FOR_NETWORK,
                uploadSessionId = photo.uploadSessionId,
                uploadTargetUrl = photo.uploadTargetUrl,
                errorCode = null,
                attemptCount = photo.attemptCount,
                updatedAt = now(),
            )
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
            if (photo.uploadSessionId == null || photo.uploadTargetUrl == null) {
                val session = api.startUpload(
                    projectId = report.projectId,
                    reportId = requireNotNull(report.serverId),
                    request = DprPhotoUploadStartRequest(
                        expectedRevision = report.revision,
                        clientPhotoId = photo.clientPhotoId,
                        originalFilename = photo.filename,
                        contentType = contentType,
                        sizeBytes = photo.sizeBytes,
                        sha256 = sha256,
                    ),
                )
                require(session.clientPhotoId == photo.clientPhotoId) {
                    "Company server returned the wrong photo identity."
                }
                require(session.target.method.equals("PUT", ignoreCase = true)) {
                    "Unsupported photo upload method."
                }
                require(session.target.headers.isEmpty()) {
                    "This app build does not support custom photo upload headers."
                }
                requireSafeRelativeUploadTarget(session.target.url)
                photoDao.updateUploadState(
                    clientPhotoId = photo.clientPhotoId,
                    state = DprPhotoState.UPLOADING,
                    uploadSessionId = session.uploadId,
                    uploadTargetUrl = session.target.url,
                    errorCode = null,
                    attemptCount = photo.attemptCount + 1,
                    updatedAt = now(),
                )
                photo = requireNotNull(photoDao.photo(photo.clientPhotoId))
            } else {
                requireSafeRelativeUploadTarget(photo.uploadTargetUrl)
                photoDao.updateUploadState(
                    clientPhotoId = photo.clientPhotoId,
                    state = DprPhotoState.UPLOADING,
                    uploadSessionId = photo.uploadSessionId,
                    uploadTargetUrl = photo.uploadTargetUrl,
                    errorCode = null,
                    attemptCount = photo.attemptCount + 1,
                    updatedAt = now(),
                )
            }

            val uploadId = requireNotNull(photo.uploadSessionId)
            val uploadTarget = requireNotNull(photo.uploadTargetUrl)
            val uploadResponse = api.uploadContent(
                relativeUrl = uploadTarget,
                body = original.asRequestBody(contentType.toMediaType()),
            )
            if (!uploadResponse.isSuccessful) {
                if (uploadResponse.code() == 410) {
                    runCatching {
                        api.cancelUpload(report.projectId, requireNotNull(report.serverId), uploadId)
                    }
                    photoDao.resetUploadSession(photo.clientPhotoId, now())
                    throw IOException("DPR photo upload session expired")
                }
                throw HttpException(uploadResponse)
            }

            val latestReport = requireNotNull(dprDao.reportById(photo.reportId))
            val finalized = api.finalizeUpload(
                projectId = latestReport.projectId,
                reportId = requireNotNull(latestReport.serverId),
                uploadId = uploadId,
                request = DprPhotoFinalizeRequest(
                    expectedRevision = latestReport.revision,
                    clientPhotoId = photo.clientPhotoId,
                    caption = photo.caption,
                    capturedAt = photo.capturedAt,
                ),
            )
            original.delete()
            photoDao.markSynced(
                clientPhotoId = photo.clientPhotoId,
                uploadSessionId = uploadId,
                serverAssetId = finalized.assetId,
                serverVersion = finalized.version,
                reportRevision = finalized.reportRevision,
                updatedAt = now(),
            )
            dprRepository.refreshProject(latestReport.projectId)
            return true
        } catch (error: HttpException) {
            return handleHttpFailure(photo, error)
        } catch (error: IOException) {
            resetForRetry(photo)
            throw error
        } catch (error: IllegalArgumentException) {
            photoDao.markNeedsAttention(
                photo.clientPhotoId,
                "unsupported_upload_target",
                now(),
            )
            return false
        } catch (error: IllegalStateException) {
            photoDao.markNeedsAttention(photo.clientPhotoId, "invalid_upload_state", now())
            return false
        }
    }

    private suspend fun handleHttpFailure(photo: DprPhotoEntity, error: HttpException): Boolean {
        return when {
            error.code() == 401 -> throw error
            error.code() in 500..599 -> {
                resetForRetry(photo)
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

    private suspend fun resetForRetry(photo: DprPhotoEntity) {
        val current = photoDao.photo(photo.clientPhotoId) ?: return
        photoDao.updateUploadState(
            clientPhotoId = current.clientPhotoId,
            state = DprPhotoState.WAITING_FOR_NETWORK,
            uploadSessionId = current.uploadSessionId,
            uploadTargetUrl = current.uploadTargetUrl,
            errorCode = null,
            attemptCount = current.attemptCount,
            updatedAt = now(),
        )
    }

    private fun requireSafeRelativeUploadTarget(url: String) {
        require(url.startsWith("/api/v1/") && "://" !in url) {
            "External photo upload targets require a non-authenticated upload client."
        }
    }

    private fun now(): Long = System.currentTimeMillis()
}
