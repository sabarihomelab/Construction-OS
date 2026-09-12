package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "boq_field_items",
    indices = [
        Index(value = ["project_id", "sort_order"]),
        Index(value = ["project_id", "boq_id"]),
        Index(value = ["project_id", "item_code"]),
        Index(value = ["project_id", "wbs_code_id"]),
    ],
)
data class BoqFieldEntity(
    @PrimaryKey @ColumnInfo(name = "item_id") val itemId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "boq_id") val boqId: String,
    @ColumnInfo(name = "boq_code") val boqCode: String,
    @ColumnInfo(name = "boq_name") val boqName: String,
    @ColumnInfo(name = "boq_revision") val boqRevision: Int,
    @ColumnInfo(name = "wbs_code_id") val wbsCodeId: String?,
    @ColumnInfo(name = "line_number") val lineNumber: Int,
    @ColumnInfo(name = "item_code") val itemCode: String,
    val description: String,
    @ColumnInfo(name = "unit_code") val unitCode: String,
    val quantity: String,
    @ColumnInfo(name = "item_revision") val itemRevision: Int,
    @ColumnInfo(name = "sort_order") val sortOrder: Int,
)
