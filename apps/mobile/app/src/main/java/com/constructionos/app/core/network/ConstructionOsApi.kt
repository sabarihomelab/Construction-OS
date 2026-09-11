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
