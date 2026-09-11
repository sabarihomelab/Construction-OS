package com.constructionos.app.core.projects

import com.constructionos.app.core.database.ProjectDao
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.ProjectResponse
import kotlinx.coroutines.flow.Flow

class ProjectRepository(
    private val api: ConstructionOsApi,
    private val dao: ProjectDao,
) {
    fun observeProjects(organizationId: String): Flow<List<ProjectEntity>> =
        dao.observeForOrganization(organizationId)

    suspend fun refresh(organizationId: String): List<ProjectEntity> {
        val projects = api.projects()
            .asSequence()
            .filter { it.organizationId == organizationId }
            .map(ProjectResponse::toEntity)
            .toList()
        dao.replaceForOrganization(organizationId, projects)
        return projects
    }

    suspend fun clear(organizationId: String) {
        dao.clearForOrganization(organizationId)
    }
}

internal fun ProjectResponse.toEntity(): ProjectEntity = ProjectEntity(
    id = id,
    organizationId = organizationId,
    number = number,
    name = name,
    description = description,
    status = status,
    revision = revision,
    timezone = timezone,
    currencyCode = currencyCode,
    unitSystem = unitSystem,
    startDate = startDate,
    targetCompletionDate = targetCompletionDate,
    addressLine1 = addressLine1,
    addressLine2 = addressLine2,
    locality = locality,
    region = region,
    postalCode = postalCode,
    countryCode = countryCode,
)
