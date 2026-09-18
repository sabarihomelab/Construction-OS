package com.constructionos.app.core.attendance

import com.constructionos.app.core.database.AttendanceDao
import com.constructionos.app.core.database.AttendanceEntryEntity
import com.constructionos.app.core.database.AttendanceMutationEntity
import com.constructionos.app.core.database.AttendanceMutationState
import com.constructionos.app.core.database.AttendanceSyncState
import com.constructionos.app.core.network.AttendanceEntriesWriteRequest
import com.constructionos.app.core.network.AttendanceEntryWriteRequest
import com.constructionos.app.core.network.AttendanceOfflineMutationRequest
import com.constructionos.app.core.network.AttendanceOfflineMutationResponse
import com.constructionos.app.core.network.AttendanceRegisterResponse
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.offline.DeviceRegistrar
import com.google.gson.Gson
import java.io.IOException
import java.util.UUID
import retrofit2.HttpException
import retrofit2.Response

class AttendanceMutationSyncService(
    private val api: ConstructionOsApi,
    private val dao: AttendanceDao,
    private val deviceRegistrar: DeviceRegistrar,
    private val gson: Gson = Gson(),
) {
    suspend fun drain() {
        dao.recoverInterruptedMutations()
        prepareDirtyEntryMutations()
        while (true) {
            val mutation = dao.pendingMutations(limit = 1).firstOrNull() ?: return
            if (!applyMutation(mutation)) return
            prepareDirtyEntryMutations()
        }
    }

    private suspend fun prepareDirtyEntryMutations() {
        val deviceId = deviceRegistrar.registeredDeviceId() ?: return
        dao.dirtyEditableRegisters().forEach { register ->
            if (register.syncState == AttendanceSyncState.NEEDS_ATTENTION) return@forEach
            if (dao.activeMutationCount(register.id, AttendanceRepository.OP_REPLACE) > 0) {
                return@forEach
            }
            val entries = dao.entries(register.id)
            val snapshotAt = System.currentTimeMillis()
            val request = AttendanceOfflineMutationRequest(
                deviceId = deviceId,
                clientMutationId = UUID.randomUUID().toString(),
                entityId = register.id,
                operation = AttendanceRepository.OP_REPLACE,
                baseRevision = register.revision,
                entries = AttendanceEntriesWriteRequest(
                    expectedRevision = register.revision,
                    entries = entries.map(AttendanceEntryEntity::toWriteRequest),
                ),
            )
            dao.upsertMutation(
                AttendanceMutationEntity(
                    clientMutationId = request.clientMutationId,
                    projectId = register.projectId,
                    entityId = register.id,
                    operation = AttendanceRepository.OP_REPLACE,
                    baseRevision = register.revision,
                    payloadJson = gson.toJson(request),
                    state = AttendanceMutationState.PENDING,
                    errorCode = null,
                    attemptCount = 0,
                    createdAt = snapshotAt,
                    updatedAt = snapshotAt,
                ),
            )
            dao.updateRegisterSyncState(
                registerId = register.id,
                syncState = AttendanceSyncState.WAITING_FOR_NETWORK,
                updatedAt = snapshotAt,
            )
        }
    }

    private suspend fun applyMutation(mutation: AttendanceMutationEntity): Boolean {
        val request = gson.fromJson(mutation.payloadJson, AttendanceOfflineMutationRequest::class.java)
        val attempt = mutation.attemptCount + 1
        val now = System.currentTimeMillis()
        dao.updateMutationState(
            clientMutationId = mutation.clientMutationId,
            state = AttendanceMutationState.IN_FLIGHT,
            errorCode = null,
            attemptCount = attempt,
            updatedAt = now,
        )

        val httpResponse = try {
            api.submitAttendanceMutation(mutation.projectId, request)
        } catch (error: IOException) {
            returnPending(mutation, attempt)
            throw error
        }
        val response = httpResponse.typedBodyOrNull()
        if (response == null) {
            if (httpResponse.code() == 403) {
                rejectTransport(mutation, attempt, "permission_denied")
                return false
            }
            if (httpResponse.code() in 400..499 && httpResponse.code() != 401) {
                rejectTransport(mutation, attempt, "http_${httpResponse.code()}")
                return false
            }
            returnPending(mutation, attempt)
            throw HttpException(httpResponse)
        }

        return when (response.status) {
            STATUS_APPLIED -> {
                applySuccess(mutation, response, attempt)
                true
            }

            STATUS_CONFLICT -> {
                finishAttention(mutation, response, attempt, AttendanceMutationState.CONFLICT)
                false
            }

            STATUS_REJECTED -> {
                finishAttention(mutation, response, attempt, AttendanceMutationState.REJECTED)
                false
            }

            else -> {
                returnPending(mutation, attempt)
                throw IOException("Unexpected attendance mutation status: ${response.status}")
            }
        }
    }

    private suspend fun applySuccess(
        mutation: AttendanceMutationEntity,
        response: AttendanceOfflineMutationResponse,
        attempt: Int,
    ) {
        val serverRegister = response.registerResult()
            ?: throw IOException("Applied attendance mutation did not return a register")
        when (mutation.operation) {
            AttendanceRepository.OP_CREATE ->
                applyCreateSuccess(mutation, response, serverRegister, attempt)

            AttendanceRepository.OP_REPLACE, AttendanceRepository.OP_SUBMIT ->
                applyExistingSuccess(mutation, response, serverRegister, attempt)

            else -> throw IOException("Unsupported attendance mutation operation: ${mutation.operation}")
        }
    }

    private suspend fun applyCreateSuccess(
        mutation: AttendanceMutationEntity,
        response: AttendanceOfflineMutationResponse,
        serverRegister: AttendanceRegisterResponse,
        attempt: Int,
    ) {
        val localEntries = dao.entries(mutation.entityId)
        val remappedEntries = localEntries.map { entry ->
            val synced = entry.localUpdatedAt < mutation.createdAt
            entry.copy(
                registerId = response.entityId,
                syncState = if (synced) AttendanceSyncState.SYNCED else AttendanceSyncState.SAVED_ON_DEVICE,
            )
        }
        val hasDirty = remappedEntries.any { it.syncState == AttendanceSyncState.SAVED_ON_DEVICE }
        val localNow = System.currentTimeMillis()
        dao.replaceRegisterIdentity(
            oldRegisterId = mutation.entityId,
            register = serverRegister.toEntity(
                syncState = if (hasDirty) AttendanceSyncState.SAVED_ON_DEVICE else AttendanceSyncState.SYNCED,
                localUpdatedAt = localNow,
            ),
            entries = remappedEntries,
        )
        dao.finishMutation(
            clientMutationId = mutation.clientMutationId,
            entityId = response.entityId,
            state = AttendanceMutationState.APPLIED,
            errorCode = null,
            attemptCount = attempt,
            updatedAt = localNow,
        )
    }

    private suspend fun applyExistingSuccess(
        mutation: AttendanceMutationEntity,
        response: AttendanceOfflineMutationResponse,
        serverRegister: AttendanceRegisterResponse,
        attempt: Int,
    ) {
        val localNow = System.currentTimeMillis()
        if (mutation.operation == AttendanceRepository.OP_REPLACE) {
            dao.markEntriesSyncedBefore(response.entityId, mutation.createdAt)
        }
        val hasDirty = dao.dirtyEntryCount(response.entityId) > 0
        dao.updateRegisterFromServer(
            registerId = response.entityId,
            status = serverRegister.status,
            revision = serverRegister.revision,
            syncState = if (hasDirty) AttendanceSyncState.SAVED_ON_DEVICE else AttendanceSyncState.SYNCED,
            serverUpdatedAt = serverRegister.updatedAt,
            localUpdatedAt = localNow,
        )
        dao.finishMutation(
            clientMutationId = mutation.clientMutationId,
            entityId = response.entityId,
            state = AttendanceMutationState.APPLIED,
            errorCode = null,
            attemptCount = attempt,
            updatedAt = localNow,
        )
    }

    private suspend fun finishAttention(
        mutation: AttendanceMutationEntity,
        response: AttendanceOfflineMutationResponse,
        attempt: Int,
        state: String,
    ) {
        val now = System.currentTimeMillis()
        dao.finishMutation(
            clientMutationId = mutation.clientMutationId,
            entityId = response.entityId,
            state = state,
            errorCode = response.errorCode,
            attemptCount = attempt,
            updatedAt = now,
        )
        val localRegister = dao.registerById(mutation.entityId) ?: dao.registerById(response.entityId)
        if (localRegister != null) {
            dao.updateRegisterSyncState(
                registerId = localRegister.id,
                syncState = AttendanceSyncState.NEEDS_ATTENTION,
                updatedAt = now,
            )
        }
    }

    private suspend fun rejectTransport(
        mutation: AttendanceMutationEntity,
        attempt: Int,
        errorCode: String,
    ) {
        val now = System.currentTimeMillis()
        dao.finishMutation(
            clientMutationId = mutation.clientMutationId,
            entityId = mutation.entityId,
            state = AttendanceMutationState.REJECTED,
            errorCode = errorCode,
            attemptCount = attempt,
            updatedAt = now,
        )
        dao.registerById(mutation.entityId)?.let { register ->
            dao.updateRegisterSyncState(
                registerId = register.id,
                syncState = AttendanceSyncState.NEEDS_ATTENTION,
                updatedAt = now,
            )
        }
    }

    private suspend fun returnPending(mutation: AttendanceMutationEntity, attempt: Int) {
        dao.updateMutationState(
            clientMutationId = mutation.clientMutationId,
            state = AttendanceMutationState.PENDING,
            errorCode = null,
            attemptCount = attempt,
            updatedAt = System.currentTimeMillis(),
        )
    }

    private fun AttendanceOfflineMutationResponse.registerResult(): AttendanceRegisterResponse? {
        val raw = result["register"] ?: return null
        return gson.fromJson(gson.toJson(raw), AttendanceRegisterResponse::class.java)
    }

    private fun Response<AttendanceOfflineMutationResponse>.typedBodyOrNull(): AttendanceOfflineMutationResponse? {
        if (isSuccessful) return body()
        val raw = errorBody()?.string()?.takeIf { it.isNotBlank() } ?: return null
        return runCatching {
            gson.fromJson(raw, AttendanceOfflineMutationResponse::class.java)
        }.getOrNull()
    }

    companion object {
        private const val STATUS_APPLIED = "applied"
        private const val STATUS_CONFLICT = "conflict"
        private const val STATUS_REJECTED = "rejected"
    }
}

internal fun AttendanceEntryEntity.toWriteRequest(): AttendanceEntryWriteRequest =
    AttendanceEntryWriteRequest(
        assignmentId = assignmentId,
        markStatus = markStatus,
        regularHours = regularHours,
        overtimeHours = overtimeHours,
        wbsCodeId = wbsCodeId,
        location = location,
        notes = notes,
    )
