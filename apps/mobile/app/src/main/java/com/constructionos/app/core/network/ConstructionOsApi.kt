package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface ConstructionOsApi {
    @GET("deployment/bootstrap") suspend fun deploymentBootstrap(): DeploymentBootstrapResponse
    @GET("auth/native/providers") suspend fun nativeProviders(): NativeProviderListResponse
    @POST("auth/native/authenticate") suspend fun authenticateNative(@Body request: NativeAuthenticationRequest): NativeAuthenticationResponse
    @POST("auth/native/select-membership") suspend fun selectMembership(@Body request: NativeMembershipSelectionRequest): NativeAuthenticationResponse
    @GET("session/context") suspend fun sessionContext(): SessionContextResponse
    @POST("session/logout") suspend fun logout(): Response<Unit>
    @GET("projects") suspend fun projects(): List<ProjectResponse>
    @POST("offline/devices") suspend fun registerDevice(@Body request: DeviceRegistrationRequest): ClientDeviceResponse

    @GET("security/permissions") suspend fun securityPermissions(): List<SecurityPermissionResponse>
    @GET("security/role-templates") suspend fun roleTemplates(): List<SecurityRoleTemplateResponse>
    @GET("security/roles") suspend fun securityRoles(): List<SecurityRoleResponse>
    @POST("security/roles") suspend fun createSecurityRole(@Body request: SecurityRoleCreateRequest): SecurityRoleResponse
    @POST("security/roles/install-defaults") suspend fun installDefaultSecurityRoles(): List<SecurityRoleResponse>
    @POST("security/roles/from-template/{templateKey}")
    suspend fun createRoleFromTemplate(
        @Path("templateKey") templateKey: String,
        @Body request: SecurityRoleFromTemplateRequest,
    ): SecurityRoleResponse
    @GET("security/roles/{roleId}/permissions")
    suspend fun securityRolePermissions(@Path("roleId") roleId: String): SecurityRolePermissionSetResponse
    @PUT("security/roles/{roleId}/permissions")
    suspend fun replaceSecurityRolePermissions(
        @Path("roleId") roleId: String,
        @Body request: SecurityRolePermissionSetRequest,
    ): SecurityRoleResponse
    @GET("security/memberships") suspend fun securityMemberships(): List<SecurityMembershipResponse>
    @POST("security/memberships") suspend fun createSecurityMembership(@Body request: SecurityMembershipCreateRequest): SecurityMembershipResponse
    @PUT("security/memberships/{membershipId}/roles")
    suspend fun replaceSecurityMembershipRoles(
        @Path("membershipId") membershipId: String,
        @Body request: SecurityMembershipRoleSetRequest,
    ): SecurityMembershipResponse
    @PATCH("security/memberships/{membershipId}/status")
    suspend fun updateSecurityMembershipStatus(
        @Path("membershipId") membershipId: String,
        @Body request: SecurityMembershipStatusRequest,
    ): SecurityMembershipResponse

    @GET("configuration/projects/{projectId}/modules/{moduleKey}")
    suspend fun effectiveProjectConfiguration(
        @Path("projectId") projectId: String,
        @Path("moduleKey") moduleKey: String,
    ): EffectiveConfigurationResponse

    @GET("commercial/parties") suspend fun parties(): List<PartyResponse>
    @GET("projects/{projectId}/commercial/party-assignments")
    suspend fun projectPartyAssignments(@Path("projectId") projectId: String): List<ProjectPartyAssignmentResponse>

    @GET("projects/{projectId}/workforce/attendance/roster")
    suspend fun attendanceRoster(@Path("projectId") projectId: String, @Query("attendance_date") attendanceDate: String): List<AttendanceRosterResponse>
    @GET("projects/{projectId}/workforce/attendance") suspend fun attendanceRegisters(@Path("projectId") projectId: String): List<AttendanceRegisterResponse>
    @GET("projects/{projectId}/workforce/attendance/{registerId}") suspend fun attendanceRegister(@Path("projectId") projectId: String, @Path("registerId") registerId: String): AttendanceRegisterDetailResponse
    @POST("projects/{projectId}/workforce/attendance/{registerId}/submit") suspend fun submitAttendance(@Path("projectId") projectId: String, @Path("registerId") registerId: String, @Body request: AttendanceVersionActionRequest): AttendanceRegisterResponse
    @POST("projects/{projectId}/workforce/attendance/{registerId}/approve") suspend fun approveAttendance(@Path("projectId") projectId: String, @Path("registerId") registerId: String, @Body request: AttendanceVersionActionRequest): AttendanceRegisterResponse
    @POST("projects/{projectId}/workforce/attendance/{registerId}/reject") suspend fun rejectAttendance(@Path("projectId") projectId: String, @Path("registerId") registerId: String, @Body request: AttendanceRequiredReasonActionRequest): AttendanceRegisterResponse
    @POST("projects/{projectId}/workforce/attendance/{registerId}/reopen") suspend fun reopenAttendance(@Path("projectId") projectId: String, @Path("registerId") registerId: String, @Body request: AttendanceRequiredReasonActionRequest): AttendanceRegisterResponse
    @POST("projects/{projectId}/workforce/attendance/offline/mutations") suspend fun submitAttendanceMutation(@Path("projectId") projectId: String, @Body request: AttendanceOfflineMutationRequest): Response<AttendanceOfflineMutationResponse>

    @GET("projects/{projectId}/daily-reports") suspend fun dailyReports(@Path("projectId") projectId: String): List<DailyReportResponse>
    @POST("projects/{projectId}/daily-reports") suspend fun createDailyReport(@Path("projectId") projectId: String, @Body request: DailyReportCreateRequest): Response<DailyReportResponse>
    @GET("projects/{projectId}/daily-reports/{reportId}") suspend fun dailyReportDetail(@Path("projectId") projectId: String, @Path("reportId") reportId: String): DailyReportDetailResponse
    @GET("projects/{projectId}/daily-reports/{reportId}/work-progress") suspend fun dprWorkProgress(@Path("projectId") projectId: String, @Path("reportId") reportId: String): List<DprWorkProgressResponse>
    @GET("projects/{projectId}/daily-reports/work-progress/references") suspend fun dprWorkProgressReferences(@Path("projectId") projectId: String): DprWorkProgressReferenceResponse
    @POST("projects/{projectId}/daily-reports/offline/mutations") suspend fun submitDailyReportMutation(@Path("projectId") projectId: String, @Body request: DailyReportOfflineMutationRequest): Response<DailyReportOfflineMutationResponse>
}

data class DeploymentBootstrapResponse(
    @SerializedName("deployment_id") val deploymentId: String,
    @SerializedName("dedicated_company") val dedicatedCompany: Boolean,
    val organization: DeploymentOrganizationResponse? = null,
    val environment: String,
    @SerializedName("environment_name") val environmentName: String,
    @SerializedName("api_path") val apiPath: String,
)

data class DeploymentOrganizationResponse(
    val id: String,
    val name: String,
    val slug: String,
)

data class EffectiveConfigurationResponse(
    val settings: List<ResolvedConfigurationSettingResponse> = emptyList(),
)

data class ResolvedConfigurationSettingResponse(
    val key: String,
    val value: Any? = null,
)

data class NativeProviderListResponse(val providers: List<String> = emptyList())
data class NativeAuthenticationRequest(@SerializedName("provider_key") val providerKey: String, val payload: Map<String, String>)
data class NativeMembershipSelectionRequest(@SerializedName("grant_token") val grantToken: String, @SerializedName("membership_id") val membershipId: String)
data class NativeMembershipOption(@SerializedName("membership_id") val membershipId: String, @SerializedName("organization_id") val organizationId: String, @SerializedName("organization_name") val organizationName: String)

data class NativeAuthenticationResponse(
    val status: String,
    @SerializedName("token_type") val tokenType: String? = null,
    @SerializedName("access_token") val accessToken: String? = null,
    @SerializedName("membership_id") val membershipId: String? = null,
    @SerializedName("grant_token") val grantToken: String? = null,
    val memberships: List<NativeMembershipOption> = emptyList(),
) {
    fun requireBearerToken(): String {
        require(status == STATUS_AUTHENTICATED) { "Authentication is not complete" }
        require(tokenType.equals("Bearer", ignoreCase = true)) { "Unsupported token type" }
        return requireNotNull(accessToken).also { require(it.isNotBlank()) }
    }
    companion object {
        const val STATUS_AUTHENTICATED = "authenticated"
        const val STATUS_MEMBERSHIP_SELECTION = "membership_selection_required"
    }
}

data class SessionContextResponse(
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("membership_id") val membershipId: String,
    @SerializedName("authorization_revision") val authorizationRevision: Int,
    @SerializedName("configuration_revision") val configurationRevision: Int,
    val permissions: List<String> = emptyList(),
    val scopes: Map<String, List<String>> = emptyMap(),
    @SerializedName("project_permissions") val projectPermissions: Map<String, List<String>> = emptyMap(),
    val features: List<VisibleFeatureResponse> = emptyList(),
)

data class VisibleFeatureResponse(
    val key: String, val name: String, val kind: String,
    @SerializedName("parent_key") val parentKey: String? = null,
    val route: String? = null, val sensitivity: String,
    @SerializedName("display_order") val displayOrder: Int,
    @SerializedName("mobile_enabled") val mobileEnabled: Boolean,
    @SerializedName("offline_enabled") val offlineEnabled: Boolean,
    @SerializedName("help_topic") val helpTopic: String? = null,
)

data class ProjectResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    val number: String, val name: String, val description: String? = null, val status: String, val revision: Int,
    val timezone: String? = null,
    @SerializedName("currency_code") val currencyCode: String? = null,
    @SerializedName("unit_system") val unitSystem: String? = null,
    @SerializedName("start_date") val startDate: String? = null,
    @SerializedName("target_completion_date") val targetCompletionDate: String? = null,
    @SerializedName("address_line_1") val addressLine1: String? = null,
    @SerializedName("address_line_2") val addressLine2: String? = null,
    val locality: String? = null, val region: String? = null,
    @SerializedName("postal_code") val postalCode: String? = null,
    @SerializedName("country_code") val countryCode: String? = null,
)

data class SecurityPermissionResponse(
    val key: String,
    val module: String,
    val resource: String,
    val action: String,
    val description: String,
    val risk: String,
)

data class SecurityRoleTemplateResponse(
    val key: String,
    val name: String,
    val description: String,
    @SerializedName("scope_hint") val scopeHint: String,
    @SerializedName("membership_kind_hint") val membershipKindHint: String,
    @SerializedName("permission_keys") val permissionKeys: List<String> = emptyList(),
)

data class SecurityRoleResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String?,
    val key: String,
    val name: String,
    val description: String? = null,
    @SerializedName("is_template") val isTemplate: Boolean,
    @SerializedName("is_protected") val isProtected: Boolean,
    @SerializedName("is_active") val isActive: Boolean,
    val version: Int,
)

data class SecurityRoleCreateRequest(
    val key: String,
    val name: String,
    val description: String? = null,
    @SerializedName("permission_keys") val permissionKeys: List<String> = emptyList(),
)

data class SecurityRoleFromTemplateRequest(
    val key: String? = null,
    val name: String? = null,
)

data class SecurityRolePermissionSetResponse(
    @SerializedName("expected_version") val expectedVersion: Int?,
    @SerializedName("permission_keys") val permissionKeys: List<String> = emptyList(),
)

data class SecurityRolePermissionSetRequest(
    @SerializedName("expected_version") val expectedVersion: Int?,
    @SerializedName("permission_keys") val permissionKeys: List<String>,
)

data class SecurityAssignedRoleResponse(
    val id: String,
    val key: String,
    val name: String,
    @SerializedName("is_template") val isTemplate: Boolean,
    @SerializedName("is_protected") val isProtected: Boolean,
)

data class SecurityMembershipResponse(
    val id: String,
    @SerializedName("user_id") val userId: String,
    @SerializedName("primary_email") val primaryEmail: String,
    @SerializedName("display_name") val displayName: String,
    val kind: String,
    val status: String,
    @SerializedName("role_ids") val roleIds: List<String> = emptyList(),
    val roles: List<SecurityAssignedRoleResponse> = emptyList(),
)

data class SecurityMembershipCreateRequest(
    @SerializedName("primary_email") val primaryEmail: String,
    @SerializedName("display_name") val displayName: String,
    val kind: String = "internal",
    val status: String = "invited",
    @SerializedName("role_ids") val roleIds: List<String> = emptyList(),
)

data class SecurityMembershipRoleSetRequest(
    @SerializedName("role_ids") val roleIds: List<String>,
)

data class SecurityMembershipStatusRequest(val status: String)

data class DeviceRegistrationRequest(@SerializedName("installation_id") val installationId: String, val platform: String = "android", @SerializedName("device_label") val deviceLabel: String? = null, @SerializedName("app_version") val appVersion: String? = null)
data class ClientDeviceResponse(val id: String, @SerializedName("organization_id") val organizationId: String, @SerializedName("user_id") val userId: String, @SerializedName("installation_id") val installationId: String, val platform: String, @SerializedName("device_label") val deviceLabel: String? = null, @SerializedName("app_version") val appVersion: String? = null, @SerializedName("last_seen_at") val lastSeenAt: String? = null, @SerializedName("revoked_at") val revokedAt: String? = null)
