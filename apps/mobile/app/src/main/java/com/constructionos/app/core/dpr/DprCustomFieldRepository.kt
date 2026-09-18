package com.constructionos.app.core.dpr

import com.constructionos.app.core.database.DprCustomFieldDao
import com.constructionos.app.core.database.DprCustomFieldDefinitionEntity
import com.constructionos.app.core.database.DprCustomFieldValueEntity
import com.constructionos.app.core.database.DprDao
import com.constructionos.app.core.database.DprMutationEntity
import com.constructionos.app.core.database.DprMutationState
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.network.DprCustomFieldApi
import com.constructionos.app.core.network.DprCustomFieldDefinitionResponse
import com.constructionos.app.core.network.DprCustomFieldValueWriteRequest
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.google.gson.Gson
import com.google.gson.JsonNull
import com.google.gson.JsonParser
import java.util.UUID
import kotlinx.coroutines.flow.Flow

class DprCustomFieldRepository(
    private val api: DprCustomFieldApi,
    private val customFieldDao: DprCustomFieldDao,
    private val dprDao: DprDao,
    private val syncScheduler: WorkspaceSyncScheduler,
    private val gson: Gson = Gson(),
) {
    fun observeDefinitions(projectId: String): Flow<List<DprCustomFieldDefinitionEntity>> =
        customFieldDao.observeDefinitions(projectId)

    fun observeValues(reportId: String): Flow<List<DprCustomFieldValueEntity>> =
        customFieldDao.observeValues(reportId)

    suspend fun refreshDefinitions(projectId: String) {
        val response = api.definitions(projectId)
        require(response.projectId == projectId) { "Company server returned custom fields for the wrong project." }
        val refreshedAt = System.currentTimeMillis()
        customFieldDao.replaceDefinitions(
            projectId = projectId,
            rows = response.fields.map { it.toEntity(projectId, refreshedAt, gson) },
        )
    }

    suspend fun refreshReport(reportId: String) {
        val report = dprDao.reportById(reportId) ?: return
        val serverId = report.serverId ?: return
        if (report.syncState == DprSyncState.NEEDS_ATTENTION) return
        if (dprDao.activeMutationCount(report.id) > 0) return

        val response = api.values(report.projectId, serverId)
        require(response.reportId == serverId) { "Company server returned custom fields for the wrong report." }
        if (response.reportRevision != report.revision) return

        val refreshedAt = System.currentTimeMillis()
        customFieldDao.replaceValues(
            reportId = report.id,
            rows = response.values.map { row ->
                DprCustomFieldValueEntity(
                    reportId = report.id,
                    projectId = report.projectId,
                    definitionId = row.definitionId,
                    valueJson = row.value?.takeUnless { it.isJsonNull }?.toString(),
                    refreshedAt = refreshedAt,
                )
            },
        )
    }

    suspend fun saveValues(
        reportId: String,
        valuesJson: Map<String, String?>,
        reason: String? = null,
    ) {
        val report = requireNotNull(dprDao.reportById(reportId)) { "Daily report was not found." }
        require(report.status == DprRepository.STATUS_DRAFT) { "Only a draft daily report can be edited." }
        require(report.syncState != DprSyncState.NEEDS_ATTENTION) {
            "Resolve the daily report sync issue before saving custom fields."
        }
        require(valuesJson.size <= 200) { "A daily report can contain at most 200 custom field values." }

        val definitions = customFieldDao.definitions(report.projectId).associateBy { it.definitionId }
        require(definitions.isNotEmpty() || valuesJson.isEmpty()) {
            "Custom field configuration is not available on this device yet. Connect once and refresh."
        }

        val writes = valuesJson.map { (definitionId, rawJson) ->
            val definition = requireNotNull(definitions[definitionId]) {
                "A configured custom field is no longer available. Refresh the daily report."
            }
            require(definition.editable) { "${definition.label} is read-only." }
            val value = rawJson.toJsonValue()
            if (definition.required) {
                require(value !== JsonNull.INSTANCE && !value.isEmptyTextValue()) {
                    "${definition.label} is required."
                }
            }
            DprCustomFieldValueWriteRequest(
                definitionId = definitionId,
                value = value,
            )
        }

        val payload = DprPendingCustomFieldsPayload(
            values = writes,
            reason = reason?.trim()?.takeIf { it.isNotEmpty() },
        )
        val now = System.currentTimeMillis()
        val existing = dprDao.mutation(report.id, OP_REPLACE_CUSTOM_FIELDS)
        if (existing != null) {
            dprDao.updatePendingMutationPayload(
                mutationId = existing.clientMutationId,
                payloadJson = gson.toJson(payload),
                updatedAt = now,
            )
        } else {
            dprDao.upsertMutation(
                DprMutationEntity(
                    clientMutationId = UUID.randomUUID().toString(),
                    projectId = report.projectId,
                    reportId = report.id,
                    operation = OP_REPLACE_CUSTOM_FIELDS,
                    payloadJson = gson.toJson(payload),
                    state = DprMutationState.PENDING,
                    errorCode = null,
                    attemptCount = 0,
                    createdAt = now,
                    updatedAt = now,
                ),
            )
        }
        dprDao.updateReportSyncState(report.id, DprSyncState.SAVED_ON_DEVICE, now)
        customFieldDao.upsertValues(
            valuesJson.map { (definitionId, rawJson) ->
                DprCustomFieldValueEntity(
                    reportId = report.id,
                    projectId = report.projectId,
                    definitionId = definitionId,
                    valueJson = rawJson,
                    refreshedAt = now,
                )
            },
        )
        syncScheduler.scheduleOnce()
    }

    companion object {
        const val OP_REPLACE_CUSTOM_FIELDS = "replace_custom_fields"
    }
}

internal data class DprPendingCustomFieldsPayload(
    val values: List<DprCustomFieldValueWriteRequest>,
    val reason: String? = null,
)

private fun DprCustomFieldDefinitionResponse.toEntity(
    projectId: String,
    refreshedAt: Long,
    gson: Gson,
): DprCustomFieldDefinitionEntity = DprCustomFieldDefinitionEntity(
    projectId = projectId,
    definitionId = definitionId,
    key = key,
    label = label,
    description = description,
    fieldType = fieldType,
    required = required,
    editable = editable,
    displayOrder = displayOrder,
    defaultValueJson = defaultValue?.takeUnless { it.isJsonNull }?.toString(),
    optionsJson = gson.toJson(options),
    refreshedAt = refreshedAt,
)

private fun String?.toJsonValue() = when {
    this == null -> JsonNull.INSTANCE
    else -> runCatching { JsonParser.parseString(this) }
        .getOrElse { throw IllegalArgumentException("Custom field value is not valid JSON.", it) }
}

private fun com.google.gson.JsonElement.isEmptyTextValue(): Boolean =
    isJsonPrimitive && asJsonPrimitive.isString && asString.trim().isEmpty()
