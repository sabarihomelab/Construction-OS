package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprAttendanceSummaryDao
import com.constructionos.app.core.database.DprAttendanceSummaryEntity
import com.constructionos.app.core.network.AttendanceDprSummaryRowResponse
import com.constructionos.app.core.network.DprAttendanceApi
import kotlinx.coroutines.flow.Flow
import retrofit2.HttpException

class DprAttendanceSummaryRepository(
    private val api: DprAttendanceApi,
    private val dao: DprAttendanceSummaryDao,
) {
    fun observe(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    ): Flow<List<DprAttendanceSummaryEntity>> =
        dao.observeSummary(projectId, attendanceDate, shiftCode)

    suspend fun refresh(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    ): DprAttendanceRefreshResult {
        val response = try {
            api.dprSummary(projectId, attendanceDate, shiftCode)
        } catch (error: HttpException) {
            if (error.code() == 404 || error.code() == 422) {
                dao.clearSummary(projectId, attendanceDate, shiftCode)
                return DprAttendanceRefreshResult.NO_APPROVED_ATTENDANCE
            }
            throw error
        }

        require(response.registerId.isNotBlank()) { "Attendance summary register is missing." }
        require(response.projectId == projectId) { "Attendance summary project mismatch." }
        require(response.attendanceDate == attendanceDate) { "Attendance summary date mismatch." }
        require(response.shiftCode == shiftCode) { "Attendance summary shift mismatch." }

        val refreshedAt = System.currentTimeMillis()
        val rows = response.rows.mapIndexed { index, row ->
            row.requireValid().toEntity(
                registerId = response.registerId,
                projectId = response.projectId,
                attendanceDate = response.attendanceDate,
                shiftCode = response.shiftCode,
                position = index,
                refreshedAt = refreshedAt,
            )
        }
        dao.replaceSummary(projectId, attendanceDate, shiftCode, rows)
        return DprAttendanceRefreshResult.UPDATED
    }
}

enum class DprAttendanceRefreshResult {
    UPDATED,
    NO_APPROVED_ATTENDANCE,
}

private fun AttendanceDprSummaryRowResponse.requireValid(): AttendanceDprSummaryRowResponse {
    require(workerCount >= 0) { "Attendance summary worker count is invalid." }
    require(presentCount >= 0) { "Attendance summary present count is invalid." }
    require(absentCount >= 0) { "Attendance summary absent count is invalid." }
    require(presentCount + absentCount <= workerCount) {
        "Attendance summary counts are inconsistent."
    }
    regularHours.toBigDecimalOrNull()
        ?: throw IllegalArgumentException("Attendance summary regular hours are invalid.")
    overtimeHours.toBigDecimalOrNull()
        ?: throw IllegalArgumentException("Attendance summary overtime hours are invalid.")
    return this
}

private fun AttendanceDprSummaryRowResponse.toEntity(
    registerId: String,
    projectId: String,
    attendanceDate: String,
    shiftCode: String,
    position: Int,
    refreshedAt: Long,
): DprAttendanceSummaryEntity = DprAttendanceSummaryEntity(
    registerId = registerId,
    groupKey = listOf(
        employerPartyId.orEmpty(),
        crewId.orEmpty(),
        trade.orEmpty(),
    ).joinToString("\u001f"),
    projectId = projectId,
    attendanceDate = attendanceDate,
    shiftCode = shiftCode,
    employerPartyId = employerPartyId,
    crewId = crewId,
    trade = trade,
    workerCount = workerCount,
    presentCount = presentCount,
    absentCount = absentCount,
    regularHours = regularHours,
    overtimeHours = overtimeHours,
    position = position,
    refreshedAt = refreshedAt,
)
