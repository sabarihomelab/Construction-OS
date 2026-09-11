package com.constructionos.app.core.attendance

import com.constructionos.app.core.database.AttendanceDao
import com.constructionos.app.core.database.AttendanceRegisterEntity
import com.constructionos.app.core.database.AttendanceRosterEntity
import com.constructionos.app.core.network.AttendanceRosterResponse
import com.constructionos.app.core.network.ConstructionOsApi
import kotlinx.coroutines.flow.Flow

class AttendanceRepository(
    private val api: ConstructionOsApi,
    private val dao: AttendanceDao,
) {
    fun observeRoster(projectId: String, attendanceDate: String): Flow<List<AttendanceRosterEntity>> =
        dao.observeActiveRoster(projectId, attendanceDate)

    fun observeRegisters(projectId: String, attendanceDate: String): Flow<List<AttendanceRegisterEntity>> =
        dao.observeRegisters(projectId, attendanceDate)

    suspend fun refreshRoster(projectId: String, attendanceDate: String) {
        val roster = api.attendanceRoster(projectId, attendanceDate)
            .map(AttendanceRosterResponse::toEntity)
        dao.replaceRoster(projectId, roster)
    }

    suspend fun clearProject(projectId: String) {
        dao.clearRoster(projectId)
    }
}

internal fun AttendanceRosterResponse.toEntity(): AttendanceRosterEntity = AttendanceRosterEntity(
    assignmentId = assignmentId,
    organizationId = organizationId,
    projectId = projectId,
    workerId = workerId,
    workerNumber = workerNumber,
    workerName = workerName,
    crewId = crewId,
    employerPartyId = employerPartyId,
    engagementType = engagementType,
    status = status,
    projectRole = projectRole,
    trade = trade,
    defaultCostCode = defaultCostCode,
    startDate = startDate,
    endDate = endDate,
    revision = revision,
)
