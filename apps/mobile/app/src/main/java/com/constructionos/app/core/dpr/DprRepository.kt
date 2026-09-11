package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.DailyReportCreateRequest
import com.constructionos.app.core.network.DailyReportResponse
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.google.gson.Gson
import java.util.UUID
import kotlinx.coroutines.flow.Flow

class DprRepository(
    private val api: ConstructionOsApi,
    private val dao: DprDao,
    private val syncScheduler: WorkspaceSyncScheduler,
    private val gson: Gson = Gson(),
) {
    fun observeDay(projectId: String, reportDate: String): Flow<List<DprReportEntity>> =
        dao.observeDay(projectId, reportDate)

    fun observeProjectReports(projectId: String): Flow<List<DprReportEntity>> =
        dao.observeProjectReports(projectId)

    suspend fun refreshProject(projectId: String) {
        api.dailyReports(projectId).forEach { remote ->
            val existing = dao.report(projectId, remote.reportDate, remote.shiftCode)
            if (existing != null && existing.serverId == null) {
                return@forEach
            }
            dao.upsertReport(
                remote.toEntity(
                    localId = existing?.id ?: remote.id,
                    localUpdatedAt = existing?.localUpdatedAt ?: System.currentTimeMillis(),
                ),
            )
        }
    }

    suspend fun startLocalDraft(
        organizationId: String,
        projectId: String,
        reportDate: String,
        shiftCode: String = "day",
        weatherCondition: String? = null,
        notes: String? = null,
    ): String {
        dao.report(projectId, reportDate, shiftCode)?.let { return it.id }

        val now = System.currentTimeMillis()
        val reportId = UUID.randomUUID().toString()
        val request = DailyReportCreateRequest(
            reportDate = reportDate,
            shiftCode = shiftCode,
            weatherCondition = weatherCondition?.trim()?.takeIf(String::isNotEmpty),
            notes = notes?.trim()?.takeIf(String::isNotEmpty),
        )
        val report = DprReportEntity(
            id = reportId,
            serverId = null,
            organizationId = organizationId,
            projectId = projectId,
            reportDate = reportDate,
            shiftCode = shiftCode,
            status = STATUS_DRAFT,
            revision = 0,
            weatherCondition = request.weatherCondition,
            temperatureLow = null,
            temperatureHigh = null,
            temperatureUnit = null,
            notes = request.notes,
            syncState = DprSyncState.SAVED_ON_DEVICE,
            serverUpdatedAt = null,
            localUpdatedAt = now,
        )
        val mutation = DprMutationEntity(
            clientMutationId = UUID.randomUUID().toString(),
            projectId = projectId,
            reportId = reportId,
            operation = OP_CREATE,
            payloadJson = gson.toJson(request),
            state = DprMutationState.PENDING,
            errorCode = null,
            attemptCount = 0,
            createdAt = now,
            updatedAt = now,
        )
        dao.createLocalDraft(report, mutation)
        syncScheduler.scheduleOnce()
        return reportId
    }

    companion object {
        const val STATUS_DRAFT = "draft"
        const val OP_CREATE = "create_report"
    }
}

internal fun DailyReportResponse.toEntity(
    localId: String = id,
    localUpdatedAt: Long = System.currentTimeMillis(),
): DprReportEntity = DprReportEntity(
    id = localId,
    serverId = id,
    organizationId = organizationId,
    projectId = projectId,
    reportDate = reportDate,
    shiftCode = shiftCode,
    status = status,
    revision = revision,
    weatherCondition = weatherCondition,
    temperatureLow = temperatureLow,
    temperatureHigh = temperatureHigh,
    temperatureUnit = temperatureUnit,
    notes = notes,
    syncState = DprSyncState.SYNCED,
    serverUpdatedAt = updatedAt,
    localUpdatedAt = localUpdatedAt,
)
