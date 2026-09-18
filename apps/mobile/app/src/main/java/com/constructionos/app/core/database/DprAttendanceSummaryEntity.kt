package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index

@Entity(
    tableName = "dpr_attendance_summary",
    primaryKeys = ["register_id", "group_key"],
    indices = [
        Index(value = ["project_id", "attendance_date", "shift_code", "position"]),
    ],
)
data class DprAttendanceSummaryEntity(
    @ColumnInfo(name = "register_id") val registerId: String,
    @ColumnInfo(name = "group_key") val groupKey: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "attendance_date") val attendanceDate: String,
    @ColumnInfo(name = "shift_code") val shiftCode: String,
    @ColumnInfo(name = "employer_party_id") val employerPartyId: String?,
    @ColumnInfo(name = "crew_id") val crewId: String?,
    val trade: String?,
    @ColumnInfo(name = "worker_count") val workerCount: Int,
    @ColumnInfo(name = "present_count") val presentCount: Int,
    @ColumnInfo(name = "absent_count") val absentCount: Int,
    @ColumnInfo(name = "regular_hours") val regularHours: String,
    @ColumnInfo(name = "overtime_hours") val overtimeHours: String,
    val position: Int,
    @ColumnInfo(name = "refreshed_at") val refreshedAt: Long,
)
