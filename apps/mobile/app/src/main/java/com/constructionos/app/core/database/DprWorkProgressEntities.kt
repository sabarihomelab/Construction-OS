package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "dpr_work_progress",
    indices = [Index(value = ["report_id", "position"])],
)
data class DprWorkProgressEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "report_id") val reportId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    val position: Int,
    @ColumnInfo(name = "wbs_code_id") val wbsCodeId: String?,
    @ColumnInfo(name = "boq_item_id") val boqItemId: String?,
    val description: String,
    val location: String?,
    val quantity: String?,
    @ColumnInfo(name = "unit_code") val unitCode: String?,
    @ColumnInfo(name = "progress_percent") val progressPercent: String?,
    val remarks: String?,
)

@Entity(
    tableName = "dpr_wbs_references",
    indices = [Index(value = ["project_id", "code"])],
)
data class DprWbsReferenceEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    val code: String,
    val name: String,
    val kind: String,
    @ColumnInfo(name = "parent_id") val parentId: String?,
)

@Entity(
    tableName = "dpr_boq_references",
    indices = [Index(value = ["project_id", "boq_code", "item_code"])],
)
data class DprBoqReferenceEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "boq_id") val boqId: String,
    @ColumnInfo(name = "boq_code") val boqCode: String,
    @ColumnInfo(name = "boq_name") val boqName: String,
    @ColumnInfo(name = "wbs_code_id") val wbsCodeId: String?,
    @ColumnInfo(name = "item_code") val itemCode: String,
    val description: String,
    @ColumnInfo(name = "unit_code") val unitCode: String,
)
