package com.constructionos.app.core.offline

import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.network.VisibleFeatureResponse
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WorkspaceSyncServiceTest {
    @Test
    fun `attendance roster refresh requires mobile workforce and attendance view permission`() {
        val context = SessionContextResponse(
            organizationId = "org-1",
            membershipId = "membership-1",
            authorizationRevision = 1,
            configurationRevision = 1,
            permissions = emptyList(),
            projectPermissions = mapOf(
                "project-1" to listOf("workforce.attendance.view"),
            ),
            features = listOf(feature("workforce", mobileEnabled = true)),
        )

        assertTrue(context.canViewAttendance("project-1"))
        assertFalse(context.canViewAttendance("project-2"))
    }

    @Test
    fun `hidden workforce mobile feature suppresses attendance roster refresh`() {
        val context = SessionContextResponse(
            organizationId = "org-1",
            membershipId = "membership-1",
            authorizationRevision = 1,
            configurationRevision = 1,
            permissions = listOf("workforce.attendance.view"),
            features = listOf(feature("workforce", mobileEnabled = false)),
        )

        assertFalse(context.canViewAttendance("project-1"))
    }

    private fun feature(key: String, mobileEnabled: Boolean) = VisibleFeatureResponse(
        key = key,
        name = key,
        kind = "module",
        sensitivity = "standard",
        displayOrder = 100,
        mobileEnabled = mobileEnabled,
        offlineEnabled = true,
    )
}
