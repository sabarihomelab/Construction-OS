package com.constructionos.app.core.files

import kotlin.math.max

enum class PhotoUploadPolicy(val wireValue: String) {
    FIELD_OPTIMIZED("field_optimized"),
    EVIDENCE_ORIGINAL("evidence_original"),
    ;
}

data class PhotoUploadDecision(
    val transformToJpeg: Boolean,
    val targetMaxEdgePx: Int,
    val jpegQuality: Int,
)

object PhotoUploadPolicyEngine {
    const val FIELD_MAX_EDGE_PX = 2560
    const val FIELD_JPEG_QUALITY = 88
    const val KEEP_ORIGINAL_MAX_BYTES = 2_500_000L

    fun decide(
        policy: PhotoUploadPolicy,
        originalSizeBytes: Long,
        width: Int,
        height: Int,
    ): PhotoUploadDecision {
        require(originalSizeBytes > 0) { "Photo size must be positive." }
        require(width > 0 && height > 0) { "Photo dimensions must be positive." }

        if (policy == PhotoUploadPolicy.EVIDENCE_ORIGINAL) {
            return PhotoUploadDecision(
                transformToJpeg = false,
                targetMaxEdgePx = max(width, height),
                jpegQuality = 100,
            )
        }

        val largestEdge = max(width, height)
        val shouldTransform =
            originalSizeBytes > KEEP_ORIGINAL_MAX_BYTES || largestEdge > FIELD_MAX_EDGE_PX
        return PhotoUploadDecision(
            transformToJpeg = shouldTransform,
            targetMaxEdgePx = FIELD_MAX_EDGE_PX,
            jpegQuality = FIELD_JPEG_QUALITY,
        )
    }
}
