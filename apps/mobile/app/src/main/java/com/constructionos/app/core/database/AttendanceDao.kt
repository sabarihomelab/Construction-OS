package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface AttendanceDao {
    @Query(
        """
        SELECT * FROM attendance_roster
        WHERE project_id = :projectId
          AND status = 'active'
          AND (start_date IS NULL OR start_date <= :attendanceDate)
          AND (end_date IS NULL OR end_date >= :attendanceDate)
        ORDER BY COALESCE(trade, ''), worker_name, worker_number
        """,
    )
    fun observeActiveRoster(projectId: String, attendanceDate: String): Flow<List<AttendanceRosterEntity>>

    @Query(
        """
        SELECT * FROM attendance_roster
        WHERE project_id = :projectId
          AND status = 'active'
          AND (start_date IS NULL OR start_date <= :attendanceDate)
          AND (end_date IS NULL OR end_date >= :attendanceDate)
        ORDER BY COALESCE(trade, ''), worker_name, worker_number
        """,
    )
    suspend fun activeRoster(projectId: String, attendanceDate: String): List<AttendanceRosterEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRoster(entries: List<AttendanceRosterEntity>)

    @Query("DELETE FROM attendance_roster WHERE project_id = :projectId")
    suspend fun clearRoster(projectId: String)

    @Transaction
    suspend fun replaceRoster(projectId: String, entries: List<AttendanceRosterEntity>) {
        clearRoster(projectId)
        if (entries.isNotEmpty()) upsertRoster(entries)
    }

    @Query(
        """
        SELECT * FROM attendance_registers
        WHERE project_id = :projectId
          AND attendance_date = :attendanceDate
        ORDER BY shift_code
        """,
    )
    fun observeRegisters(projectId: String, attendanceDate: String): Flow<List<AttendanceRegisterEntity>>

    @Query(
        """
        SELECT * FROM attendance_registers
        WHERE project_id = :projectId
          AND attendance_date = :attendanceDate
          AND shift_code = :shiftCode
        LIMIT 1
        """,
    )
    suspend fun register(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    ): AttendanceRegisterEntity?

    @Query("SELECT * FROM attendance_registers WHERE id = :registerId LIMIT 1")
    suspend fun registerById(registerId: String): AttendanceRegisterEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRegister(register: AttendanceRegisterEntity)

    @Query("DELETE FROM attendance_registers WHERE id = :registerId")
    suspend fun deleteRegister(registerId: String)

    @Query(
        """
        SELECT * FROM attendance_registers r
        WHERE r.revision > 0
          AND r.status IN ('draft', 'rejected')
          AND EXISTS (
              SELECT 1 FROM attendance_entries e
              WHERE e.register_id = r.id
                AND e.sync_state = 'saved_on_device'
          )
        ORDER BY r.local_updated_at
        """,
    )
    suspend fun dirtyEditableRegisters(): List<AttendanceRegisterEntity>

    @Query(
        """
        UPDATE attendance_registers
        SET sync_state = :syncState,
            local_updated_at = :updatedAt
        WHERE id = :registerId
        """,
    )
    suspend fun updateRegisterSyncState(registerId: String, syncState: String, updatedAt: Long)

    @Query(
        """
        UPDATE attendance_registers
        SET status = :status,
            revision = :revision,
            sync_state = :syncState,
            server_updated_at = :serverUpdatedAt,
            local_updated_at = :localUpdatedAt
        WHERE id = :registerId
        """,
    )
    suspend fun updateRegisterFromServer(
        registerId: String,
        status: String,
        revision: Int,
        syncState: String,
        serverUpdatedAt: String?,
        localUpdatedAt: Long,
    )

    @Query(
        """
        SELECT * FROM attendance_entries
        WHERE register_id = :registerId
        ORDER BY COALESCE(trade, ''), worker_name, worker_number
        """,
    )
    fun observeEntries(registerId: String): Flow<List<AttendanceEntryEntity>>

    @Query("SELECT * FROM attendance_entries WHERE register_id = :registerId")
    suspend fun entries(registerId: String): List<AttendanceEntryEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertEntries(entries: List<AttendanceEntryEntity>)

    @Query("DELETE FROM attendance_entries WHERE register_id = :registerId")
    suspend fun clearEntries(registerId: String)

    @Transaction
    suspend fun replaceEntries(registerId: String, entries: List<AttendanceEntryEntity>) {
        clearEntries(registerId)
        if (entries.isNotEmpty()) upsertEntries(entries)
    }

    @Query(
        """
        UPDATE attendance_entries
        SET mark_status = :markStatus,
            regular_hours = CASE
                WHEN :markStatus IN ('not_marked', 'absent', 'leave', 'weekly_off') THEN '0'
                ELSE regular_hours
            END,
            overtime_hours = CASE
                WHEN :markStatus IN ('not_marked', 'absent', 'leave', 'weekly_off') THEN '0'
                ELSE overtime_hours
            END,
            sync_state = 'saved_on_device',
            local_updated_at = :updatedAt
        WHERE register_id = :registerId
        """,
    )
    suspend fun markAllLocally(registerId: String, markStatus: String, updatedAt: Long)

    @Query(
        """
        UPDATE attendance_entries
        SET mark_status = :markStatus,
            regular_hours = CASE
                WHEN :markStatus IN ('not_marked', 'absent', 'leave', 'weekly_off') THEN '0'
                ELSE regular_hours
            END,
            overtime_hours = CASE
                WHEN :markStatus IN ('not_marked', 'absent', 'leave', 'weekly_off') THEN '0'
                ELSE overtime_hours
            END,
            sync_state = 'saved_on_device',
            local_updated_at = :updatedAt
        WHERE register_id = :registerId
          AND assignment_id = :assignmentId
        """,
    )
    suspend fun markEntryLocally(
        registerId: String,
        assignmentId: String,
        markStatus: String,
        updatedAt: Long,
    )

    @Query(
        """
        UPDATE attendance_entries
        SET sync_state = 'synced'
        WHERE register_id = :registerId
          AND local_updated_at < :snapshotAt
        """,
    )
    suspend fun markEntriesSyncedBefore(registerId: String, snapshotAt: Long)

    @Query(
        """
        SELECT COUNT(*) FROM attendance_entries
        WHERE register_id = :registerId
          AND sync_state = 'saved_on_device'
        """,
    )
    suspend fun dirtyEntryCount(registerId: String): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertMutation(mutation: AttendanceMutationEntity)

    @Query(
        """
        SELECT * FROM attendance_mutations
        WHERE state = 'pending'
        ORDER BY created_at
        LIMIT :limit
        """,
    )
    suspend fun pendingMutations(limit: Int = 50): List<AttendanceMutationEntity>

    @Query(
        """
        SELECT COUNT(*) FROM attendance_mutations
        WHERE entity_id = :entityId
          AND operation = :operation
          AND state IN ('pending', 'in_flight')
        """,
    )
    suspend fun activeMutationCount(entityId: String, operation: String): Int

    @Query("UPDATE attendance_mutations SET state = 'pending' WHERE state = 'in_flight'")
    suspend fun recoverInterruptedMutations()

    @Query(
        """
        UPDATE attendance_mutations
        SET state = :state,
            error_code = :errorCode,
            attempt_count = :attemptCount,
            updated_at = :updatedAt
        WHERE client_mutation_id = :clientMutationId
        """,
    )
    suspend fun updateMutationState(
        clientMutationId: String,
        state: String,
        errorCode: String?,
        attemptCount: Int,
        updatedAt: Long,
    )

    @Query(
        """
        UPDATE attendance_mutations
        SET entity_id = :entityId,
            state = :state,
            error_code = :errorCode,
            attempt_count = :attemptCount,
            updated_at = :updatedAt
        WHERE client_mutation_id = :clientMutationId
        """,
    )
    suspend fun finishMutation(
        clientMutationId: String,
        entityId: String,
        state: String,
        errorCode: String?,
        attemptCount: Int,
        updatedAt: Long,
    )

    @Query(
        """
        SELECT COUNT(*) FROM attendance_mutations
        WHERE project_id = :projectId
          AND state IN ('pending', 'in_flight')
        """,
    )
    fun observePendingMutationCount(projectId: String): Flow<Int>

    @Query(
        """
        SELECT COUNT(*) FROM attendance_mutations
        WHERE project_id = :projectId
          AND state IN ('conflict', 'rejected')
        """,
    )
    fun observeAttentionCount(projectId: String): Flow<Int>

    @Transaction
    suspend fun createLocalRegister(
        register: AttendanceRegisterEntity,
        entries: List<AttendanceEntryEntity>,
        mutation: AttendanceMutationEntity,
    ) {
        upsertRegister(register)
        if (entries.isNotEmpty()) upsertEntries(entries)
        upsertMutation(mutation)
    }

    @Transaction
    suspend fun markAllAndDirty(registerId: String, markStatus: String, updatedAt: Long) {
        markAllLocally(registerId, markStatus, updatedAt)
        updateRegisterSyncState(registerId, AttendanceSyncState.SAVED_ON_DEVICE, updatedAt)
    }

    @Transaction
    suspend fun markEntryAndDirty(
        registerId: String,
        assignmentId: String,
        markStatus: String,
        updatedAt: Long,
    ) {
        markEntryLocally(registerId, assignmentId, markStatus, updatedAt)
        updateRegisterSyncState(registerId, AttendanceSyncState.SAVED_ON_DEVICE, updatedAt)
    }

    @Transaction
    suspend fun replaceRegisterIdentity(
        oldRegisterId: String,
        register: AttendanceRegisterEntity,
        entries: List<AttendanceEntryEntity>,
    ) {
        clearEntries(oldRegisterId)
        deleteRegister(oldRegisterId)
        upsertRegister(register)
        if (entries.isNotEmpty()) upsertEntries(entries)
    }

    @Transaction
    suspend fun cacheServerRegister(
        register: AttendanceRegisterEntity,
        entries: List<AttendanceEntryEntity>,
    ) {
        upsertRegister(register)
        replaceEntries(register.id, entries)
    }
}
