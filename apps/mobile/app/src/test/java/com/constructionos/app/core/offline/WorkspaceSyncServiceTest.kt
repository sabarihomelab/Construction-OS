package com.constructionos.app.core.offline

import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.network.VisibleFeatureResponse
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WorkspaceSyncServiceTest {
    @Test
    fun `attendance server pull requires mobile workforce and view permission`() {
        val context = context(
            projectPermissions = mapOf(
                "project-1" to listOf("workforce.attendance.view"),
            ),
        )

        assertTrue(context.canUseAttendance("project-1"))
        assertTrue(context.canViewAttendance("project-1"))
        assertFalse(context.canViewAttendance("project-2"))
    }

    @Test
    fun `attendance roster cache also supports create or update users`() {
        val creator = context(
            projectPermissions = mapOf(
                "project-1" to listOf("workforce.attendance.create"),
            ),
        )
        val editor = context(
            projectPermissions = mapOf(
                "project-1" to listOf("workforce.attendance.update"),
            ),
        )

        assertTrue(creator.canUseAttendance("project-1"))
        assertFalse(creator.canViewAttendance("project-1"))
        assertTrue(editor.canUseAttendance("project-1"))
    }

    @Test
    fun `hidden workforce mobile feature suppresses all attendance sync`() {
        val context = context(
            permissions = listOf("workforce.attendance.view"),
            features = listOf(feature("workforce", mobileEnabled = false)),
        )

        assertFalse(context.canUseAttendance("project-1"))
        assertFalse(context.canViewAttendance("project-1"))
    }

    private fun context(
        permissions: List<String> = emptyList(),
        projectPermissions: Map<String, List<String>> = emptyMap(),
        features: List<VisibleFeatureResponse> = listOf(feature("workforce", mobileEnabled = true)),
    ) = SessionContextResponse(
        organizationId = "org-1",
        membershipId = "membership-1",
        authorizationRevision = 1,
        configurationRevision = 1,
        permissions = permissions,
        projectPermissions = projectPermissions,
        features = features,
    )

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
