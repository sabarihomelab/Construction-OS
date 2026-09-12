package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprAttendanceSummaryDao
import com.constructionos.app.core.database.DprAttendanceSummaryEntity
import com.constructionos.app.core.network.AttendanceDprSummaryResponse
import com.constructionos.app.core.network.AttendanceDprSummaryRowResponse
import com.constructionos.app.core.network.AttendanceRegisterResponse
import com.constructionos.app.core.network.DprAttendanceApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DprAttendanceSummaryRepositoryTest {
    @Test
    fun `approved attendance summary is cached exactly`() = runBlocking {
        val dao = FakeSummaryDao()
        val api = FakeSummaryApi(
            registers = listOf(approvedRegister()),
            summary = AttendanceDprSummaryResponse(
                registerId = "register-1",
                projectId = "project-1",
                attendanceDate = "2026-09-12",
                shiftCode = "day",
                rows = listOf(
                    AttendanceDprSummaryRowResponse(
                        employerPartyId = "party-1",
                        crewId = "crew-1",
                        trade = "Masonry",
                        workerCount = 12,
                        presentCount = 10,
                        absentCount = 1,
                        regularHours = "80.0",
                        overtimeHours = "6.5",
                    ),
                ),
            ),
        )
        val repository = DprAttendanceSummaryRepository(api, dao)

        val result = repository.refresh("project-1", "2026-09-12", "day")

        assertEquals(DprAttendanceRefreshResult.UPDATED, result)
        assertEquals(1, dao.rows.size)
        val row = dao.rows.single()
        assertEquals("register-1", row.registerId)
        assertEquals("Masonry", row.trade)
        assertEquals(12, row.workerCount)
        assertEquals(10, row.presentCount)
        assertEquals(1, row.absentCount)
        assertEquals("80.0", row.regularHours)
        assertEquals("6.5", row.overtimeHours)
    }

    @Test
    fun `missing approved attendance clears stale cached summary`() = runBlocking {
        val dao = FakeSummaryDao().apply {
            rows = listOf(
                DprAttendanceSummaryEntity(
                    registerId = "old-register",
                    groupKey = "old",
                    projectId = "project-1",
                    attendanceDate = "2026-09-12",
                    shiftCode = "day",
                    employerPartyId = null,
                    crewId = null,
                    trade = "Old",
                    workerCount = 2,
                    presentCount = 2,
                    absentCount = 0,
                    regularHours = "16",
                    overtimeHours = "0",
                    position = 0,
                    refreshedAt = 1L,
                ),
            )
        }
        val api = FakeSummaryApi(registers = emptyList(), summary = null)
        val repository = DprAttendanceSummaryRepository(api, dao)

        val result = repository.refresh("project-1", "2026-09-12", "day")

        assertEquals(DprAttendanceRefreshResult.NO_APPROVED_ATTENDANCE, result)
        assertTrue(dao.rows.isEmpty())
    }

    private fun approvedRegister() = AttendanceRegisterResponse(
        id = "register-1",
        organizationId = "org-1",
        projectId = "project-1",
        attendanceDate = "2026-09-12",
        shiftCode = "day",
        status = "approved",
        revision = 3,
        preparedByMembershipId = "member-1",
        approvedByMembershipId = "member-2",
        workflowInstanceId = null,
        configurationContext = emptyMap(),
        notes = null,
        submittedAt = "2026-09-12T12:00:00Z",
        approvedAt = "2026-09-12T12:05:00Z",
        rejectedAt = null,
        voidedAt = null,
        createdAt = "2026-09-12T08:00:00Z",
        updatedAt = "2026-09-12T12:05:00Z",
    )
}

private class FakeSummaryApi(
    private val registers: List<AttendanceRegisterResponse>,
    private val summary: AttendanceDprSummaryResponse?,
) : DprAttendanceApi {
    override suspend fun attendanceRegisters(projectId: String): List<AttendanceRegisterResponse> = registers

    override suspend fun dprSummary(
        projectId: String,
        registerId: String,
    ): AttendanceDprSummaryResponse = requireNotNull(summary)
}

private class FakeSummaryDao : DprAttendanceSummaryDao {
    var rows: List<DprAttendanceSummaryEntity> = emptyList()
    private val state = MutableStateFlow(rows)

    override fun observeSummary(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    ): Flow<List<DprAttendanceSummaryEntity>> = state

    override suspend fun insertAll(rows: List<DprAttendanceSummaryEntity>) {
        this.rows = rows
        state.value = rows
    }

    override suspend fun clearSummary(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    ) {
        rows = emptyList()
        state.value = emptyList()
    }
}
