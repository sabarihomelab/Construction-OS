package com.constructionos.app.core.files

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PhotoUploadPolicyTest {
    @Test
    fun evidencePolicyNeverTransformsOriginal() {
        val decision = PhotoUploadPolicyEngine.decide(
            policy = PhotoUploadPolicy.EVIDENCE_ORIGINAL,
            originalSizeBytes = 20_000_000,
            width = 8000,
            height = 6000,
        )

        assertFalse(decision.transformToJpeg)
    }

    @Test
    fun fieldPolicyKeepsSmallPhotoOriginal() {
        val decision = PhotoUploadPolicyEngine.decide(
            policy = PhotoUploadPolicy.FIELD_OPTIMIZED,
            originalSizeBytes = 1_500_000,
            width = 1920,
            height = 1080,
        )

        assertFalse(decision.transformToJpeg)
    }

    @Test
    fun fieldPolicyOptimizesLargeBytePayload() {
        val decision = PhotoUploadPolicyEngine.decide(
            policy = PhotoUploadPolicy.FIELD_OPTIMIZED,
            originalSizeBytes = 5_000_000,
            width = 2000,
            height = 1500,
        )

        assertTrue(decision.transformToJpeg)
    }

    @Test
    fun fieldPolicyOptimizesLargeDimensions() {
        val decision = PhotoUploadPolicyEngine.decide(
            policy = PhotoUploadPolicy.FIELD_OPTIMIZED,
            originalSizeBytes = 1_000_000,
            width = 4032,
            height = 3024,
        )

        assertTrue(decision.transformToJpeg)
    }
}
