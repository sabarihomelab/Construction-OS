package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface WorkforceDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertWorkers(rows: List<WorkforceWorkerEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertCrews(rows: List<WorkforceCrewEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAssignments(rows: List<WorkforceAssignmentEntity>)

    @Query("DELETE FROM workforce_workers WHERE organization_id = :organizationId")
    suspend fun deleteWorkers(organizationId: String)

    @Query("DELETE FROM workforce_crews WHERE organization_id = :organizationId")
    suspend fun deleteCrews(organizationId: String)

    @Query("DELETE FROM workforce_assignments WHERE project_id = :projectId")
    suspend fun deleteAssignments(projectId: String)

    @Transaction
    suspend fun replaceWorkers(organizationId: String, rows: List<WorkforceWorkerEntity>) {
        deleteWorkers(organizationId)
        upsertWorkers(rows)
    }

    @Transaction
    suspend fun replaceCrews(organizationId: String, rows: List<WorkforceCrewEntity>) {
        deleteCrews(organizationId)
        upsertCrews(rows)
    }

    @Transaction
    suspend fun replaceAssignments(projectId: String, rows: List<WorkforceAssignmentEntity>) {
        deleteAssignments(projectId)
        upsertAssignments(rows)
    }

    @Query(
        """
        SELECT
            a.id AS assignment_id,
            w.id AS worker_id,
            w.worker_number AS worker_number,
            w.display_name AS display_name,
            w.status AS worker_status,
            a.status AS assignment_status,
            w.job_title AS job_title,
            COALESCE(a.trade, w.trade) AS trade,
            a.project_role AS project_role,
            a.crew_id AS crew_id,
            c.name AS crew_name,
            a.engagement_type AS engagement_type,
            a.default_cost_code AS default_cost_code,
            a.start_date AS start_date,
            a.end_date AS end_date
        FROM workforce_assignments a
        INNER JOIN workforce_workers w ON w.id = a.worker_id
        LEFT JOIN workforce_crews c ON c.id = a.crew_id
        WHERE a.project_id = :projectId
          AND (
              :query = '' OR
              LOWER(w.display_name) LIKE '%' || LOWER(:query) || '%' OR
              LOWER(w.worker_number) LIKE '%' || LOWER(:query) || '%' OR
              LOWER(COALESCE(a.trade, w.trade, '')) LIKE '%' || LOWER(:query) || '%' OR
              LOWER(COALESCE(a.project_role, '')) LIKE '%' || LOWER(:query) || '%' OR
              LOWER(COALESCE(c.name, '')) LIKE '%' || LOWER(:query) || '%'
          )
        ORDER BY
            CASE WHEN a.status = 'active' THEN 0 ELSE 1 END,
            w.display_name,
            w.worker_number
        """,
    )
    fun observeProjectWorkers(projectId: String, query: String): Flow<List<WorkforceWorkerDirectoryRow>>

    @Query(
        """
        SELECT
            c.id AS id,
            c.name AS name,
            c.status AS status,
            sw.display_name AS supervisor_name,
            CAST(COUNT(a.id) AS INTEGER) AS assigned_count
        FROM workforce_crews c
        LEFT JOIN workforce_workers sw ON sw.id = c.supervisor_worker_id
        LEFT JOIN workforce_assignments a
            ON a.crew_id = c.id
            AND a.project_id = :projectId
            AND a.status = 'active'
        WHERE c.organization_id = :organizationId
          AND (
              :query = '' OR
              LOWER(c.name) LIKE '%' || LOWER(:query) || '%' OR
              LOWER(COALESCE(sw.display_name, '')) LIKE '%' || LOWER(:query) || '%'
          )
        GROUP BY c.id, c.name, c.status, sw.display_name
        ORDER BY
            CASE WHEN c.status = 'active' THEN 0 ELSE 1 END,
            c.name
        """,
    )
    fun observeCrews(
        organizationId: String,
        projectId: String,
        query: String,
    ): Flow<List<WorkforceCrewDirectoryRow>>
}
