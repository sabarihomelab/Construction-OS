package com.constructionos.app.core.projects

import com.constructionos.app.core.network.ProjectResponse
import org.junit.Assert.assertEquals
import org.junit.Test

class ProjectResponseMappingTest {
    @Test
    fun `project response maps to organization-scoped local entity`() {
        val response = ProjectResponse(
            id = "project-1",
            organizationId = "org-1",
            number = "P-100",
            name = "Riverside Fitout",
            description = "Interior construction",
            status = "active",
            revision = 7,
            timezone = "America/New_York",
            currencyCode = "USD",
            unitSystem = "imperial",
            locality = "Austin",
            region = "TX",
            countryCode = "US",
        )

        val entity = response.toEntity()

        assertEquals("project-1", entity.id)
        assertEquals("org-1", entity.organizationId)
        assertEquals("P-100", entity.number)
        assertEquals("Riverside Fitout", entity.name)
        assertEquals("active", entity.status)
        assertEquals(7, entity.revision)
        assertEquals("USD", entity.currencyCode)
        assertEquals("Austin", entity.locality)
    }
}
