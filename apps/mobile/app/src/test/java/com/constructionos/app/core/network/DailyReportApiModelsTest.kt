package com.constructionos.app.core.network

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DailyReportApiModelsTest {
    @Test
    fun headerUpdateMutationCarriesTheSameBaseRevisionAsItsUpdate() {
        val update = DailyReportUpdateRequest(
            expectedRevision = 7,
            weatherCondition = "Overcast",
            notes = "North elevation formwork continued",
        )
        val request = DailyReportOfflineMutationRequest(
            deviceId = "00000000-0000-0000-0000-000000000001",
            clientMutationId = "00000000-0000-0000-0000-000000000002",
            entityId = "00000000-0000-0000-0000-000000000003",
            operation = "update_header",
            baseRevision = update.expectedRevision,
            update = update,
        )

        assertEquals(7, request.baseRevision)
        assertEquals(7, request.update?.expectedRevision)
        assertEquals("update_header", request.operation)
    }

    @Test
    fun headerUpdateSerializesOnlyTheUpdateOperationPayload() {
        val request = DailyReportOfflineMutationRequest(
            deviceId = "device-id",
            clientMutationId = "mutation-id",
            entityId = "report-id",
            operation = "update_header",
            baseRevision = 3,
            update = DailyReportUpdateRequest(
                expectedRevision = 3,
                weatherCondition = "Clear",
                notes = "Concrete pour completed",
            ),
        )

        val json = Gson().toJson(request)

        assertTrue(json.contains("\"operation\":\"update_header\""))
        assertTrue(json.contains("\"base_revision\":3"))
        assertTrue(json.contains("\"expected_revision\":3"))
        assertFalse(json.contains("\"create\""))
        assertFalse(json.contains("\"action\""))
    }
}
