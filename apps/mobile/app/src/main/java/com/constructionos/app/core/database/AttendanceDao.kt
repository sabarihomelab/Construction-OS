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
    suspend fun activeRoster(projectId: String, attendanceDate: String): List<AttendanceRosterEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRoster(entries: List<AttendanceRosterEntity>)

    @Query("DELETE FROM attendance_roster WHERE project_id = :projectId")
    suspend fun clearRoster(projectId: String)

    @Transaction
    suspend fun replaceRoster(projectId: String, entries: List<AttendanceRosterEntity>) {
        clearRoster(projectId)
        upsertRoster(entries)
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
        upsertEntries(entries)
    }

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
}
