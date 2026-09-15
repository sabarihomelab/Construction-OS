package com.constructionos.app.core.dpr

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprPhotoDao
import com.constructionos.app.core.database.DprPhotoEntity
import com.constructionos.app.core.database.DprPhotoState
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.files.PhotoUploadPolicy
import com.constructionos.app.core.files.PhotoUploadPreparer
import com.constructionos.app.core.network.DprPhotoApi
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext

class DprPhotoRepository(
    context: Context,
    private val connectionNamespace: String,
    private val api: DprPhotoApi,
    private val photoDao: DprPhotoDao,
    private val dprDao: DprDao,
    private val syncScheduler: WorkspaceSyncScheduler,
) {
    private val applicationContext = context.applicationContext
    private val resolver = applicationContext.contentResolver
    private val uploadPreparer = PhotoUploadPreparer()
    private val photoRoot = File(
        applicationContext.filesDir,
        "dpr_photos/${safeNamespace(connectionNamespace)}",
    )

    fun observePhotos(reportId: String): Flow<List<DprPhotoEntity>> =
        photoDao.observeReportPhotos(reportId)

    suspend fun stageGalleryPhoto(
        reportId: String,
        sourceUri: Uri,
        caption: String? = null,
        uploadPolicy: PhotoUploadPolicy = PhotoUploadPolicy.FIELD_OPTIMIZED,
    ): String = withContext(Dispatchers.IO) {
        val report = requireNotNull(dprDao.reportById(reportId)) { "Daily report was not found." }
        require(report.status == DprRepository.STATUS_DRAFT) {
            "Photos can only be added while the daily report is a draft."
        }
        require(report.syncState != DprSyncState.NEEDS_ATTENTION) {
            "Resolve the daily report sync issue before adding photos."
        }
        val normalizedCaption = caption?.trim()?.takeIf { it.isNotEmpty() }
        require((normalizedCaption?.length ?: 0) <= 1000) {
            "Photo caption must be 1000 characters or fewer."
        }

        val clientPhotoId = UUID.randomUUID().toString()
        val directory = File(photoRoot, clientPhotoId)
        check(directory.mkdirs() || directory.isDirectory) { "Could not prepare photo storage." }

        try {
            val displayName = queryDisplayName(sourceUri)
                ?.let(::safeFilename)
                ?.takeIf { it.isNotBlank() }
                ?: "site-photo-$clientPhotoId"
            val original = File(directory, "original-${safeFilename(displayName)}")
            val copied = copyAndHash(sourceUri, original)
            val originalContentType = detectContentType(original, resolver.getType(sourceUri))
                ?: throw IllegalArgumentException("Select a supported JPEG, PNG, WebP, HEIC or HEIF image.")
            val prepared = uploadPreparer.prepare(
                original = original,
                originalFilename = displayName,
                originalContentType = originalContentType,
                originalSizeBytes = copied.sizeBytes,
                originalSha256 = copied.sha256,
                policy = uploadPolicy,
                workingDirectory = directory,
            )
            val thumbnail = File(directory, "thumbnail.jpg")
            uploadPreparer.createThumbnail(prepared.file, thumbnail)

            val now = System.currentTimeMillis()
            photoDao.upsert(
                DprPhotoEntity(
                    clientPhotoId = clientPhotoId,
                    reportId = report.id,
                    projectId = report.projectId,
                    originalPath = original.absolutePath,
                    uploadPath = prepared.file
                        .takeIf { it.absolutePath != original.absolutePath }
                        ?.absolutePath,
                    uploadPolicy = uploadPolicy.wireValue,
                    thumbnailPath = thumbnail.absolutePath,
                    filename = prepared.filename,
                    contentType = prepared.contentType,
                    sizeBytes = prepared.sizeBytes,
                    sha256 = prepared.sha256,
                    caption = normalizedCaption,
                    capturedAt = null,
                    uploadSessionId = null,
                    uploadTargetUrl = null,
                    serverAssetId = null,
                    serverVersion = null,
                    baseRevision = report.revision,
                    state = if (syncScheduler.isNetworkAvailable()) {
                        DprPhotoState.WAITING_FOR_NETWORK
                    } else {
                        DprPhotoState.SAVED_ON_DEVICE
                    },
                    errorCode = null,
                    attemptCount = 0,
                    createdAt = now,
                    updatedAt = now,
                ),
            )
            syncScheduler.scheduleOnce()
            clientPhotoId
        } catch (error: Exception) {
            directory.deleteRecursively()
            throw error
        }
    }

    suspend fun refreshReport(reportId: String) {
        val report = dprDao.reportById(reportId) ?: return
        val serverId = report.serverId ?: return
        val remote = api.photos(report.projectId, serverId)
        if (remote.isEmpty()) return

        val now = System.currentTimeMillis()
        val entities = remote.map { row ->
            val existing = row.clientPhotoId?.let { photoDao.photo(it) }
                ?: photoDao.photoByServerAssetId(row.assetId)
            DprPhotoEntity(
                clientPhotoId = row.clientPhotoId ?: existing?.clientPhotoId ?: "server:${row.assetId}",
                reportId = report.id,
                projectId = report.projectId,
                originalPath = existing?.originalPath,
                uploadPath = existing?.uploadPath,
                uploadPolicy = existing?.uploadPolicy ?: "server_original",
                thumbnailPath = existing?.thumbnailPath,
                filename = row.filename,
                contentType = row.contentType,
                sizeBytes = row.sizeBytes,
                sha256 = existing?.sha256,
                caption = row.caption,
                capturedAt = row.capturedAt,
                uploadSessionId = existing?.uploadSessionId,
                uploadTargetUrl = null,
                uploadedBytes = row.sizeBytes,
                chunkSizeBytes = existing?.chunkSizeBytes ?: DEFAULT_CHUNK_SIZE_BYTES,
                serverAssetId = row.assetId,
                serverVersion = row.version,
                baseRevision = row.reportRevision,
                state = DprPhotoState.SYNCED,
                errorCode = null,
                attemptCount = existing?.attemptCount ?: 0,
                createdAt = parseCreatedAt(row.createdAt) ?: existing?.createdAt ?: now,
                updatedAt = now,
            )
        }
        photoDao.upsertAll(entities)
    }

    suspend fun discardLocalPhoto(clientPhotoId: String) = withContext(Dispatchers.IO) {
        val photo = photoDao.photo(clientPhotoId) ?: return@withContext
        require(photo.serverAssetId == null) { "Synced photos must be removed through the server." }
        if (photo.uploadSessionId == null) {
            localDirectory(photo)?.deleteRecursively()
            photoDao.delete(clientPhotoId)
        } else {
            photoDao.markCancelRequested(clientPhotoId, System.currentTimeMillis())
            syncScheduler.scheduleOnce()
        }
    }

    suspend fun retryPhoto(clientPhotoId: String) {
        val photo = requireNotNull(photoDao.photo(clientPhotoId)) { "Photo was not found." }
        require(photo.state == DprPhotoState.NEEDS_ATTENTION) { "Photo does not need a retry." }
        photoDao.updateResumableState(
            clientPhotoId = photo.clientPhotoId,
            state = DprPhotoState.WAITING_FOR_NETWORK,
            uploadSessionId = photo.uploadSessionId,
            uploadedBytes = photo.uploadedBytes,
            chunkSizeBytes = photo.chunkSizeBytes,
            errorCode = null,
            attemptCount = photo.attemptCount,
            updatedAt = System.currentTimeMillis(),
        )
        syncScheduler.scheduleOnce()
    }

    private fun queryDisplayName(uri: Uri): String? {
        return resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (!cursor.moveToFirst()) return@use null
            val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (index < 0) null else cursor.getString(index)
        }
    }

    private fun copyAndHash(uri: Uri, target: File): CopiedPhoto {
        val digest = MessageDigest.getInstance("SHA-256")
        var total = 0L
        val input = requireNotNull(resolver.openInputStream(uri)) { "Selected photo could not be opened." }
        input.buffered().use { source ->
            target.outputStream().buffered().use { sink ->
                val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                while (true) {
                    val count = source.read(buffer)
                    if (count < 0) break
                    if (count == 0) continue
                    total += count
                    require(total <= MAX_PHOTO_BYTES) { "Photo must be 25 MB or smaller." }
                    digest.update(buffer, 0, count)
                    sink.write(buffer, 0, count)
                }
            }
        }
        require(total > 0) { "Selected photo is empty." }
        return CopiedPhoto(total, digest.digest().toHex())
    }

    private fun detectContentType(file: File, declared: String?): String? {
        val signature = ByteArray(16)
        val count = file.inputStream().use { it.read(signature) }
        if (count >= 12) {
            if (
                signature[0] == 0xFF.toByte() &&
                signature[1] == 0xD8.toByte() &&
                signature[2] == 0xFF.toByte()
            ) return "image/jpeg"
            if (
                signature.copyOfRange(0, 8).contentEquals(
                    byteArrayOf(
                        0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
                    ),
                )
            ) return "image/png"
            if (
                String(signature, 0, 4, Charsets.US_ASCII) == "RIFF" &&
                String(signature, 8, 4, Charsets.US_ASCII) == "WEBP"
            ) return "image/webp"
            if (String(signature, 4, 4, Charsets.US_ASCII) == "ftyp") {
                val brand = String(signature, 8, 4, Charsets.US_ASCII).lowercase()
                if (brand in HEIF_BRANDS) {
                    return if (brand.startsWith("hei") || brand.startsWith("hev")) {
                        "image/heic"
                    } else {
                        "image/heif"
                    }
                }
            }
        }
        return declared?.lowercase()?.takeIf { it in SUPPORTED_CONTENT_TYPES }
    }

    private fun localDirectory(photo: DprPhotoEntity): File? =
        photo.originalPath?.let(::File)?.parentFile
            ?: photo.uploadPath?.let(::File)?.parentFile
            ?: photo.thumbnailPath?.let(::File)?.parentFile

    companion object {
        private const val MAX_PHOTO_BYTES = 25L * 1024L * 1024L
        private const val DEFAULT_CHUNK_SIZE_BYTES = 5 * 1024 * 1024
        private val SUPPORTED_CONTENT_TYPES = setOf(
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "image/heic",
            "image/heif",
        )
        private val HEIF_BRANDS = setOf("heic", "heix", "hevc", "hevx", "mif1", "msf1")
    }
}

private data class CopiedPhoto(val sizeBytes: Long, val sha256: String)

private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it.toInt() and 0xff) }

private fun safeFilename(value: String): String = value
    .substringAfterLast('/')
    .substringAfterLast('\\')
    .replace(Regex("[^A-Za-z0-9._-]"), "_")
    .take(160)
    .ifBlank { "photo" }

private fun safeNamespace(value: String): String = MessageDigest.getInstance("SHA-256")
    .digest(value.toByteArray(Charsets.UTF_8))
    .take(8)
    .joinToString("") { "%02x".format(it.toInt() and 0xff) }

private fun parseCreatedAt(value: String): Long? = runCatching { Instant.parse(value).toEpochMilli() }.getOrNull()
