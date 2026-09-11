package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "projects")
data class ProjectEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    val number: String,
    val name: String,
    val description: String?,
    val status: String,
    val revision: Int,
    val timezone: String?,
    @ColumnInfo(name = "currency_code") val currencyCode: String?,
    @ColumnInfo(name = "unit_system") val unitSystem: String?,
    @ColumnInfo(name = "start_date") val startDate: String?,
    @ColumnInfo(name = "target_completion_date") val targetCompletionDate: String?,
    @ColumnInfo(name = "address_line_1") val addressLine1: String?,
    @ColumnInfo(name = "address_line_2") val addressLine2: String?,
    val locality: String?,
    val region: String?,
    @ColumnInfo(name = "postal_code") val postalCode: String?,
    @ColumnInfo(name = "country_code") val countryCode: String?,
)
