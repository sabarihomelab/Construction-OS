package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "workforce_workers",
    indices = [
        Index(value = ["organization_id", "worker_number"], unique = true),
        Index(value = ["organization_id", "status"]),
    ],
)
data class WorkforceWorkerEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    @ColumnInfo(name = "worker_number") val workerNumber: String,
    @ColumnInfo(name = "display_name") val displayName: String,
    @ColumnInfo(name = "job_title") val jobTitle: String?,
    val trade: String?,
    val status: String,
    val revision: Int,
)

@Entity(
    tableName = "workforce_crews",
    indices = [
        Index(value = ["organization_id", "name"]),
        Index(value = ["organization_id", "status"]),
    ],
)
data class WorkforceCrewEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    val name: String,
    @ColumnInfo(name = "supervisor_worker_id") val supervisorWorkerId: String?,
    val status: String,
    val revision: Int,
)

@Entity(
    tableName = "workforce_assignments",
    indices = [
        Index(value = ["project_id", "worker_id"]),
        Index(value = ["project_id", "crew_id"]),
        Index(value = ["project_id", "status"]),
    ],
)
data class WorkforceAssignmentEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "worker_id") val workerId: String,
    @ColumnInfo(name = "crew_id") val crewId: String?,
    @ColumnInfo(name = "employer_party_id") val employerPartyId: String?,
    @ColumnInfo(name = "engagement_type") val engagementType: String?,
    val status: String,
    @ColumnInfo(name = "project_role") val projectRole: String?,
    val trade: String?,
    @ColumnInfo(name = "default_cost_code") val defaultCostCode: String?,
    @ColumnInfo(name = "start_date") val startDate: String?,
    @ColumnInfo(name = "end_date") val endDate: String?,
    val revision: Int,
)

data class WorkforceWorkerDirectoryRow(
    @ColumnInfo(name = "assignment_id") val assignmentId: String,
    @ColumnInfo(name = "worker_id") val workerId: String,
    @ColumnInfo(name = "worker_number") val workerNumber: String,
    @ColumnInfo(name = "display_name") val displayName: String,
    @ColumnInfo(name = "worker_status") val workerStatus: String,
    @ColumnInfo(name = "assignment_status") val assignmentStatus: String,
    @ColumnInfo(name = "job_title") val jobTitle: String?,
    val trade: String?,
    @ColumnInfo(name = "project_role") val projectRole: String?,
    @ColumnInfo(name = "crew_id") val crewId: String?,
    @ColumnInfo(name = "crew_name") val crewName: String?,
    @ColumnInfo(name = "engagement_type") val engagementType: String?,
    @ColumnInfo(name = "default_cost_code") val defaultCostCode: String?,
    @ColumnInfo(name = "start_date") val startDate: String?,
    @ColumnInfo(name = "end_date") val endDate: String?,
)

data class WorkforceCrewDirectoryRow(
    val id: String,
    val name: String,
    val status: String,
    @ColumnInfo(name = "supervisor_name") val supervisorName: String?,
    @ColumnInfo(name = "assigned_count") val assignedCount: Int,
)
