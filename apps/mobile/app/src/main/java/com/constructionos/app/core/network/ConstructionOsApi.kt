package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface ConstructionOsApi {
    @GET("auth/native/providers")
    suspend fun nativeProviders(): NativeProviderListResponse

    @POST("auth/native/authenticate")
    suspend fun authenticateNative(
        @Body request: NativeAuthenticationRequest,
    ): NativeAuthenticationResponse

    @POST("auth/native/select-membership")
    suspend fun selectMembership(
        @Body request: NativeMembershipSelectionRequest,
    ): NativeAuthenticationResponse

    @GET("session/context")
    suspend fun sessionContext(): SessionContextResponse

    @POST("session/logout")
    suspend fun logout(): Response<Unit>

    @GET("projects")
    suspend fun projects(): List<ProjectResponse>

    @POST("offline/devices")
    suspend fun registerDevice(
        @Body request: DeviceRegistrationRequest,
    ): ClientDeviceResponse
}

data class NativeProviderListResponse(
    val providers: List<String> = emptyList(),
)

data class NativeAuthenticationRequest(
    @SerializedName("provider_key") val providerKey: String,
    val payload: Map<String, String>,
)

data class NativeMembershipSelectionRequest(
    @SerializedName("grant_token") val grantToken: String,
    @SerializedName("membership_id") val membershipId: String,
)

data class NativeMembershipOption(
    @SerializedName("membership_id") val membershipId: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("organization_name") val organizationName: String,
)

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
    val key: String,
    val name: String,
    val kind: String,
    @SerializedName("parent_key") val parentKey: String? = null,
    val route: String? = null,
    val sensitivity: String,
    @SerializedName("display_order") val displayOrder: Int,
    @SerializedName("mobile_enabled") val mobileEnabled: Boolean,
    @SerializedName("offline_enabled") val offlineEnabled: Boolean,
    @SerializedName("help_topic") val helpTopic: String? = null,
)

data class ProjectResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    val number: String,
    val name: String,
    val description: String? = null,
    val status: String,
    val revision: Int,
    val timezone: String? = null,
    @SerializedName("currency_code") val currencyCode: String? = null,
    @SerializedName("unit_system") val unitSystem: String? = null,
    @SerializedName("start_date") val startDate: String? = null,
    @SerializedName("target_completion_date") val targetCompletionDate: String? = null,
    @SerializedName("address_line_1") val addressLine1: String? = null,
    @SerializedName("address_line_2") val addressLine2: String? = null,
    val locality: String? = null,
    val region: String? = null,
    @SerializedName("postal_code") val postalCode: String? = null,
    @SerializedName("country_code") val countryCode: String? = null,
)

data class DeviceRegistrationRequest(
    @SerializedName("installation_id") val installationId: String,
    val platform: String = "android",
    @SerializedName("device_label") val deviceLabel: String? = null,
    @SerializedName("app_version") val appVersion: String? = null,
)

data class ClientDeviceResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("user_id") val userId: String,
    @SerializedName("installation_id") val installationId: String,
    val platform: String,
    @SerializedName("device_label") val deviceLabel: String? = null,
    @SerializedName("app_version") val appVersion: String? = null,
    @SerializedName("last_seen_at") val lastSeenAt: String? = null,
    @SerializedName("revoked_at") val revokedAt: String? = null,
)
