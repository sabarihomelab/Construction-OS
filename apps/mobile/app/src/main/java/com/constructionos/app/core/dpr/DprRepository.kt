package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprBoqReferenceEntity
import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprDelayEntity
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.database.DprWbsReferenceEntity
import com.constructionos.app.core.database.DprWorkProgressEntity
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.DailyReportCreateRequest
import com.constructionos.app.core.network.DailyReportResponse
import com.constructionos.app.core.network.DailyReportUpdateRequest
import com.constructionos.app.core.network.DprDelayWriteRequest
import com.constructionos.app.core.network.DprWorkProgressWriteRequest
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.google.gson.Gson
import java.math.BigDecimal
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

    fun observeWorkProgress(reportId: String): Flow<List<DprWorkProgressEntity>> =
        dao.observeWorkProgress(reportId)

    fun observeDelays(reportId: String): Flow<List<DprDelayEntity>> =
        dao.observeDelays(reportId)

    fun observeWbsReferences(projectId: String): Flow<List<DprWbsReferenceEntity>> =
        dao.observeWbsReferences(projectId)

    fun observeBoqReferences(projectId: String): Flow<List<DprBoqReferenceEntity>> =
        dao.observeBoqReferences(projectId)

    suspend fun enabledSections(projectId: String): Set<String> {
        val setting = api.effectiveProjectConfiguration(projectId, "field")
            .settings
            .firstOrNull { it.key == "field.daily_reports.sections.enabled" }
            ?.value
        val sections = (setting as? List<*>)
            ?.mapNotNull { it as? String }
            ?.toSet()
            .orEmpty()
        return sections.ifEmpty { DEFAULT_ENABLED_SECTIONS }
    }

    suspend fun refreshProject(projectId: String) {
        val remotes = api.dailyReports(projectId)
        remotes.forEach { remote ->
            val existing = dao.report(projectId, remote.reportDate, remote.shiftCode)
            if (existing != null && existing.serverId == null) return@forEach
            if (existing != null && existing.syncState != DprSyncState.SYNCED) return@forEach
            if (existing != null && dao.activeMutationCount(existing.id) > 0) return@forEach
            val localId = existing?.id ?: remote.id
            dao.upsertReport(
                remote.toEntity(
                    localId = localId,
                    localUpdatedAt = existing?.localUpdatedAt ?: System.currentTimeMillis(),
                ),
            )
            val rows = api.dprWorkProgress(projectId, remote.id).mapIndexed { index, row ->
                DprWorkProgressEntity(
                    id = row.id,
                    reportId = localId,
                    projectId = projectId,
                    position = index,
                    wbsCodeId = row.wbsCodeId,
                    boqItemId = row.boqItemId,
                    description = row.description,
                    location = row.location,
                    quantity = row.quantity,
                    unitCode = row.unitCode,
                    progressPercent = row.progressPercent,
                    remarks = row.remarks,
                )
            }
            dao.replaceWorkProgressFromServer(localId, rows)

            val detail = api.dailyReportDetail(projectId, remote.id)
            dao.replaceDelaysFromServer(
                localId,
                detail.delays.mapIndexed { index, row ->
                    DprDelayEntity(
                        id = row.id,
                        reportId = localId,
                        projectId = projectId,
                        position = index,
                        category = row.category,
                        description = row.description,
                        startedAt = row.startedAt,
                        endedAt = row.endedAt,
                        lostHours = row.lostHours,
                        responsibleParty = row.responsibleParty,
                        scheduleImpact = row.scheduleImpact,
                        notes = row.notes,
                    )
                },
            )
        }

        val references = api.dprWorkProgressReferences(projectId)
        dao.replaceReferences(
            projectId = projectId,
            wbs = references.wbsCodes.map { row ->
                DprWbsReferenceEntity(
                    id = row.id,
                    projectId = projectId,
                    code = row.code,
                    name = row.name,
                    kind = row.kind,
                    parentId = row.parentId,
                )
            },
            boq = references.boqItems.map { row ->
                DprBoqReferenceEntity(
                    id = row.id,
                    projectId = projectId,
                    boqId = row.boqId,
                    boqCode = row.boqCode,
                    boqName = row.boqName,
                    wbsCodeId = row.wbsCodeId,
                    itemCode = row.itemCode,
                    description = row.description,
                    unitCode = row.unitCode,
                )
            },
        )
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
            dao.updatePendingCreate(
                reportId = report.id,
                mutationId = createMutation.clientMutationId,
                payloadJson = gson.toJson(
                    create.copy(
                        weatherCondition = normalizedWeather,
                        notes = normalizedNotes,
                    ),
                ),
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

    suspend fun saveWorkProgress(
        reportId: String,
        rows: List<DprWorkProgressDraft>,
    ) {
        val report = requireNotNull(dao.reportById(reportId)) { "Daily report was not found" }
        require(report.status == STATUS_DRAFT) { "Only a draft daily report can be edited." }
        require(rows.size <= 1000) { "A daily report can contain at most 1000 work progress rows." }

        val normalized = rows.mapIndexed { index, draft ->
            val description = draft.description.trim()
            require(description.isNotEmpty()) { "Work progress description is required." }
            require(description.length <= 2000) { "Work progress description must be 2000 characters or fewer." }
            require(draft.wbsCodeId != null || draft.boqItemId != null) {
                "Select a WBS / Cost Code or approved BOQ item."
            }
            draft.quantity.normalizedDecimal("Quantity")?.let { require(it >= BigDecimal.ZERO) { "Quantity cannot be negative." } }
            draft.progressPercent.normalizedDecimal("Progress")?.let {
                require(it >= BigDecimal.ZERO && it <= BigDecimal("100")) { "Progress must be between 0 and 100." }
            }
            DprWorkProgressEntity(
                id = draft.id ?: UUID.randomUUID().toString(),
                reportId = report.id,
                projectId = report.projectId,
                position = index,
                wbsCodeId = draft.wbsCodeId,
                boqItemId = draft.boqItemId,
                description = description,
                location = draft.location.normalizedOrNull(),
                quantity = draft.quantity.normalizedOrNull(),
                unitCode = draft.unitCode.normalizedOrNull(),
                progressPercent = draft.progressPercent.normalizedOrNull(),
                remarks = draft.remarks.normalizedOrNull(),
            )
        }

        val payload = DprPendingWorkProgressPayload(
            rows = normalized.map { it.toWriteRequest() },
        )
        val now = System.currentTimeMillis()
        val existing = dao.mutation(report.id, OP_REPLACE_WORK_PROGRESS)
        val mutation = existing?.copy(
            payloadJson = gson.toJson(payload),
            updatedAt = now,
        ) ?: DprMutationEntity(
            clientMutationId = UUID.randomUUID().toString(),
            projectId = report.projectId,
            reportId = report.id,
            operation = OP_REPLACE_WORK_PROGRESS,
            payloadJson = gson.toJson(payload),
            state = DprMutationState.PENDING,
            errorCode = null,
            attemptCount = 0,
            createdAt = now,
            updatedAt = now,
        )
        dao.replaceWorkProgressLocally(report.id, normalized, mutation, now)
        syncScheduler.scheduleOnce()
    }

    suspend fun saveDelays(
        reportId: String,
        rows: List<DprDelayDraft>,
    ) {
        val report = requireNotNull(dao.reportById(reportId)) { "Daily report was not found" }
        require(report.status == STATUS_DRAFT) { "Only a draft daily report can be edited." }
        require(rows.size <= 1000) { "A daily report can contain at most 1000 delay rows." }

        val normalized = rows.mapIndexed { index, draft ->
            val description = draft.description.trim()
            val category = draft.category.normalizedOrNull()
            val responsibleParty = draft.responsibleParty.normalizedOrNull()
            require(description.isNotEmpty()) { "Delay / blocker description is required." }
            require(description.length <= 2000) { "Delay / blocker description must be 2000 characters or fewer." }
            require((category?.length ?: 0) <= 120) { "Delay category must be 120 characters or fewer." }
            require((responsibleParty?.length ?: 0) <= 255) { "Responsible party must be 255 characters or fewer." }
            draft.lostHours.normalizedDecimal("Lost hours")?.let {
                require(it >= BigDecimal.ZERO) { "Lost hours cannot be negative." }
            }
            DprDelayEntity(
                id = draft.id ?: UUID.randomUUID().toString(),
                reportId = report.id,
                projectId = report.projectId,
                position = index,
                category = category,
                description = description,
                startedAt = draft.startedAt.normalizedOrNull(),
                endedAt = draft.endedAt.normalizedOrNull(),
                lostHours = draft.lostHours.normalizedOrNull(),
                responsibleParty = responsibleParty,
                scheduleImpact = draft.scheduleImpact,
                notes = draft.notes.normalizedOrNull(),
            )
        }

        val payload = DprPendingDelaysPayload(
            rows = normalized.map { it.toWriteRequest() },
        )
        val now = System.currentTimeMillis()
        val existing = dao.mutation(report.id, OP_REPLACE_DELAYS)
        val mutation = existing?.copy(
            payloadJson = gson.toJson(payload),
            updatedAt = now,
        ) ?: DprMutationEntity(
            clientMutationId = UUID.randomUUID().toString(),
            projectId = report.projectId,
            reportId = report.id,
            operation = OP_REPLACE_DELAYS,
            payloadJson = gson.toJson(payload),
            state = DprMutationState.PENDING,
            errorCode = null,
            attemptCount = 0,
            createdAt = now,
            updatedAt = now,
        )
        dao.replaceDelaysLocally(report.id, normalized, mutation, now)
        syncScheduler.scheduleOnce()
    }

    companion object {
        const val STATUS_DRAFT = "draft"
        const val OP_CREATE = "create_report"
        const val OP_UPDATE_HEADER = "update_header"
        const val OP_REPLACE_WORK_PROGRESS = "replace_work_progress"
        const val OP_REPLACE_DELAYS = "replace_delays"
        val DEFAULT_ENABLED_SECTIONS = setOf("crew", "work", "photos", "notes")
    }
}

data class DprWorkProgressDraft(
    val id: String? = null,
    val wbsCodeId: String? = null,
    val boqItemId: String? = null,
    val description: String,
    val location: String? = null,
    val quantity: String? = null,
    val unitCode: String? = null,
    val progressPercent: String? = null,
    val remarks: String? = null,
)

data class DprDelayDraft(
    val id: String? = null,
    val category: String? = null,
    val description: String,
    val startedAt: String? = null,
    val endedAt: String? = null,
    val lostHours: String? = null,
    val responsibleParty: String? = null,
    val scheduleImpact: Boolean = false,
    val notes: String? = null,
)

internal data class DprPendingWorkProgressPayload(
    val rows: List<DprWorkProgressWriteRequest>,
    val reason: String? = null,
)

internal data class DprPendingDelaysPayload(
    val rows: List<DprDelayWriteRequest>,
    val reason: String? = null,
)

private fun DprWorkProgressEntity.toWriteRequest(): DprWorkProgressWriteRequest = DprWorkProgressWriteRequest(
    wbsCodeId = wbsCodeId,
    boqItemId = boqItemId,
    description = description,
    location = location,
    quantity = quantity,
    unitCode = unitCode,
    progressPercent = progressPercent,
    remarks = remarks,
)

private fun DprDelayEntity.toWriteRequest(): DprDelayWriteRequest = DprDelayWriteRequest(
    category = category,
    description = description,
    startedAt = startedAt,
    endedAt = endedAt,
    lostHours = lostHours,
    responsibleParty = responsibleParty,
    scheduleImpact = scheduleImpact,
    notes = notes,
)

private fun String?.normalizedOrNull(): String? = this?.trim()?.takeIf { it.isNotEmpty() }

private fun String?.normalizedDecimal(label: String): BigDecimal? {
    val value = normalizedOrNull() ?: return null
    return value.toBigDecimalOrNull() ?: throw IllegalArgumentException("$label must be a valid number.")
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
