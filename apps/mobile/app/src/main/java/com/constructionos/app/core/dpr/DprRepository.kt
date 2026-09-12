package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.DailyReportCreateRequest
import com.constructionos.app.core.network.DailyReportResponse
import com.constructionos.app.core.network.DailyReportUpdateRequest
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
            if (existing != null && existing.syncState != DprSyncState.SYNCED) {
                return@forEach
            }
            if (existing != null && dao.activeMutationCount(existing.id) > 0) {
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
            weatherCondition = weatherCondition.normalizedOrNull(),
            notes = notes.normalizedOrNull(),
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

    suspend fun saveDraftHeader(
        reportId: String,
        weatherCondition: String?,
        notes: String?,
    ) {
        val report = requireNotNull(dao.reportById(reportId)) { "Daily report was not found" }
        require(report.status == STATUS_DRAFT) { "Only a draft daily report can be edited." }

        val normalizedWeather = weatherCondition.normalizedOrNull()
        val normalizedNotes = notes.normalizedOrNull()
        require((normalizedWeather?.length ?: 0) <= 120) { "Weather must be 120 characters or fewer." }

        val now = System.currentTimeMillis()
        if (report.serverId == null) {
            val createMutation = requireNotNull(dao.mutation(report.id, OP_CREATE)) {
                "Finish syncing this daily report before editing it again."
            }
            val create = runCatching {
                gson.fromJson(createMutation.payloadJson, DailyReportCreateRequest::class.java)
            }.getOrElse {
                throw IllegalStateException("The local daily report draft could not be read.", it)
            }
            val updatedCreate = create.copy(
                weatherCondition = normalizedWeather,
                notes = normalizedNotes,
            )
            dao.updatePendingCreate(
                reportId = report.id,
                mutationId = createMutation.clientMutationId,
                payloadJson = gson.toJson(updatedCreate),
                weatherCondition = normalizedWeather,
                notes = normalizedNotes,
                updatedAt = now,
            )
            syncScheduler.scheduleOnce()
            return
        }

        require(report.revision > 0) { "Finish syncing this daily report before editing it." }
        require(dao.activeMutationCount(report.id) == 0) {
            "Finish syncing the previous daily report change before saving another one."
        }

        val request = DailyReportUpdateRequest(
            expectedRevision = report.revision,
            weatherCondition = normalizedWeather ?: "",
            notes = normalizedNotes ?: "",
        )
        val mutation = DprMutationEntity(
            clientMutationId = UUID.randomUUID().toString(),
            projectId = report.projectId,
            reportId = report.id,
            operation = OP_UPDATE_HEADER,
            payloadJson = gson.toJson(request),
            state = DprMutationState.PENDING,
            errorCode = null,
            attemptCount = 0,
            createdAt = now,
            updatedAt = now,
        )
        dao.queueHeaderUpdate(
            reportId = report.id,
            weatherCondition = normalizedWeather,
            notes = normalizedNotes,
            mutation = mutation,
            updatedAt = now,
        )
        syncScheduler.scheduleOnce()
    }

    companion object {
        const val STATUS_DRAFT = "draft"
        const val OP_CREATE = "create_report"
        const val OP_UPDATE_HEADER = "update_header"
    }
}

private fun String?.normalizedOrNull(): String? = this?.trim()?.takeIf { it.isNotEmpty() }

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
