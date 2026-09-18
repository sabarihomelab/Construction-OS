package com.constructionos.app.core.authorization

import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.ProjectAccessMembershipResponse
import com.constructionos.app.core.network.ProjectMembershipCreateRequest
import com.constructionos.app.core.network.ProjectMembershipResponse
import com.constructionos.app.core.network.ProjectMembershipStatusRequest
import com.constructionos.app.core.network.ProjectRoleSetRequest
import com.constructionos.app.core.network.SecurityMembershipResponse
import com.constructionos.app.core.network.SecurityRoleResponse

/**
 * Project access administration is online-only. The backend remains authoritative for
 * project membership and project-scoped role assignment.
 */
class ProjectAccessAdminRepository(
    private val api: ConstructionOsApi,
) {
    suspend fun snapshot(projectId: String): ProjectAccessAdminSnapshot =
        ProjectAccessAdminSnapshot(
            access = api.projectAccess(projectId),
            companyMemberships = api.securityMemberships(),
            projectRoles = api.securityRoles().filter { role ->
                role.isActive && role.assignmentScope in setOf("project", "both")
            },
        )

    suspend fun addMember(
        projectId: String,
        organizationMembershipId: String,
        title: String?,
    ): ProjectMembershipResponse = api.addProjectMembership(
        projectId,
        ProjectMembershipCreateRequest(
            organizationMembershipId = organizationMembershipId,
            title = title,
        ),
    )

    suspend fun replaceRoles(
        projectId: String,
        projectMembershipId: String,
        roleIds: Set<String>,
    ): ProjectAccessMembershipResponse = api.replaceProjectMembershipRoles(
        projectId,
        projectMembershipId,
        ProjectRoleSetRequest(roleIds.sorted()),
    )

    suspend fun updateStatus(
        projectId: String,
        projectMembershipId: String,
        status: String,
    ): ProjectMembershipResponse = api.updateProjectMembershipStatus(
        projectId,
        projectMembershipId,
        ProjectMembershipStatusRequest(status = status),
    )
}

data class ProjectAccessAdminSnapshot(
    val access: List<ProjectAccessMembershipResponse>,
    val companyMemberships: List<SecurityMembershipResponse>,
    val projectRoles: List<SecurityRoleResponse>,
)
