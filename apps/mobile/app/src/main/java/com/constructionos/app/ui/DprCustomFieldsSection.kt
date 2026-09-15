package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.DprCustomFieldDefinitionEntity
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.database.DprSyncState
import com.constructionos.app.core.dpr.DprCustomFieldRepository
import com.constructionos.app.core.dpr.DprRepository
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.gson.JsonPrimitive
import kotlinx.coroutines.launch

@Composable
fun DprCustomFieldsSection(
    projectId: String,
    report: DprReportEntity,
    repository: DprCustomFieldRepository,
    editable: Boolean,
) {
    val definitions by remember(projectId) {
        repository.observeDefinitions(projectId)
    }.collectAsState(initial = emptyList())
    val values by remember(report.id) {
        repository.observeValues(report.id)
    }.collectAsState(initial = emptyList())
    val scope = rememberCoroutineScope()
    val editorValues = remember(report.id) { mutableStateMapOf<String, String?>() }
    var dirty by remember(report.id) { mutableStateOf(false) }
    var saving by remember(report.id) { mutableStateOf(false) }
    var message by remember(report.id) { mutableStateOf<String?>(null) }

    LaunchedEffect(projectId) {
        runCatching { repository.refreshDefinitions(projectId) }
    }

    LaunchedEffect(
        report.id,
        report.serverId,
        report.revision,
        report.syncState,
    ) {
        if (report.serverId != null && report.revision > 0) {
            runCatching { repository.refreshReport(report.id) }
        }
    }

    LaunchedEffect(definitions, values, dirty) {
        if (!dirty) {
            val stored = values.associate { it.definitionId to it.valueJson }
            editorValues.clear()
            definitions.forEach { definition ->
                editorValues[definition.definitionId] = if (definition.definitionId in stored) {
                    stored[definition.definitionId]
                } else {
                    definition.defaultValueJson
                }
            }
        }
    }

    if (definitions.isEmpty()) return

    HorizontalDivider(modifier = Modifier.padding(top = 22.dp))
    Text(
        "Additional fields",
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(top = 16.dp),
    )
    Text(
        "Configured by your company for this Daily Report. Required fields must be complete before submission.",
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier.padding(top = 3.dp, bottom = 8.dp),
    )

    definitions.forEach { definition ->
        DprCustomFieldEditor(
            definition = definition,
            rawJson = editorValues[definition.definitionId],
            editable = editable && definition.editable && definition.fieldType !in REFERENCE_TYPES,
            onChange = { newValue ->
                editorValues[definition.definitionId] = newValue
                dirty = true
                message = null
            },
        )
    }

    if (definitions.any { it.fieldType in REFERENCE_TYPES }) {
        Text(
            "Reference/attachment custom fields are shown read-only on mobile. Use the web workspace to change them.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp),
        )
    }

    if (editable) {
        Button(
            onClick = {
                scope.launch {
                    saving = true
                    message = null
                    val editableValues = definitions
                        .filter { it.editable && it.fieldType !in REFERENCE_TYPES }
                        .associate { definition ->
                            definition.definitionId to editorValues[definition.definitionId]
                        }
                    runCatching {
                        validateRequiredMobileFields(definitions, editableValues)
                        repository.saveValues(report.id, editableValues)
                    }.onSuccess {
                        dirty = false
                        message = "Saved on device. Changes will sync in the background."
                    }.onFailure { error ->
                        message = error.message ?: "Custom fields could not be saved."
                    }
                    saving = false
                }
            },
            enabled = !saving && report.status == DprRepository.STATUS_DRAFT &&
                report.syncState != DprSyncState.NEEDS_ATTENTION,
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        ) {
            Text(if (saving) "Saving…" else "Save additional fields")
        }
    }

    message?.let {
        Text(
            it,
            style = MaterialTheme.typography.bodySmall,
            color = if (it.startsWith("Saved")) {
                MaterialTheme.colorScheme.onSurfaceVariant
            } else {
                MaterialTheme.colorScheme.error
            },
            modifier = Modifier.padding(top = 6.dp),
        )
    }

    Text(
        customFieldSyncLabel(report.syncState),
        style = MaterialTheme.typography.bodySmall,
        color = if (report.syncState == DprSyncState.NEEDS_ATTENTION) {
            MaterialTheme.colorScheme.error
        } else {
            MaterialTheme.colorScheme.onSurfaceVariant
        },
        modifier = Modifier.padding(top = 4.dp, bottom = 12.dp),
    )
}

@Composable
private fun DprCustomFieldEditor(
    definition: DprCustomFieldDefinitionEntity,
    rawJson: String?,
    editable: Boolean,
    onChange: (String?) -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 7.dp)) {
        Text(
            buildString {
                append(definition.label)
                if (definition.required) append(" *")
            },
            style = MaterialTheme.typography.labelLarge,
        )
        definition.description?.takeIf { it.isNotBlank() }?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 2.dp),
            )
        }

        when (definition.fieldType) {
            "boolean" -> {
                val checked = rawJson.toBooleanValue()
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 5.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Checkbox(
                        checked = checked,
                        onCheckedChange = if (editable) {
                            { value -> onChange(JsonPrimitive(value).toString()) }
                        } else {
                            null
                        },
                    )
                    Text(if (checked) "Yes" else "No")
                }
            }

            "single_select" -> {
                val selected = rawJson.toSimpleText()
                definition.options().forEach { option ->
                    OutlinedButton(
                        onClick = { onChange(JsonPrimitive(option.key).toString()) },
                        enabled = editable,
                        modifier = Modifier.fillMaxWidth().padding(top = 5.dp),
                    ) {
                        Text(if (selected == option.key) "✓ ${option.label}" else option.label)
                    }
                }
            }

            "multi_select" -> {
                val selected = rawJson.toStringSet()
                definition.options().forEach { option ->
                    val checked = option.key in selected
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 3.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(
                            checked = checked,
                            onCheckedChange = if (editable) {
                                { value ->
                                    val next = selected.toMutableSet()
                                    if (value) next += option.key else next -= option.key
                                    onChange(next.sorted().toJsonArray())
                                }
                            } else {
                                null
                            },
                        )
                        Text(option.label)
                    }
                }
            }

            "currency" -> {
                val current = rawJson.toObject()
                val amount = current?.get("amount")?.asString.orEmpty()
                val currency = current?.get("currency")?.asString.orEmpty()
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 5.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedTextField(
                        value = amount,
                        onValueChange = { value ->
                            onChange(currencyJson(value, currency))
                        },
                        enabled = editable,
                        label = { Text("Amount") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = currency,
                        onValueChange = { value ->
                            onChange(currencyJson(amount, value.uppercase()))
                        },
                        enabled = editable,
                        label = { Text("Currency") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            "measurement" -> {
                val current = rawJson.toObject()
                val value = current?.get("value")?.asString.orEmpty()
                val unit = current?.get("unit")?.asString.orEmpty()
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 5.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedTextField(
                        value = value,
                        onValueChange = { next -> onChange(measurementJson(next, unit)) },
                        enabled = editable,
                        label = { Text("Value") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = unit,
                        onValueChange = { next -> onChange(measurementJson(value, next)) },
                        enabled = editable,
                        label = { Text("Unit") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            in REFERENCE_TYPES -> {
                OutlinedTextField(
                    value = rawJson.toSimpleText(),
                    onValueChange = {},
                    enabled = false,
                    label = { Text("Managed on web") },
                    modifier = Modifier.fillMaxWidth().padding(top = 5.dp),
                )
            }

            else -> {
                val label = when (definition.fieldType) {
                    "date" -> "YYYY-MM-DD"
                    "datetime" -> "ISO date/time with timezone"
                    "integer" -> "Whole number"
                    "decimal" -> "Number"
                    else -> definition.label
                }
                OutlinedTextField(
                    value = rawJson.toSimpleText(),
                    onValueChange = { value ->
                        onChange(value.toPrimitiveJson(definition.fieldType))
                    },
                    enabled = editable,
                    label = { Text(label) },
                    minLines = if (definition.fieldType == "long_text") 3 else 1,
                    maxLines = if (definition.fieldType == "long_text") 6 else 1,
                    modifier = Modifier.fillMaxWidth().padding(top = 5.dp),
                )
            }
        }
    }
}

private fun validateRequiredMobileFields(
    definitions: List<DprCustomFieldDefinitionEntity>,
    values: Map<String, String?>,
) {
    definitions
        .filter { it.required && it.editable && it.fieldType !in REFERENCE_TYPES }
        .forEach { definition ->
            val raw = values[definition.definitionId]
            require(!raw.isNullOrBlank() && raw != "null" && raw.toSimpleText().isNotBlank()) {
                "${definition.label} is required."
            }
        }
}

private data class CustomFieldOption(val key: String, val label: String)

private fun DprCustomFieldDefinitionEntity.options(): List<CustomFieldOption> = runCatching {
    JsonParser.parseString(optionsJson).asJsonArray.mapNotNull { element ->
        val item = element.asJsonObject
        val key = item.get("key")?.asString ?: return@mapNotNull null
        val label = item.get("label")?.asString ?: key
        CustomFieldOption(key, label)
    }
}.getOrDefault(emptyList())

private fun String?.toSimpleText(): String {
    if (this.isNullOrBlank()) return ""
    return runCatching {
        val parsed = JsonParser.parseString(this)
        if (parsed.isJsonNull) "" else if (parsed.isJsonPrimitive) parsed.asString else parsed.toString()
    }.getOrDefault("")
}

private fun String?.toBooleanValue(): Boolean = runCatching {
    !this.isNullOrBlank() && JsonParser.parseString(this).asBoolean
}.getOrDefault(false)

private fun String?.toStringSet(): Set<String> = runCatching {
    if (this.isNullOrBlank()) return@runCatching emptySet()
    JsonParser.parseString(this).asJsonArray.map { it.asString }.toSet()
}.getOrDefault(emptySet())

private fun String?.toObject(): JsonObject? = runCatching {
    if (this.isNullOrBlank()) null else JsonParser.parseString(this).asJsonObject
}.getOrNull()

private fun Set<String>.toJsonArray(): String {
    val array = JsonArray()
    forEach { array.add(it) }
    return array.toString()
}

private fun currencyJson(amount: String, currency: String): String? {
    if (amount.isBlank() && currency.isBlank()) return null
    return JsonObject().apply {
        addProperty("amount", amount)
        addProperty("currency", currency)
    }.toString()
}

private fun measurementJson(value: String, unit: String): String? {
    if (value.isBlank() && unit.isBlank()) return null
    return JsonObject().apply {
        addProperty("value", value)
        addProperty("unit", unit)
    }.toString()
}

private fun String.toPrimitiveJson(fieldType: String): String? {
    if (isBlank()) return null
    return when (fieldType) {
        "integer", "decimal" -> this
        else -> JsonPrimitive(this).toString()
    }
}

private fun customFieldSyncLabel(syncState: String): String = when (syncState) {
    DprSyncState.SAVED_ON_DEVICE -> "Saved on device"
    DprSyncState.WAITING_FOR_NETWORK -> "Waiting for network"
    DprSyncState.SYNCING -> "Syncing"
    DprSyncState.SYNCED -> "Synced"
    DprSyncState.NEEDS_ATTENTION -> "Needs attention"
    else -> syncState.replace('_', ' ')
}

private val REFERENCE_TYPES = setOf("user", "company", "project", "attachment")
