package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface DprDao {
    @Query(
        """
        SELECT * FROM dpr_reports
        WHERE project_id = :projectId AND report_date = :reportDate
        ORDER BY shift_code
        """,
    )
    fun observeDay(projectId: String, reportDate: String): Flow<List<DprReportEntity>>

    @Query(
        """
        SELECT * FROM dpr_reports
        WHERE project_id = :projectId
        ORDER BY report_date DESC, shift_code, id
        """,
    )
    fun observeProjectReports(projectId: String): Flow<List<DprReportEntity>>

    @Query(
        """
        SELECT * FROM dpr_reports
        WHERE project_id = :projectId AND report_date = :reportDate AND shift_code = :shiftCode
        LIMIT 1
        """,
    )
    suspend fun report(projectId: String, reportDate: String, shiftCode: String): DprReportEntity?

    @Query("SELECT * FROM dpr_reports WHERE id = :reportId LIMIT 1")
    suspend fun reportById(reportId: String): DprReportEntity?

    @Upsert
    suspend fun upsertReport(report: DprReportEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertMutation(mutation: DprMutationEntity)

    @Query(
        """
        SELECT * FROM dpr_mutations
        WHERE state = :state
        ORDER BY created_at, client_mutation_id
        LIMIT :limit
        """,
    )
    suspend fun mutationsByState(
        state: String = DprMutationState.PENDING,
        limit: Int = 50,
    ): List<DprMutationEntity>

    @Query("UPDATE dpr_mutations SET state = 'pending' WHERE state = 'in_flight'")
    suspend fun recoverInterruptedMutations()

    @Query(
        """
        UPDATE dpr_mutations
        SET state = :state,
            error_code = :errorCode,
            attempt_count = :attemptCount,
            updated_at = :updatedAt
        WHERE client_mutation_id = :mutationId
        """,
    )
    suspend fun updateMutationState(
        mutationId: String,
        state: String,
        errorCode: String?,
        attemptCount: Int,
        updatedAt: Long,
    )

    @Query(
        """
        UPDATE dpr_reports
        SET sync_state = :syncState,
            local_updated_at = :updatedAt
        WHERE id = :reportId
        """,
    )
    suspend fun updateReportSyncState(reportId: String, syncState: String, updatedAt: Long)

    @Transaction
    suspend fun createLocalDraft(report: DprReportEntity, mutation: DprMutationEntity) {
        upsertReport(report)
        upsertMutation(mutation)
    }

    @Transaction
    suspend fun markInFlight(mutation: DprMutationEntity, updatedAt: Long) {
        updateMutationState(
            mutationId = mutation.clientMutationId,
            state = DprMutationState.IN_FLIGHT,
            errorCode = null,
            attemptCount = mutation.attemptCount + 1,
            updatedAt = updatedAt,
        )
        updateReportSyncState(mutation.reportId, DprSyncState.SYNCING, updatedAt)
    }

    @Transaction
    suspend fun resetPending(mutation: DprMutationEntity, updatedAt: Long) {
        updateMutationState(
            mutationId = mutation.clientMutationId,
            state = DprMutationState.PENDING,
            errorCode = null,
            attemptCount = mutation.attemptCount + 1,
            updatedAt = updatedAt,
        )
        updateReportSyncState(mutation.reportId, DprSyncState.WAITING_FOR_NETWORK, updatedAt)
    }

    @Transaction
    suspend fun markNeedsAttention(
        mutation: DprMutationEntity,
        mutationState: String,
        errorCode: String?,
        updatedAt: Long,
    ) {
        updateMutationState(
            mutationId = mutation.clientMutationId,
            state = mutationState,
            errorCode = errorCode,
            attemptCount = mutation.attemptCount + 1,
            updatedAt = updatedAt,
        )
        updateReportSyncState(mutation.reportId, DprSyncState.NEEDS_ATTENTION, updatedAt)
    }

    @Transaction
    suspend fun applyCreate(
        mutation: DprMutationEntity,
        serverReport: DprReportEntity,
        updatedAt: Long,
    ) {
        upsertReport(serverReport.copy(id = mutation.reportId, localUpdatedAt = updatedAt))
        updateMutationState(
            mutationId = mutation.clientMutationId,
            state = DprMutationState.APPLIED,
            errorCode = null,
            attemptCount = mutation.attemptCount + 1,
            updatedAt = updatedAt,
        )
    }
}
