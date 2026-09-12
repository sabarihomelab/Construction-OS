package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.constructionos.app.core.database.DprDelayEntity
import com.constructionos.app.core.database.DprReportEntity
import com.constructionos.app.core.dpr.DprDelayDraft

@Composable
internal fun DprDelaysSection(
    report: DprReportEntity,
    rows: List<DprDelayEntity>,
    editable: Boolean,
    onSave: (List<DprDelayDraft>) -> Unit,
) {
    var category by rememberSaveable(report.id) { mutableStateOf("") }
    var description by rememberSaveable(report.id) { mutableStateOf("") }
    var lostHours by rememberSaveable(report.id) { mutableStateOf("") }
    var responsibleParty by rememberSaveable(report.id) { mutableStateOf("") }
    var scheduleImpact by rememberSaveable(report.id) { mutableStateOf(false) }
    var notes by rememberSaveable(report.id) { mutableStateOf("") }

    HorizontalDivider(modifier = Modifier.padding(top = 22.dp))
    Text(
        "Delays / blockers",
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(top = 16.dp),
    )
    Text(
        if (rows.isEmpty()) {
            "No delays or blockers recorded"
        } else {
            "${rows.size} delay${if (rows.size == 1) "" else "s"} / blocker${if (rows.size == 1) "" else "s"} recorded"
        },
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier.padding(top = 3.dp, bottom = 8.dp),
    )

    rows.forEach { row ->
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 10.dp),
        ) {
            Text(
                row.category?.takeIf { it.isNotBlank() } ?: "Blocker",
                style = MaterialTheme.typography.labelLarge,
            )
            Text(
                row.description,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 2.dp),
            )
            val details = buildList {
                row.lostHours?.takeIf { it.isNotBlank() }?.let { add("$it lost hours") }
                row.responsibleParty?.takeIf { it.isNotBlank() }?.let { add(it) }
                if (row.scheduleImpact) add("Schedule impact")
            }.joinToString(" • ")
            if (details.isNotBlank()) {
                Text(
                    details,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 3.dp),
                )
            }
            row.notes?.takeIf { it.isNotBlank() }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 3.dp),
                )
            }
            if (editable) {
                TextButton(
                    onClick = {
                        onSave(rows.filterNot { it.id == row.id }.map(DprDelayEntity::toDraft))
                    },
                ) {
                    Text("Remove")
                }
            }
        }
        HorizontalDivider()
    }

    if (!editable) return

    Text(
        "Add delay / blocker",
        style = MaterialTheme.typography.titleSmall,
        modifier = Modifier.padding(top = 18.dp),
    )
    OutlinedTextField(
        value = category,
        onValueChange = { category = it },
        label = { Text("Category (optional)") },
        supportingText = { Text("For example: Weather, Access, Material, RFI") },
        singleLine = true,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    OutlinedTextField(
        value = description,
        onValueChange = { description = it },
        label = { Text("What is blocking the work?") },
        minLines = 2,
        maxLines = 5,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        OutlinedTextField(
            value = lostHours,
            onValueChange = { lostHours = it },
            label = { Text("Lost hours") },
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
        OutlinedTextField(
            value = responsibleParty,
            onValueChange = { responsibleParty = it },
            label = { Text("Responsible party") },
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
    }
    OutlinedButton(
        onClick = { scheduleImpact = !scheduleImpact },
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    ) {
        Text(if (scheduleImpact) "Schedule impact: Yes" else "Schedule impact: No")
    }
    OutlinedTextField(
        value = notes,
        onValueChange = { notes = it },
        label = { Text("Blocker notes (optional)") },
        minLines = 2,
        maxLines = 4,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
    )
    Button(
        onClick = {
            val next = rows.map(DprDelayEntity::toDraft) + DprDelayDraft(
                category = category,
                description = description,
                lostHours = lostHours,
                responsibleParty = responsibleParty,
                scheduleImpact = scheduleImpact,
                notes = notes,
            )
            onSave(next)
            category = ""
            description = ""
            lostHours = ""
            responsibleParty = ""
            scheduleImpact = false
            notes = ""
        },
        enabled = description.isNotBlank(),
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 12.dp, bottom = 24.dp),
    ) {
        Text("Add delay / blocker")
    }
}

private fun DprDelayEntity.toDraft(): DprDelayDraft = DprDelayDraft(
    id = id,
    category = category,
    description = description,
    startedAt = startedAt,
    endedAt = endedAt,
    lostHours = lostHours,
    responsibleParty = responsibleParty,
    scheduleImpact = scheduleImpact,
    notes = notes,
)
