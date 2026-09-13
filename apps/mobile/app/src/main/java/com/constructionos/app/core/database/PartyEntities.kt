package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "parties",
    indices = [
        Index(value = ["organization_id", "name"]),
        Index(value = ["organization_id", "code"], unique = true),
    ],
)
data class PartyEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    val code: String,
    val name: String,
    @ColumnInfo(name = "legal_name") val legalName: String?,
    @ColumnInfo(name = "party_type") val partyType: String,
    val status: String,
    val email: String?,
    val phone: String?,
    @ColumnInfo(name = "address_line_1") val addressLine1: String?,
    @ColumnInfo(name = "address_line_2") val addressLine2: String?,
    val locality: String?,
    @ColumnInfo(name = "state_name") val stateName: String?,
    @ColumnInfo(name = "postal_code") val postalCode: String?,
    val revision: Int,
)

@Entity(
    tableName = "project_party_assignments",
    indices = [
        Index(value = ["project_id", "party_id"]),
        Index(value = ["project_id", "role"]),
    ],
)
data class ProjectPartyAssignmentEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "party_id") val partyId: String,
    val role: String,
    val active: Boolean,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)
