package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
abstract class ProjectDao {
    @Query("SELECT * FROM projects WHERE organization_id = :organizationId ORDER BY name, id")
    abstract fun observeForOrganization(organizationId: String): Flow<List<ProjectEntity>>

    @Query("DELETE FROM projects WHERE organization_id = :organizationId")
    protected abstract suspend fun deleteForOrganization(organizationId: String)

    @Upsert
    protected abstract suspend fun upsertAll(projects: List<ProjectEntity>)

    @Transaction
    open suspend fun replaceForOrganization(
        organizationId: String,
        projects: List<ProjectEntity>,
    ) {
        deleteForOrganization(organizationId)
        if (projects.isNotEmpty()) {
            upsertAll(projects)
        }
    }

    @Query("DELETE FROM projects WHERE organization_id = :organizationId")
    abstract suspend fun clearForOrganization(organizationId: String)
}
