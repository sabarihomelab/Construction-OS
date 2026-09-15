package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "wbs_codes",
    indices = [
        Index(value = ["project_id", "tree_order"]),
        Index(value = ["project_id", "code"]),
        Index(value = ["project_id", "parent_id"]),
    ],
)
data class WbsEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "parent_id") val parentId: String?,
    val code: String,
    val name: String,
    val kind: String,
    val status: String,
    val description: String?,
    val revision: Int,
    val depth: Int,
    @ColumnInfo(name = "path_codes") val pathCodes: String,
    @ColumnInfo(name = "child_count") val childCount: Int,
    @ColumnInfo(name = "tree_order") val treeOrder: Int,
)
