package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface DprCustomFieldDao {
    @Query(
        """
        SELECT * FROM dpr_custom_field_definitions
        WHERE project_id = :projectId
        ORDER BY display_order, field_key, definition_id
        """,
    )
    fun observeDefinitions(projectId: String): Flow<List<DprCustomFieldDefinitionEntity>>

    @Query(
        """
        SELECT * FROM dpr_custom_field_definitions
        WHERE project_id = :projectId
        ORDER BY display_order, field_key, definition_id
        """,
    )
    suspend fun definitions(projectId: String): List<DprCustomFieldDefinitionEntity>

    @Query(
        """
        SELECT * FROM dpr_custom_field_values
        WHERE report_id = :reportId
        ORDER BY definition_id
        """,
    )
    fun observeValues(reportId: String): Flow<List<DprCustomFieldValueEntity>>

    @Query(
        """
        SELECT * FROM dpr_custom_field_values
        WHERE report_id = :reportId
        ORDER BY definition_id
        """,
    )
    suspend fun values(reportId: String): List<DprCustomFieldValueEntity>

    @Upsert
    suspend fun upsertDefinitions(rows: List<DprCustomFieldDefinitionEntity>)

    @Upsert
    suspend fun upsertValues(rows: List<DprCustomFieldValueEntity>)

    @Query("DELETE FROM dpr_custom_field_definitions WHERE project_id = :projectId")
    suspend fun clearDefinitions(projectId: String)

    @Query("DELETE FROM dpr_custom_field_values WHERE report_id = :reportId")
    suspend fun clearValues(reportId: String)

    @Transaction
    suspend fun replaceDefinitions(
        projectId: String,
        rows: List<DprCustomFieldDefinitionEntity>,
    ) {
        clearDefinitions(projectId)
        if (rows.isNotEmpty()) upsertDefinitions(rows)
    }

    @Transaction
    suspend fun replaceValues(
        reportId: String,
        rows: List<DprCustomFieldValueEntity>,
    ) {
        clearValues(reportId)
        if (rows.isNotEmpty()) upsertValues(rows)
    }
}
