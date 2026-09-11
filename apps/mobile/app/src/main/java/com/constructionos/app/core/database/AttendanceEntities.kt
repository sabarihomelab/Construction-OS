package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "attendance_roster",
    indices = [Index(value = ["project_id", "status"])],
)
data class AttendanceRosterEntity(
    @PrimaryKey
    @ColumnInfo(name = "assignment_id") val assignmentId: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "worker_id") val workerId: String,
    @ColumnInfo(name = "worker_number") val workerNumber: String,
    @ColumnInfo(name = "worker_name") val workerName: String,
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

@Entity(
    tableName = "attendance_registers",
    indices = [
        Index(value = ["project_id", "attendance_date", "shift_code"], unique = true),
    ],
)
data class AttendanceRegisterEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "attendance_date") val attendanceDate: String,
    @ColumnInfo(name = "shift_code") val shiftCode: String,
    val status: String,
    val revision: Int,
    val notes: String?,
    @ColumnInfo(name = "sync_state") val syncState: String,
    @ColumnInfo(name = "server_updated_at") val serverUpdatedAt: String?,
    @ColumnInfo(name = "local_updated_at") val localUpdatedAt: Long,
)

@Entity(
    tableName = "attendance_entries",
    primaryKeys = ["register_id", "assignment_id"],
    indices = [Index(value = ["register_id"])],
)
data class AttendanceEntryEntity(
    @ColumnInfo(name = "register_id") val registerId: String,
    @ColumnInfo(name = "assignment_id") val assignmentId: String,
    @ColumnInfo(name = "server_entry_id") val serverEntryId: String?,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "worker_id") val workerId: String,
    @ColumnInfo(name = "worker_number") val workerNumber: String,
    @ColumnInfo(name = "worker_name") val workerName: String,
    @ColumnInfo(name = "crew_id") val crewId: String?,
    @ColumnInfo(name = "employer_party_id") val employerPartyId: String?,
    val trade: String?,
    @ColumnInfo(name = "mark_status") val markStatus: String,
    @ColumnInfo(name = "regular_hours") val regularHours: String,
    @ColumnInfo(name = "overtime_hours") val overtimeHours: String,
    @ColumnInfo(name = "wbs_code_id") val wbsCodeId: String?,
    val location: String?,
    val notes: String?,
    @ColumnInfo(name = "sync_state") val syncState: String,
    @ColumnInfo(name = "local_updated_at") val localUpdatedAt: Long,
)

@Entity(
    tableName = "attendance_mutations",
    indices = [
        Index(value = ["project_id", "state"]),
        Index(value = ["entity_id", "operation", "state"]),
    ],
)
data class AttendanceMutationEntity(
    @PrimaryKey
    @ColumnInfo(name = "client_mutation_id") val clientMutationId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "entity_id") val entityId: String,
    val operation: String,
    @ColumnInfo(name = "base_revision") val baseRevision: Int?,
    @ColumnInfo(name = "payload_json") val payloadJson: String,
    val state: String,
    @ColumnInfo(name = "error_code") val errorCode: String?,
    @ColumnInfo(name = "attempt_count") val attemptCount: Int,
    @ColumnInfo(name = "created_at") val createdAt: Long,
    @ColumnInfo(name = "updated_at") val updatedAt: Long,
)

object AttendanceSyncState {
    const val SAVED_ON_DEVICE = "saved_on_device"
    const val WAITING_FOR_NETWORK = "waiting_for_network"
    const val SYNCING = "syncing"
    const val SYNCED = "synced"
    const val NEEDS_ATTENTION = "needs_attention"
}

object AttendanceMutationState {
    const val PENDING = "pending"
    const val IN_FLIGHT = "in_flight"
    const val APPLIED = "applied"
    const val CONFLICT = "conflict"
    const val REJECTED = "rejected"
}
