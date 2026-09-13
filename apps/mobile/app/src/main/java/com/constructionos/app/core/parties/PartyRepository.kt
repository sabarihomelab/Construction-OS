package com.constructionos.app.core.parties

import com.constructionos.app.core.database.PartyDao
import com.constructionos.app.core.database.PartyEntity
import com.constructionos.app.core.database.ProjectPartyAssignmentEntity
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.PartyResponse
import com.constructionos.app.core.network.ProjectPartyAssignmentResponse
import kotlinx.coroutines.flow.Flow

class PartyRepository(
    private val api: ConstructionOsApi,
    private val dao: PartyDao,
) {
    fun observeParties(organizationId: String): Flow<List<PartyEntity>> =
        dao.observeParties(organizationId)

    fun observeAssignments(projectId: String): Flow<List<ProjectPartyAssignmentEntity>> =
        dao.observeAssignments(projectId)

    suspend fun refresh(organizationId: String, projectId: String) {
        val parties = api.parties().map(PartyResponse::toEntity)
        val assignments = api.projectPartyAssignments(projectId)
            .filter { it.active }
            .map(ProjectPartyAssignmentResponse::toEntity)
        dao.replaceDirectory(
            organizationId = organizationId,
            projectId = projectId,
            parties = parties,
            assignments = assignments,
        )
    }
}

private fun PartyResponse.toEntity(): PartyEntity = PartyEntity(
    id = id,
    organizationId = organizationId,
    code = code,
    name = name,
    legalName = legalName,
    partyType = partyType,
    status = status,
    email = email,
    phone = phone,
    addressLine1 = addressLine1,
    addressLine2 = addressLine2,
    locality = locality,
    stateName = stateName,
    postalCode = postalCode,
    revision = revision,
)

private fun ProjectPartyAssignmentResponse.toEntity(): ProjectPartyAssignmentEntity =
    ProjectPartyAssignmentEntity(
        id = id,
        projectId = projectId,
        partyId = partyId,
        role = role,
        active = active,
        updatedAt = updatedAt,
    )
