package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface WbsDao {
    @Query(
        """
        SELECT * FROM wbs_codes
        WHERE project_id = :projectId
        ORDER BY tree_order
        """,
    )
    fun observeTree(projectId: String): Flow<List<WbsEntity>>

    @Query(
        """
        SELECT * FROM wbs_codes
        WHERE project_id = :projectId
          AND (
            code LIKE '%' || :query || '%' COLLATE NOCASE OR
            name LIKE '%' || :query || '%' COLLATE NOCASE OR
            path_codes LIKE '%' || :query || '%' COLLATE NOCASE
          )
        ORDER BY tree_order
        """,
    )
    fun search(projectId: String, query: String): Flow<List<WbsEntity>>

    @Upsert
    suspend fun upsert(rows: List<WbsEntity>)

    @Query("DELETE FROM wbs_codes WHERE project_id = :projectId")
    suspend fun deleteProject(projectId: String)

    @Transaction
    suspend fun replaceProject(projectId: String, rows: List<WbsEntity>) {
        deleteProject(projectId)
        if (rows.isNotEmpty()) upsert(rows)
    }
}
