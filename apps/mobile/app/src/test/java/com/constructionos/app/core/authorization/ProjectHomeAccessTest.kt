package com.constructionos.app.core.authorization

import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.network.VisibleFeatureResponse
import org.junit.Assert.assertEquals
import org.junit.Test

class ProjectHomeAccessTest {
    @Test
    fun `actions require both mobile feature visibility and project permission`() {
        val context = context(
            permissions = emptyList(),
            projectPermissions = mapOf(
                "project-1" to listOf(
                    "workforce.attendance.view",
                    "field.daily_report.create",
                ),
            ),
            features = listOf(
                feature("workforce", mobileEnabled = true),
                feature("field", mobileEnabled = true),
                feature("projects", mobileEnabled = true),
            ),
        )

        assertEquals(
            listOf(ProjectHomeActionKey.ATTENDANCE, ProjectHomeActionKey.DAILY_REPORT),
            context.projectHomeActions("project-1").map { it.key },
        )
        assertEquals(emptyList<ProjectHomeAction>(), context.projectHomeActions("project-2"))
    }

    @Test
    fun `organization permission can authorize action but hidden mobile feature still suppresses it`() {
        val context = context(
            permissions = listOf(
                "workforce.attendance.view",
                "field.daily_report.view",
            ),
            projectPermissions = emptyMap(),
            features = listOf(
                feature("workforce", mobileEnabled = false),
                feature("field", mobileEnabled = true),
            ),
        )

        assertEquals(
            listOf(ProjectHomeActionKey.DAILY_REPORT),
            context.projectHomeActions("project-1").map { it.key },
        )
    }

    private fun context(
        permissions: List<String>,
        projectPermissions: Map<String, List<String>>,
        features: List<VisibleFeatureResponse>,
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
