package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.DailyReportCreateRequest
import com.constructionos.app.core.network.DailyReportOfflineMutationRequest
import com.constructionos.app.core.network.DailyReportOfflineMutationResponse
import com.constructionos.app.core.network.DailyReportResponse
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
        if (mutation.operation != DprRepository.OP_CREATE) {
            dao.markNeedsAttention(
                mutation = mutation,
                mutationState = DprMutationState.REJECTED,
                errorCode = "unsupported_operation",
                updatedAt = System.currentTimeMillis(),
            )
            return false
        }

        val create = runCatching {
            gson.fromJson(mutation.payloadJson, DailyReportCreateRequest::class.java)
        }.getOrElse {
            dao.markNeedsAttention(
                mutation = mutation,
                mutationState = DprMutationState.REJECTED,
                errorCode = "invalid_payload",
                updatedAt = System.currentTimeMillis(),
            )
            return false
        }

        val deviceId = deviceRegistrar.registeredDeviceId() ?: deviceRegistrar.register()
        val request = DailyReportOfflineMutationRequest(
            deviceId = deviceId,
            clientMutationId = mutation.clientMutationId,
            entityId = mutation.reportId,
            operation = DprRepository.OP_CREATE,
            create = create,
        )
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
            STATUS_APPLIED -> {
                val remote = response.reportResult()
                if (remote == null) {
                    dao.markNeedsAttention(
                        mutation = mutation,
                        mutationState = DprMutationState.REJECTED,
                        errorCode = "empty_report_result",
                        updatedAt = System.currentTimeMillis(),
                    )
                    false
                } else {
                    dao.applyCreate(
                        mutation = mutation,
                        serverReport = remote.toEntity(localId = mutation.reportId),
                        updatedAt = System.currentTimeMillis(),
                    )
                    true
                }
            }

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

    private fun Response<DailyReportOfflineMutationResponse>.typedBodyOrNull(): DailyReportOfflineMutationResponse? {
        if (isSuccessful) return body()
        val raw = errorBody()?.string()?.takeIf { it.isNotBlank() } ?: return null
        return runCatching {
            gson.fromJson(raw, DailyReportOfflineMutationResponse::class.java)
        }.getOrNull()
    }

    companion object {
        private const val STATUS_APPLIED = "applied"
        private const val STATUS_CONFLICT = "conflict"
        private const val STATUS_REJECTED = "rejected"
    }
}
