package com.constructionos.app.core.network

import com.google.gson.annotations.SerializedName

data class PartyResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    val code: String,
    val name: String,
    @SerializedName("legal_name") val legalName: String? = null,
    @SerializedName("party_type") val partyType: String,
    val status: String,
    val email: String? = null,
    val phone: String? = null,
    @SerializedName("address_line_1") val addressLine1: String? = null,
    @SerializedName("address_line_2") val addressLine2: String? = null,
    val locality: String? = null,
    @SerializedName("state_name") val stateName: String? = null,
    @SerializedName("postal_code") val postalCode: String? = null,
    val revision: Int,
)

data class ProjectPartyAssignmentResponse(
    val id: String,
    @SerializedName("organization_id") val organizationId: String,
    @SerializedName("project_id") val projectId: String,
    @SerializedName("party_id") val partyId: String,
    val role: String,
    val active: Boolean,
    @SerializedName("updated_at") val updatedAt: String,
)
