package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index

@Entity(
    tableName = "dpr_custom_field_definitions",
    primaryKeys = ["project_id", "definition_id"],
    indices = [
        Index(value = ["project_id", "display_order", "field_key"]),
    ],
)
data class DprCustomFieldDefinitionEntity(
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "definition_id") val definitionId: String,
    @ColumnInfo(name = "field_key") val key: String,
    val label: String,
    val description: String?,
    @ColumnInfo(name = "field_type") val fieldType: String,
    val required: Boolean,
    val editable: Boolean,
    @ColumnInfo(name = "display_order") val displayOrder: Int,
    @ColumnInfo(name = "default_value_json") val defaultValueJson: String?,
    @ColumnInfo(name = "options_json") val optionsJson: String,
    @ColumnInfo(name = "refreshed_at") val refreshedAt: Long,
)

@Entity(
    tableName = "dpr_custom_field_values",
    primaryKeys = ["report_id", "definition_id"],
    indices = [
        Index(value = ["project_id", "report_id"]),
    ],
)
data class DprCustomFieldValueEntity(
    @ColumnInfo(name = "report_id") val reportId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "definition_id") val definitionId: String,
    @ColumnInfo(name = "value_json") val valueJson: String?,
    @ColumnInfo(name = "refreshed_at") val refreshedAt: Long,
)
