package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.DailyReportCreateRequest
import com.google.gson.Gson
import java.io.IOException
import retrofit2.HttpException

class DprMutationSyncService(
    private val api: ConstructionOsApi,
    private val dao: DprDao,
    private val gson: Gson = Gson(),
) {
    suspend fun drain() {
        dao.recoverInterruptedMutations()
        while (true) {
            val pending = dao.mutationsByState(limit = 50)
            if (pending.isEmpty()) return
            pending.forEach { mutation ->
                when (mutation.operation) {
                    DprRepository.OP_CREATE -> syncCreate(mutation)
                    else -> dao.markNeedsAttention(
                        mutation = mutation,
                        mutationState = DprMutationState.REJECTED,
                        errorCode = "unsupported_operation",
                        updatedAt = System.currentTimeMillis(),
                    )
                }
            }
            if (pending.size < 50) return
        }
    }

    private suspend fun syncCreate(mutation: DprMutationEntity) {
        val localReport = dao.reportById(mutation.reportId)
        if (localReport == null) {
            dao.markNeedsAttention(
                mutation = mutation,
                mutationState = DprMutationState.REJECTED,
                errorCode = "local_report_missing",
                updatedAt = System.currentTimeMillis(),
            )
            return
        }

        val request = runCatching {
            gson.fromJson(mutation.payloadJson, DailyReportCreateRequest::class.java)
        }.getOrElse {
            dao.markNeedsAttention(
                mutation = mutation,
                mutationState = DprMutationState.REJECTED,
                errorCode = "invalid_payload",
                updatedAt = System.currentTimeMillis(),
            )
            return
        }

        dao.markInFlight(mutation, System.currentTimeMillis())

        val response = try {
            api.createDailyReport(mutation.projectId, request)
        } catch (error: IOException) {
            dao.resetPending(mutation, System.currentTimeMillis())
            throw error
        }

        if (response.isSuccessful) {
            val remote = response.body()
            if (remote == null) {
                dao.markNeedsAttention(
                    mutation = mutation,
                    mutationState = DprMutationState.REJECTED,
                    errorCode = "empty_response",
                    updatedAt = System.currentTimeMillis(),
                )
                return
            }
            dao.applyCreate(
                mutation = mutation,
                serverReport = remote.toEntity(localId = mutation.reportId),
                updatedAt = System.currentTimeMillis(),
            )
            return
        }

        if (response.code() == 409) {
            val existing = try {
                api.dailyReports(mutation.projectId).firstOrNull {
                    it.reportDate == localReport.reportDate && it.shiftCode == localReport.shiftCode
                }
            } catch (error: HttpException) {
                dao.resetPending(mutation, System.currentTimeMillis())
                throw error
            } catch (error: IOException) {
                dao.resetPending(mutation, System.currentTimeMillis())
                throw error
            }
            if (existing != null) {
                dao.applyCreate(
                    mutation = mutation,
                    serverReport = existing.toEntity(localId = mutation.reportId),
                    updatedAt = System.currentTimeMillis(),
                )
            } else {
                dao.markNeedsAttention(
                    mutation = mutation,
                    mutationState = DprMutationState.CONFLICT,
                    errorCode = "create_conflict",
                    updatedAt = System.currentTimeMillis(),
                )
            }
            return
        }

        if (response.code() == 401 || response.code() >= 500) {
            dao.resetPending(mutation, System.currentTimeMillis())
            throw HttpException(response)
        }

        dao.markNeedsAttention(
            mutation = mutation,
            mutationState = DprMutationState.REJECTED,
            errorCode = "http_${response.code()}",
            updatedAt = System.currentTimeMillis(),
        )
    }
}
