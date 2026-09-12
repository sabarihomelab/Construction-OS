package com.constructionos.app.core.authorization

import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.SecurityMembershipCreateRequest
import com.constructionos.app.core.network.SecurityMembershipPartyRequest
import com.constructionos.app.core.network.SecurityMembershipResponse
import com.constructionos.app.core.network.SecurityMembershipRoleSetRequest
import com.constructionos.app.core.network.SecurityMembershipStatusRequest
import com.constructionos.app.core.network.SecurityPartyReferenceResponse
import com.constructionos.app.core.network.SecurityPermissionResponse
import com.constructionos.app.core.network.SecurityRoleCreateRequest
import com.constructionos.app.core.network.SecurityRoleFromTemplateRequest
import com.constructionos.app.core.network.SecurityRolePermissionSetRequest
import com.constructionos.app.core.network.SecurityRolePermissionSetResponse
import com.constructionos.app.core.network.SecurityRoleResponse
import com.constructionos.app.core.network.SecurityRoleTemplateResponse

/**
 * Security administration is intentionally online-only.
 * Roles, permissions, memberships and represented-party links are server-authoritative
 * and are not cached in Room.
 */
class AccessAdminRepository(
    private val api: ConstructionOsApi,
) {
    suspend fun snapshot(): AccessAdminSnapshot = AccessAdminSnapshot(
        roles = api.securityRoles(),
        templates = api.roleTemplates(),
        permissions = api.securityPermissions(),
        memberships = api.securityMemberships(),
        partyReferences = api.securityPartyReferences(),
    )

    suspend fun installDefaults(): List<SecurityRoleResponse> =
        api.installDefaultSecurityRoles()

    suspend fun createBlankRole(
        key: String,
        name: String,
        description: String?,
        assignmentScope: String = "project",
    ): SecurityRoleResponse = api.createSecurityRole(
        SecurityRoleCreateRequest(
            key = key,
            name = name,
            description = description,
            assignmentScope = assignmentScope,
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
        representedPartyId: String? = null,
    ): SecurityMembershipResponse = api.createSecurityMembership(
        SecurityMembershipCreateRequest(
            primaryEmail = email,
            displayName = displayName,
            kind = kind,
            status = status,
            roleIds = roleIds.sorted(),
            representedPartyId = representedPartyId,
        )
    )

    suspend fun replaceMembershipRoles(
        membershipId: String,
        roleIds: Set<String>,
    ): SecurityMembershipResponse = api.replaceSecurityMembershipRoles(
        membershipId,
        SecurityMembershipRoleSetRequest(roleIds.sorted()),
    )

    suspend fun updateMembershipParty(
        membershipId: String,
        partyId: String?,
    ): SecurityMembershipResponse = api.updateSecurityMembershipParty(
        membershipId,
        SecurityMembershipPartyRequest(partyId),
    )

    suspend fun updateMembershipStatus(
        membershipId: String,
        status: String,
    ): SecurityMembershipResponse = api.updateSecurityMembershipStatus(
        membershipId,
        SecurityMembershipStatusRequest(status),
    )
}

data class AccessAdminSnapshot(
    val roles: List<SecurityRoleResponse>,
    val templates: List<SecurityRoleTemplateResponse>,
    val permissions: List<SecurityPermissionResponse>,
    val memberships: List<SecurityMembershipResponse>,
    val partyReferences: List<SecurityPartyReferenceResponse>,
)
