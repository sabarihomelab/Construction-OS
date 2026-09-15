package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprAttendanceSummaryDao
import com.constructionos.app.core.database.DprAttendanceSummaryEntity
import com.constructionos.app.core.network.AttendanceDprSummaryResponse
import com.constructionos.app.core.network.AttendanceDprSummaryRowResponse
import com.constructionos.app.core.network.DprAttendanceApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

class DprAttendanceSummaryRepositoryTest {
    @Test
    fun `approved attendance summary is cached exactly`() = runBlocking {
        val dao = FakeSummaryDao()
        val api = FakeSummaryApi(
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
        assertEquals("2026-09-12", api.lastAttendanceDate)
        assertEquals("day", api.lastShiftCode)
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
        val api = FakeSummaryApi(httpCode = 404)
        val repository = DprAttendanceSummaryRepository(api, dao)

        val result = repository.refresh("project-1", "2026-09-12", "day")

        assertEquals(DprAttendanceRefreshResult.NO_APPROVED_ATTENDANCE, result)
        assertTrue(dao.rows.isEmpty())
    }
}

private class FakeSummaryApi(
    private val summary: AttendanceDprSummaryResponse? = null,
    private val httpCode: Int? = null,
) : DprAttendanceApi {
    var lastAttendanceDate: String? = null
    var lastShiftCode: String? = null

    override suspend fun dprSummary(
        projectId: String,
        attendanceDate: String,
        shiftCode: String,
    ): AttendanceDprSummaryResponse {
        lastAttendanceDate = attendanceDate
        lastShiftCode = shiftCode
        httpCode?.let { code ->
            val body = "{}".toResponseBody("application/json".toMediaType())
            throw HttpException(Response.error<AttendanceDprSummaryResponse>(code, body))
        }
        return requireNotNull(summary)
    }
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
