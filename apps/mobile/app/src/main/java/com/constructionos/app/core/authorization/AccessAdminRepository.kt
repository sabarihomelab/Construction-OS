package com.constructionos.app.core.authorization

import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.SecurityMembershipCreateRequest
import com.constructionos.app.core.network.SecurityMembershipResponse
import com.constructionos.app.core.network.SecurityMembershipRoleSetRequest
import com.constructionos.app.core.network.SecurityPermissionResponse
import com.constructionos.app.core.network.SecurityRoleCreateRequest
import com.constructionos.app.core.network.SecurityRoleFromTemplateRequest
import com.constructionos.app.core.network.SecurityRolePermissionSetRequest
import com.constructionos.app.core.network.SecurityRolePermissionSetResponse
import com.constructionos.app.core.network.SecurityRoleResponse
import com.constructionos.app.core.network.SecurityRoleTemplateResponse

/**
 * Security administration is intentionally online-only.
 * Roles, permissions and memberships are server-authoritative and are not cached in Room.
 */
class AccessAdminRepository(
    private val api: ConstructionOsApi,
) {
    suspend fun snapshot(): AccessAdminSnapshot = AccessAdminSnapshot(
        roles = api.securityRoles(),
        templates = api.roleTemplates(),
        permissions = api.securityPermissions(),
        memberships = api.securityMemberships(),
    )

    suspend fun installDefaults(): List<SecurityRoleResponse> =
        api.installDefaultSecurityRoles()

    suspend fun createBlankRole(
        key: String,
        name: String,
        description: String?,
    ): SecurityRoleResponse = api.createSecurityRole(
        SecurityRoleCreateRequest(
            key = key,
            name = name,
            description = description,
        )
    )

    suspend fun createFromTemplate(
        templateKey: String,
        key: String? = null,
        name: String? = null,
    ): SecurityRoleResponse = api.createRoleFromTemplate(
        templateKey,
        SecurityRoleFromTemplateRequest(key = key, name = name),
    )

    suspend fun rolePermissions(roleId: String): SecurityRolePermissionSetResponse =
        api.securityRolePermissions(roleId)

    suspend fun replaceRolePermissions(
        roleId: String,
        expectedVersion: Int?,
        permissionKeys: Set<String>,
    ): SecurityRoleResponse = api.replaceSecurityRolePermissions(
        roleId,
        SecurityRolePermissionSetRequest(
            expectedVersion = expectedVersion,
            permissionKeys = permissionKeys.sorted(),
        )
    )

    suspend fun addPerson(
        email: String,
        displayName: String,
        kind: String,
        status: String,
        roleIds: Set<String> = emptySet(),
    ): SecurityMembershipResponse = api.createSecurityMembership(
        SecurityMembershipCreateRequest(
            primaryEmail = email,
            displayName = displayName,
            kind = kind,
            status = status,
            roleIds = roleIds.sorted(),
        )
    )

    suspend fun replaceMembershipRoles(
        membershipId: String,
        roleIds: Set<String>,
    ): SecurityMembershipResponse = api.replaceSecurityMembershipRoles(
        membershipId,
        SecurityMembershipRoleSetRequest(roleIds.sorted()),
    )
}

data class AccessAdminSnapshot(
    val roles: List<SecurityRoleResponse>,
    val templates: List<SecurityRoleTemplateResponse>,
    val permissions: List<SecurityPermissionResponse>,
    val memberships: List<SecurityMembershipResponse>,
)
