package com.constructionos.app.core.attendance

import com.constructionos.app.core.database.AttendanceDao
import com.constructionos.app.core.database.AttendanceEntryEntity
import com.constructionos.app.core.database.AttendanceMutationEntity
import com.constructionos.app.core.database.AttendanceMutationState
import com.constructionos.app.core.database.AttendanceRegisterEntity
import com.constructionos.app.core.database.AttendanceRosterEntity
import com.constructionos.app.core.database.AttendanceSyncState
import com.constructionos.app.core.network.AttendanceOfflineMutationRequest
import com.constructionos.app.core.network.AttendanceRegisterCreateRequest
import com.constructionos.app.core.network.AttendanceRegisterDetailResponse
import com.constructionos.app.core.network.AttendanceRegisterResponse
import com.constructionos.app.core.network.AttendanceRosterResponse
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.offline.DeviceRegistrar
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.google.gson.Gson
import java.util.UUID
import kotlinx.coroutines.flow.Flow

class AttendanceRepository(
    private val api: ConstructionOsApi,
    private val dao: AttendanceDao,
    private val deviceRegistrar: DeviceRegistrar,
    private val syncScheduler: WorkspaceSyncScheduler,
    private val gson: Gson = Gson(),
) {
    fun observeRoster(projectId: String, attendanceDate: String): Flow<List<AttendanceRosterEntity>> =
        dao.observeActiveRoster(projectId, attendanceDate)

    fun observeRegisters(projectId: String, attendanceDate: String): Flow<List<AttendanceRegisterEntity>> =
        dao.observeRegisters(projectId, attendanceDate)

    fun observeEntries(registerId: String): Flow<List<AttendanceEntryEntity>> =
        dao.observeEntries(registerId)

    fun observePendingMutationCount(projectId: String): Flow<Int> =
        dao.observePendingMutationCount(projectId)

    fun observeAttentionCount(projectId: String): Flow<Int> =
        dao.observeAttentionCount(projectId)

    suspend fun refreshRoster(projectId: String, attendanceDate: String) {
        val roster = api.attendanceRoster(projectId, attendanceDate)
            .map(AttendanceRosterResponse::toEntity)
        dao.replaceRoster(projectId, roster)
    }

    suspend fun refreshDay(projectId: String, attendanceDate: String) {
        api.attendanceRegisters(projectId)
            .asSequence()
            .filter { it.attendanceDate == attendanceDate }
            .forEach { remote ->
                val local = dao.register(projectId, remote.attendanceDate, remote.shiftCode)
                if (local != null && local.syncState != AttendanceSyncState.SYNCED) {
                    return@forEach
                }
                if (local != null && hasActiveMutation(local.id)) {
                    return@forEach
                }
                val detail = api.attendanceRegister(projectId, remote.id)
                cacheServerDetail(detail)
            }
    }

    suspend fun createLocalRegister(
        organizationId: String,
        projectId: String,
        attendanceDate: String,
        shiftCode: String = "day",
        notes: String? = null,
    ): String {
        dao.register(projectId, attendanceDate, shiftCode)?.let { return it.id }
        val deviceId = requireNotNull(deviceRegistrar.registeredDeviceId()) {
            "This device must connect once before attendance can be created offline."
        }
        val roster = dao.activeRoster(projectId, attendanceDate)
        val registerId = UUID.randomUUID().toString()
        val now = System.currentTimeMillis()
        val register = AttendanceRegisterEntity(
            id = registerId,
            organizationId = organizationId,
            projectId = projectId,
            attendanceDate = attendanceDate,
            shiftCode = shiftCode,
            status = STATUS_DRAFT,
            revision = 0,
            notes = notes,
            syncState = AttendanceSyncState.SAVED_ON_DEVICE,
            serverUpdatedAt = null,
            localUpdatedAt = now,
        )
        val entries = roster.map { worker ->
            AttendanceEntryEntity(
                registerId = registerId,
                assignmentId = worker.assignmentId,
                serverEntryId = null,
                projectId = projectId,
                workerId = worker.workerId,
                workerNumber = worker.workerNumber,
                workerName = worker.workerName,
                crewId = worker.crewId,
                employerPartyId = worker.employerPartyId,
                trade = worker.trade,
                markStatus = MARK_NOT_MARKED,
                regularHours = "0",
                overtimeHours = "0",
                wbsCodeId = null,
                location = null,
                notes = null,
                syncState = AttendanceSyncState.SAVED_ON_DEVICE,
                localUpdatedAt = now - 1,
            )
        }
        val request = AttendanceOfflineMutationRequest(
            deviceId = deviceId,
            clientMutationId = UUID.randomUUID().toString(),
            entityId = registerId,
            operation = OP_CREATE,
            create = AttendanceRegisterCreateRequest(
                attendanceDate = attendanceDate,
                shiftCode = shiftCode,
                notes = notes,
                populateActiveWorkers = true,
            ),
        )
        val mutation = AttendanceMutationEntity(
            clientMutationId = request.clientMutationId,
            projectId = projectId,
            entityId = registerId,
            operation = OP_CREATE,
            baseRevision = null,
            payloadJson = gson.toJson(request),
            state = AttendanceMutationState.PENDING,
            errorCode = null,
            attemptCount = 0,
            createdAt = now,
            updatedAt = now,
        )
        dao.createLocalRegister(register, entries, mutation)
        syncScheduler.scheduleOnce()
        return registerId
    }

    suspend fun markAll(registerId: String, markStatus: String) {
        require(markStatus in MARK_STATUSES) { "Unsupported attendance mark" }
        requireEditable(registerId)
        dao.markAllAndDirty(registerId, markStatus, System.currentTimeMillis())
        syncScheduler.scheduleOnce()
    }

    suspend fun markRemainingPresent(registerId: String) {
        requireEditable(registerId)
        dao.markUnmarkedAndDirty(
            registerId = registerId,
            markStatus = MARK_PRESENT,
            updatedAt = System.currentTimeMillis(),
        )
        syncScheduler.scheduleOnce()
    }

    suspend fun markWorker(registerId: String, assignmentId: String, markStatus: String) {
        require(markStatus in MARK_STATUSES) { "Unsupported attendance mark" }
        requireEditable(registerId)
        dao.markEntryAndDirty(
            registerId = registerId,
            assignmentId = assignmentId,
            markStatus = markStatus,
            updatedAt = System.currentTimeMillis(),
        )
        syncScheduler.scheduleOnce()
    }

    suspend fun clearProject(projectId: String) {
        dao.clearRoster(projectId)
    }

    private suspend fun requireEditable(registerId: String) {
        val register = requireNotNull(dao.registerById(registerId)) { "Attendance register was not found" }
        require(register.status == STATUS_DRAFT || register.status == STATUS_REJECTED) {
            "Attendance must be reopened before it can be edited."
        }
    }

    private suspend fun hasActiveMutation(registerId: String): Boolean =
        dao.activeMutationCount(registerId, OP_CREATE) > 0 ||
            dao.activeMutationCount(registerId, OP_REPLACE) > 0 ||
            dao.activeMutationCount(registerId, OP_SUBMIT) > 0

    private suspend fun cacheServerDetail(detail: AttendanceRegisterDetailResponse) {
        val now = System.currentTimeMillis()
        val register = detail.toEntity(AttendanceSyncState.SYNCED, now)
        val entries = detail.entries.map { it.toEntity(detail.id, detail.projectId, now) }
        dao.cacheServerRegister(register, entries)
    }

    companion object {
        const val STATUS_DRAFT = "draft"
        const val STATUS_REJECTED = "rejected"
        const val MARK_NOT_MARKED = "not_marked"
        const val MARK_PRESENT = "present"
        const val MARK_ABSENT = "absent"
        const val MARK_HALF_DAY = "half_day"
        const val MARK_LEAVE = "leave"
        const val MARK_WEEKLY_OFF = "weekly_off"
        const val OP_CREATE = "create_register"
        const val OP_REPLACE = "replace_entries"
        const val OP_SUBMIT = "submit"

        val MARK_STATUSES = setOf(
            MARK_NOT_MARKED,
            MARK_PRESENT,
            MARK_ABSENT,
            MARK_HALF_DAY,
            MARK_LEAVE,
            MARK_WEEKLY_OFF,
        )
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

internal fun AttendanceRegisterResponse.toEntity(
    syncState: String,
    localUpdatedAt: Long,
): AttendanceRegisterEntity = AttendanceRegisterEntity(
    id = id,
    organizationId = organizationId,
    projectId = projectId,
    attendanceDate = attendanceDate,
    shiftCode = shiftCode,
    status = status,
    revision = revision,
    notes = notes,
    syncState = syncState,
    serverUpdatedAt = updatedAt,
    localUpdatedAt = localUpdatedAt,
)

internal fun AttendanceRegisterDetailResponse.toEntity(
    syncState: String,
    localUpdatedAt: Long,
): AttendanceRegisterEntity = AttendanceRegisterEntity(
    id = id,
    organizationId = organizationId,
    projectId = projectId,
    attendanceDate = attendanceDate,
    shiftCode = shiftCode,
    status = status,
    revision = revision,
    notes = notes,
    syncState = syncState,
    serverUpdatedAt = updatedAt,
    localUpdatedAt = localUpdatedAt,
)

internal fun com.constructionos.app.core.network.AttendanceEntryResponse.toEntity(
    registerId: String,
    projectId: String,
    localUpdatedAt: Long,
): AttendanceEntryEntity = AttendanceEntryEntity(
    registerId = registerId,
    assignmentId = assignmentId,
    serverEntryId = id,
    projectId = projectId,
    workerId = workerId,
    workerNumber = contextSnapshot["worker_number"]?.toString().orEmpty(),
    workerName = contextSnapshot["worker_name"]?.toString().orEmpty(),
    crewId = crewId,
    employerPartyId = employerPartyId,
    trade = trade,
    markStatus = markStatus,
    regularHours = regularHours,
    overtimeHours = overtimeHours,
    wbsCodeId = wbsCodeId,
    location = location,
    notes = notes,
    syncState = AttendanceSyncState.SYNCED,
    localUpdatedAt = localUpdatedAt,
)
