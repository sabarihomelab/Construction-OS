package com.constructionos.app.core.files

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import java.io.File
import java.security.MessageDigest
import kotlin.math.max

class PhotoUploadPreparer {
    fun prepare(
        original: File,
        originalFilename: String,
        originalContentType: String,
        originalSizeBytes: Long,
        originalSha256: String,
        policy: PhotoUploadPolicy,
        workingDirectory: File,
    ): PreparedPhotoUpload {
        val bounds = readBounds(original)
        val decision = PhotoUploadPolicyEngine.decide(
            policy = policy,
            originalSizeBytes = originalSizeBytes,
            width = bounds.first,
            height = bounds.second,
        )
        val transformable = originalContentType.lowercase() in TRANSFORMABLE_CONTENT_TYPES
        if (!decision.transformToJpeg || !transformable) {
            return PreparedPhotoUpload(
                file = original,
                filename = originalFilename,
                contentType = originalContentType,
                sizeBytes = originalSizeBytes,
                sha256 = originalSha256,
                transformed = false,
            )
        }

        val uploadFile = File(workingDirectory, "upload.jpg")
        val decoded = decodeForTarget(original, decision.targetMaxEdgePx)
        try {
            uploadFile.outputStream().buffered().use { output ->
                check(decoded.compress(Bitmap.CompressFormat.JPEG, decision.jpegQuality, output)) {
                    "Could not create the optimized photo upload."
                }
            }
        } finally {
            decoded.recycle()
        }

        val uploadSize = uploadFile.length()
        if (uploadSize <= 0L || uploadSize >= originalSizeBytes) {
            uploadFile.delete()
            return PreparedPhotoUpload(
                file = original,
                filename = originalFilename,
                contentType = originalContentType,
                sizeBytes = originalSizeBytes,
                sha256 = originalSha256,
                transformed = false,
            )
        }

        return PreparedPhotoUpload(
            file = uploadFile,
            filename = jpegFilename(originalFilename),
            contentType = "image/jpeg",
            sizeBytes = uploadSize,
            sha256 = sha256(uploadFile),
            transformed = true,
        )
    }

    fun createThumbnail(
        source: File,
        target: File,
        maxEdgePx: Int = THUMBNAIL_MAX_EDGE_PX,
        jpegQuality: Int = THUMBNAIL_JPEG_QUALITY,
    ) {
        require(maxEdgePx > 0) { "Thumbnail size must be positive." }
        require(jpegQuality in 1..100) { "Thumbnail quality must be between 1 and 100." }
        val decoded = decodeForTarget(source, maxEdgePx)
        try {
            target.outputStream().buffered().use { output ->
                check(decoded.compress(Bitmap.CompressFormat.JPEG, jpegQuality, output)) {
                    "Could not create photo thumbnail."
                }
            }
        } finally {
            decoded.recycle()
        }
    }

    private fun readBounds(file: File): Pair<Int, Int> {
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, options)
        require(options.outWidth > 0 && options.outHeight > 0) {
            "Selected file is not a readable image."
        }
        return options.outWidth to options.outHeight
    }

    private fun decodeForTarget(file: File, targetMaxEdgePx: Int): Bitmap {
        val (width, height) = readBounds(file)
        var sampleSize = 1
        val decodeCeiling = targetMaxEdgePx * 2
        while (max(width / sampleSize, height / sampleSize) > decodeCeiling) {
            sampleSize *= 2
        }

        val decoded = BitmapFactory.decodeFile(
            file.absolutePath,
            BitmapFactory.Options().apply { inSampleSize = sampleSize },
        ) ?: throw IllegalArgumentException("Selected image could not be decoded.")

        val oriented = applyExifOrientation(decoded, file)
        if (oriented !== decoded) decoded.recycle()

        val largest = max(oriented.width, oriented.height)
        if (largest <= targetMaxEdgePx) return oriented

        val ratio = targetMaxEdgePx.toFloat() / largest.toFloat()
        val scaled = Bitmap.createScaledBitmap(
            oriented,
            (oriented.width * ratio).toInt().coerceAtLeast(1),
            (oriented.height * ratio).toInt().coerceAtLeast(1),
            true,
        )
        if (scaled !== oriented) oriented.recycle()
        return scaled
    }

    private fun applyExifOrientation(bitmap: Bitmap, file: File): Bitmap {
        val orientation = runCatching {
            ExifInterface(file.absolutePath).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )
        }.getOrDefault(ExifInterface.ORIENTATION_NORMAL)

        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.setScale(-1f, 1f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.setRotate(180f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> {
                matrix.setRotate(180f)
                matrix.postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_TRANSPOSE -> {
                matrix.setRotate(90f)
                matrix.postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.setRotate(90f)
            ExifInterface.ORIENTATION_TRANSVERSE -> {
                matrix.setRotate(-90f)
                matrix.postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.setRotate(-90f)
            else -> return bitmap
        }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                if (count == 0) continue
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }

    private fun jpegFilename(value: String): String {
        val base = value.substringBeforeLast('.', value).ifBlank { "site-photo" }
        return "$base.jpg"
    }

    companion object {
        private const val THUMBNAIL_MAX_EDGE_PX = 512
        private const val THUMBNAIL_JPEG_QUALITY = 82
        private val TRANSFORMABLE_CONTENT_TYPES = setOf(
            "image/jpeg",
            "image/jpg",
            "image/heic",
            "image/heif",
        )
    }
}

data class PreparedPhotoUpload(
    val file: File,
    val filename: String,
    val contentType: String,
    val sizeBytes: Long,
    val sha256: String,
    val transformed: Boolean,
)
