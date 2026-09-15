package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface BoqFieldDao {
    @Query(
        """
        SELECT * FROM boq_field_items
        WHERE project_id = :projectId
        ORDER BY sort_order
        """,
    )
    fun observe(projectId: String): Flow<List<BoqFieldEntity>>

    @Query(
        """
        SELECT * FROM boq_field_items
        WHERE project_id = :projectId
          AND (
            boq_code LIKE '%' || :query || '%' COLLATE NOCASE OR
            boq_name LIKE '%' || :query || '%' COLLATE NOCASE OR
            item_code LIKE '%' || :query || '%' COLLATE NOCASE OR
            description LIKE '%' || :query || '%' COLLATE NOCASE
          )
        ORDER BY sort_order
        """,
    )
    fun search(projectId: String, query: String): Flow<List<BoqFieldEntity>>

    @Upsert
    suspend fun upsert(rows: List<BoqFieldEntity>)

    @Query("DELETE FROM boq_field_items WHERE project_id = :projectId")
    suspend fun deleteProject(projectId: String)

    @Transaction
    suspend fun replaceProject(projectId: String, rows: List<BoqFieldEntity>) {
        deleteProject(projectId)
        if (rows.isNotEmpty()) upsert(rows)
    }
}
