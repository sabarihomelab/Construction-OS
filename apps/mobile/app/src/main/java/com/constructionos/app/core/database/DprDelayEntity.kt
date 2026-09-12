package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "dpr_delays",
    indices = [Index(value = ["report_id", "position"])],
)
data class DprDelayEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "report_id") val reportId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    val position: Int,
    val category: String?,
    val description: String,
    @ColumnInfo(name = "started_at") val startedAt: String?,
    @ColumnInfo(name = "ended_at") val endedAt: String?,
    @ColumnInfo(name = "lost_hours") val lostHours: String?,
    @ColumnInfo(name = "responsible_party") val responsibleParty: String?,
    @ColumnInfo(name = "schedule_impact") val scheduleImpact: Boolean,
    val notes: String?,
)
