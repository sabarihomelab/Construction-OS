package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.network.DailyReportRequiredReasonActionRequest
import com.constructionos.app.core.network.DailyReportVersionActionRequest
import com.constructionos.app.core.network.DprGenerationStatusResponse
import com.constructionos.app.core.network.DprLifecycleApi
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.google.gson.Gson
import java.util.UUID
import retrofit2.HttpException

class DprLifecycleRepository(
    private val api: DprLifecycleApi,
    private val dao: DprDao,
    private val syncScheduler: WorkspaceSyncScheduler,
    private val gson: Gson = Gson(),
) {
    suspend fun submit(reportId: String, reason: String? = null) {
        val report = requireSyncedReport(reportId, STATUS_DRAFT)
        val now = System.currentTimeMillis()
        val action = DailyReportVersionActionRequest(
            expectedRevision = report.revision,
            reason = reason.normalizedOrNull(),
        )
        dao.upsertMutation(
            DprMutationEntity(
                clientMutationId = UUID.randomUUID().toString(),
                projectId = report.projectId,
                reportId = report.id,
                operation = OP_SUBMIT,
                payloadJson = gson.toJson(action),
                state = DprMutationState.PENDING,
                errorCode = null,
                attemptCount = 0,
                createdAt = now,
                updatedAt = now,
            ),
        )
        dao.updateReportSyncState(report.id, DprSyncState.WAITING_FOR_NETWORK, now)
        syncScheduler.scheduleOnce()
    }

    suspend fun approve(reportId: String, reason: String? = null): DprReportEntity =
        runOnlineAction(reportId, STATUS_IN_REVIEW) { report ->
            api.approve(
                projectId = report.projectId,
                reportId = requireNotNull(report.serverId),
                request = DailyReportVersionActionRequest(
                    expectedRevision = report.revision,
                    reason = reason.normalizedOrNull(),
                ),
            )
        }

    suspend fun reject(reportId: String, reason: String): DprReportEntity {
        val normalizedReason = reason.trim()
        require(normalizedReason.isNotEmpty()) { "A rejection reason is required." }
        return runOnlineAction(reportId, STATUS_IN_REVIEW) { report ->
            api.reject(
                projectId = report.projectId,
                reportId = requireNotNull(report.serverId),
                request = DailyReportRequiredReasonActionRequest(
                    expectedRevision = report.revision,
                    reason = normalizedReason,
                ),
            )
        }
    }

    suspend fun reopen(reportId: String, reason: String? = null): DprReportEntity =
        runOnlineAction(reportId, STATUS_REJECTED) { report ->
            api.reopen(
                projectId = report.projectId,
                reportId = requireNotNull(report.serverId),
                request = DailyReportVersionActionRequest(
                    expectedRevision = report.revision,
                    reason = reason.normalizedOrNull(),
                ),
            )
        }

    suspend fun voidReport(reportId: String, reason: String): DprReportEntity {
        val normalizedReason = reason.trim()
        require(normalizedReason.isNotEmpty()) { "A reason is required to void the daily report." }
        val report = requireCleanServerReport(reportId)
        return executeOnline(report) {
            api.voidReport(
                projectId = report.projectId,
                reportId = requireNotNull(report.serverId),
                request = DailyReportRequiredReasonActionRequest(
                    expectedRevision = report.revision,
                    reason = normalizedReason,
                ),
            )
        }
    }

    suspend fun generationStatus(reportId: String): DprGenerationStatusResponse {
        val report = requireCleanServerReport(reportId)
        return api.reportGeneration(
            projectId = report.projectId,
            reportId = requireNotNull(report.serverId),
        )
    }

    private suspend fun runOnlineAction(
        reportId: String,
        requiredStatus: String,
        action: suspend (DprReportEntity) -> com.constructionos.app.core.network.DailyReportResponse,
    ): DprReportEntity {
        val report = requireSyncedReport(reportId, requiredStatus)
        return executeOnline(report) { action(report) }
    }

    private suspend fun executeOnline(
        report: DprReportEntity,
        action: suspend () -> com.constructionos.app.core.network.DailyReportResponse,
    ): DprReportEntity {
        return try {
            val remote = action()
            val updated = remote.toEntity(
                localId = report.id,
                localUpdatedAt = System.currentTimeMillis(),
            )
            dao.upsertReport(updated)
            updated
        } catch (error: HttpException) {
            if (error.code() == 409) {
                dao.updateReportSyncState(
                    report.id,
                    DprSyncState.NEEDS_ATTENTION,
                    System.currentTimeMillis(),
                )
            }
            throw error
        }
    }

    private suspend fun requireSyncedReport(reportId: String, requiredStatus: String): DprReportEntity {
        val report = requireCleanServerReport(reportId)
        require(report.status == requiredStatus) {
            "This action is not available while the daily report is ${report.status.replace('_', ' ')}."
        }
        return report
    }

    private suspend fun requireCleanServerReport(reportId: String): DprReportEntity {
        val report = requireNotNull(dao.reportById(reportId)) { "Daily report was not found." }
        require(report.serverId != null && report.revision > 0) {
            "Finish syncing this daily report before using this action."
        }
        require(report.syncState == DprSyncState.SYNCED) {
            "Resolve or finish syncing local daily report changes first."
        }
        require(dao.activeMutationCount(report.id) == 0) {
            "Finish syncing local daily report changes first."
        }
        return report
    }

    companion object {
        const val OP_SUBMIT = "submit"
        const val STATUS_DRAFT = "draft"
        const val STATUS_IN_REVIEW = "in_review"
        const val STATUS_APPROVED = "approved"
        const val STATUS_REJECTED = "rejected"
        const val STATUS_VOID = "void"
    }
}

private fun String?.normalizedOrNull(): String? = this?.trim()?.takeIf { it.isNotEmpty() }
