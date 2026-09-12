package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprDelayEntity
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.database.DprWorkProgressEntity
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.DailyReportCreateRequest
import com.constructionos.app.core.network.DailyReportOfflineMutationRequest
import com.constructionos.app.core.network.DailyReportOfflineMutationResponse
import com.constructionos.app.core.network.DailyReportResponse
import com.constructionos.app.core.network.DailyReportUpdateRequest
import com.constructionos.app.core.network.DprDelayReplaceRequest
import com.constructionos.app.core.network.DprDelayResponse
import com.constructionos.app.core.network.DprWorkProgressReplaceRequest
import com.constructionos.app.core.network.DprWorkProgressResponse
import com.constructionos.app.core.offline.DeviceRegistrar
import com.google.gson.Gson
import java.io.IOException
import retrofit2.HttpException
import retrofit2.Response

class DprMutationSyncService(
    private val api: ConstructionOsApi,
    private val dao: DprDao,
    private val deviceRegistrar: DeviceRegistrar,
    private val gson: Gson = Gson(),
) {
    suspend fun drain() {
        dao.recoverInterruptedMutations()
        while (true) {
            val mutation = dao.mutationsByState(limit = 1).firstOrNull() ?: return
            if (!applyMutation(mutation)) return
        }
    }

    private suspend fun applyMutation(mutation: DprMutationEntity): Boolean {
        val deviceId = deviceRegistrar.registeredDeviceId() ?: deviceRegistrar.register()
        val request = when (mutation.operation) {
            DprRepository.OP_CREATE -> buildCreateRequest(mutation, deviceId)
            DprRepository.OP_UPDATE_HEADER -> buildUpdateRequest(mutation, deviceId)
            DprRepository.OP_REPLACE_WORK_PROGRESS -> buildWorkProgressRequest(mutation, deviceId)
            DprRepository.OP_REPLACE_DELAYS -> buildDelaysRequest(mutation, deviceId)
            else -> null
        }
        if (request == null) {
            dao.markNeedsAttention(
                mutation = mutation,
                mutationState = DprMutationState.REJECTED,
                errorCode = if (mutation.operation in SUPPORTED_OPERATIONS) "invalid_payload" else "unsupported_operation",
                updatedAt = System.currentTimeMillis(),
            )
            return false
        }

        dao.markInFlight(mutation, System.currentTimeMillis())
        val httpResponse = try {
            api.submitDailyReportMutation(mutation.projectId, request)
        } catch (error: IOException) {
            dao.resetPending(mutation, System.currentTimeMillis())
            throw error
        }

        val response = httpResponse.typedBodyOrNull()
        if (response == null) {
            if (httpResponse.code() == 403) {
                rejectTransport(mutation, "permission_denied")
                return false
            }
            if (httpResponse.code() in 400..499 && httpResponse.code() != 401) {
                rejectTransport(mutation, "http_${httpResponse.code()}")
                return false
            }
            dao.resetPending(mutation, System.currentTimeMillis())
            throw HttpException(httpResponse)
        }

        return when (response.status) {
            STATUS_APPLIED -> applySuccessfulMutation(mutation, response)
            STATUS_CONFLICT -> {
                dao.markNeedsAttention(
                    mutation = mutation,
                    mutationState = DprMutationState.CONFLICT,
                    errorCode = response.errorCode,
                    updatedAt = System.currentTimeMillis(),
                )
                false
            }
            STATUS_REJECTED -> {
                dao.markNeedsAttention(
                    mutation = mutation,
                    mutationState = DprMutationState.REJECTED,
                    errorCode = response.errorCode,
                    updatedAt = System.currentTimeMillis(),
                )
                false
            }
            else -> {
                dao.resetPending(mutation, System.currentTimeMillis())
                throw IOException("Unexpected Daily Report mutation status: ${response.status}")
            }
        }
    }

    private suspend fun applySuccessfulMutation(
        mutation: DprMutationEntity,
        response: DailyReportOfflineMutationResponse,
    ): Boolean {
        val remote = response.reportResult()
        if (remote == null) {
            dao.markNeedsAttention(
                mutation = mutation,
                mutationState = DprMutationState.REJECTED,
                errorCode = "empty_report_result",
                updatedAt = System.currentTimeMillis(),
            )
            return false
        }
        val workProgress = if (mutation.operation == DprRepository.OP_REPLACE_WORK_PROGRESS) {
            response.workProgressResult().mapIndexed { index, row -> row.toEntity(mutation.reportId, index) }
        } else {
            null
        }
        val delays = if (mutation.operation == DprRepository.OP_REPLACE_DELAYS) {
            response.delaysResult().mapIndexed { index, row -> row.toEntity(mutation.reportId, remote.projectId, index) }
        } else {
            null
        }
        dao.applyServerResult(
            mutation = mutation,
            serverReport = remote.toEntity(localId = mutation.reportId),
            serverWorkProgress = workProgress,
            serverDelays = delays,
            updatedAt = System.currentTimeMillis(),
        )
        return true
    }

    private suspend fun buildCreateRequest(mutation: DprMutationEntity, deviceId: String): DailyReportOfflineMutationRequest? {
        val create = runCatching { gson.fromJson(mutation.payloadJson, DailyReportCreateRequest::class.java) }.getOrNull() ?: return null
        return DailyReportOfflineMutationRequest(
            deviceId = deviceId,
            clientMutationId = mutation.clientMutationId,
            entityId = mutation.reportId,
            operation = DprRepository.OP_CREATE,
            create = create,
        )
    }

    private suspend fun buildUpdateRequest(mutation: DprMutationEntity, deviceId: String): DailyReportOfflineMutationRequest? {
        val report = dao.reportById(mutation.reportId) ?: return null
        val serverId = report.serverId ?: return null
        val update = runCatching { gson.fromJson(mutation.payloadJson, DailyReportUpdateRequest::class.java) }.getOrNull() ?: return null
        if (update.expectedRevision < 1) return null
        return DailyReportOfflineMutationRequest(
            deviceId = deviceId,
            clientMutationId = mutation.clientMutationId,
            entityId = serverId,
            operation = DprRepository.OP_UPDATE_HEADER,
            baseRevision = update.expectedRevision,
            update = update,
        )
    }

    private suspend fun buildWorkProgressRequest(mutation: DprMutationEntity, deviceId: String): DailyReportOfflineMutationRequest? {
        val report = dao.reportById(mutation.reportId) ?: return null
        val serverId = report.serverId ?: return null
        if (report.revision < 1) return null
        val pending = runCatching { gson.fromJson(mutation.payloadJson, DprPendingWorkProgressPayload::class.java) }.getOrNull() ?: return null
        return DailyReportOfflineMutationRequest(
            deviceId = deviceId,
            clientMutationId = mutation.clientMutationId,
            entityId = serverId,
            operation = DprRepository.OP_REPLACE_WORK_PROGRESS,
            baseRevision = report.revision,
            workProgress = DprWorkProgressReplaceRequest(
                expectedRevision = report.revision,
                rows = pending.rows,
                reason = pending.reason,
            ),
        )
    }

    private suspend fun buildDelaysRequest(mutation: DprMutationEntity, deviceId: String): DailyReportOfflineMutationRequest? {
        val report = dao.reportById(mutation.reportId) ?: return null
        val serverId = report.serverId ?: return null
        if (report.revision < 1) return null
        val pending = runCatching { gson.fromJson(mutation.payloadJson, DprPendingDelaysPayload::class.java) }.getOrNull() ?: return null
        return DailyReportOfflineMutationRequest(
            deviceId = deviceId,
            clientMutationId = mutation.clientMutationId,
            entityId = serverId,
            operation = DprRepository.OP_REPLACE_DELAYS,
            baseRevision = report.revision,
            delays = DprDelayReplaceRequest(
                expectedRevision = report.revision,
                rows = pending.rows,
                reason = pending.reason,
            ),
        )
    }

    private suspend fun rejectTransport(mutation: DprMutationEntity, errorCode: String) {
        dao.markNeedsAttention(
            mutation = mutation,
            mutationState = DprMutationState.REJECTED,
            errorCode = errorCode,
            updatedAt = System.currentTimeMillis(),
        )
    }

    private fun DailyReportOfflineMutationResponse.reportResult(): DailyReportResponse? {
        val raw = result["report"] ?: return null
        return gson.fromJson(gson.toJson(raw), DailyReportResponse::class.java)
    }

    private fun DailyReportOfflineMutationResponse.workProgressResult(): List<DprWorkProgressResponse> {
        val raw = result["work_progress"] ?: return emptyList()
        val array = gson.toJsonTree(raw)
        if (!array.isJsonArray) return emptyList()
        return array.asJsonArray.mapNotNull { element ->
            runCatching { gson.fromJson(element, DprWorkProgressResponse::class.java) }.getOrNull()
        }
    }

    private fun DailyReportOfflineMutationResponse.delaysResult(): List<DprDelayResponse> {
        val raw = result["delays"] ?: return emptyList()
        val array = gson.toJsonTree(raw)
        if (!array.isJsonArray) return emptyList()
        return array.asJsonArray.mapNotNull { element ->
            runCatching { gson.fromJson(element, DprDelayResponse::class.java) }.getOrNull()
        }
    }

    private fun DprWorkProgressResponse.toEntity(localReportId: String, position: Int): DprWorkProgressEntity =
        DprWorkProgressEntity(
            id = id,
            reportId = localReportId,
            projectId = projectId,
            position = position,
            wbsCodeId = wbsCodeId,
            boqItemId = boqItemId,
            description = description,
            location = location,
            quantity = quantity,
            unitCode = unitCode,
            progressPercent = progressPercent,
            remarks = remarks,
        )

    private fun DprDelayResponse.toEntity(localReportId: String, projectId: String, position: Int): DprDelayEntity =
        DprDelayEntity(
            id = id,
            reportId = localReportId,
            projectId = projectId,
            position = position,
            category = category,
            description = description,
            startedAt = startedAt,
            endedAt = endedAt,
            lostHours = lostHours,
            responsibleParty = responsibleParty,
            scheduleImpact = scheduleImpact,
            notes = notes,
        )

    private fun Response<DailyReportOfflineMutationResponse>.typedBodyOrNull(): DailyReportOfflineMutationResponse? {
        if (isSuccessful) return body()
        val raw = errorBody()?.string()?.takeIf { it.isNotBlank() } ?: return null
        return runCatching { gson.fromJson(raw, DailyReportOfflineMutationResponse::class.java) }.getOrNull()
    }

    companion object {
        private val SUPPORTED_OPERATIONS = setOf(
            DprRepository.OP_CREATE,
            DprRepository.OP_UPDATE_HEADER,
            DprRepository.OP_REPLACE_WORK_PROGRESS,
            DprRepository.OP_REPLACE_DELAYS,
        )
        private const val STATUS_APPLIED = "applied"
        private const val STATUS_CONFLICT = "conflict"
        private const val STATUS_REJECTED = "rejected"
    }
}
