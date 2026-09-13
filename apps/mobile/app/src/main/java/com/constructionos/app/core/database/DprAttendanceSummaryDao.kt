package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface DprAttendanceSummaryDao {
    @Query(
        """
        SELECT * FROM dpr_attendance_summary
        WHERE project_id = :projectId
          AND attendance_date = :attendanceDate
          AND shift_code = :shiftCode
        ORDER BY position, group_key
        """,
    )
    fun observeSummary(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    ): Flow<List<DprAttendanceSummaryEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(rows: List<DprAttendanceSummaryEntity>)

    @Query(
        """
        DELETE FROM dpr_attendance_summary
        WHERE project_id = :projectId
          AND attendance_date = :attendanceDate
          AND shift_code = :shiftCode
        """,
    )
    suspend fun clearSummary(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    )

    @Transaction
    suspend fun replaceSummary(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
        rows: List<DprAttendanceSummaryEntity>,
    ) {
        clearSummary(projectId, attendanceDate, shiftCode)
        if (rows.isNotEmpty()) insertAll(rows)
    }
}
