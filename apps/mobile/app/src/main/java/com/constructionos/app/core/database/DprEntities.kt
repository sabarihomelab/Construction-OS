package com.constructionos.app.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "dpr_reports",
    indices = [
        Index(value = ["project_id", "report_date", "shift_code"], unique = true),
        Index(value = ["server_id"], unique = true),
        Index(value = ["project_id", "status", "report_date"]),
    ],
)
data class DprReportEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "server_id") val serverId: String?,
    @ColumnInfo(name = "organization_id") val organizationId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "report_date") val reportDate: String,
    @ColumnInfo(name = "shift_code") val shiftCode: String,
    val status: String,
    val revision: Int,
    @ColumnInfo(name = "weather_condition") val weatherCondition: String?,
    @ColumnInfo(name = "temperature_low") val temperatureLow: String?,
    @ColumnInfo(name = "temperature_high") val temperatureHigh: String?,
    @ColumnInfo(name = "temperature_unit") val temperatureUnit: String?,
    val notes: String?,
    @ColumnInfo(name = "sync_state") val syncState: String,
    @ColumnInfo(name = "server_updated_at") val serverUpdatedAt: String?,
    @ColumnInfo(name = "local_updated_at") val localUpdatedAt: Long,
)

@Entity(
    tableName = "dpr_mutations",
    indices = [
        Index(value = ["project_id", "state"]),
        Index(value = ["report_id", "operation", "state"]),
    ],
)
data class DprMutationEntity(
    @PrimaryKey
    @ColumnInfo(name = "client_mutation_id") val clientMutationId: String,
    @ColumnInfo(name = "project_id") val projectId: String,
    @ColumnInfo(name = "report_id") val reportId: String,
    val operation: String,
    @ColumnInfo(name = "payload_json") val payloadJson: String,
    val state: String,
    @ColumnInfo(name = "error_code") val errorCode: String?,
    @ColumnInfo(name = "attempt_count") val attemptCount: Int,
    @ColumnInfo(name = "created_at") val createdAt: Long,
    @ColumnInfo(name = "updated_at") val updatedAt: Long,
)

object DprSyncState {
    const val SAVED_ON_DEVICE = "saved_on_device"
    const val WAITING_FOR_NETWORK = "waiting_for_network"
    const val SYNCING = "syncing"
    const val SYNCED = "synced"
    const val NEEDS_ATTENTION = "needs_attention"
}

object DprMutationState {
    const val PENDING = "pending"
    const val IN_FLIGHT = "in_flight"
    const val APPLIED = "applied"
    const val CONFLICT = "conflict"
    const val REJECTED = "rejected"
}
