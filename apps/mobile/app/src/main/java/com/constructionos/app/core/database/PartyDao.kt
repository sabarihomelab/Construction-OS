package com.constructionos.app.core.database

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface PartyDao {
    @Query(
        """
        SELECT * FROM parties
        WHERE organization_id = :organizationId
        ORDER BY name, code
        """,
    )
    fun observeParties(organizationId: String): Flow<List<PartyEntity>>

    @Query(
        """
        SELECT * FROM project_party_assignments
        WHERE project_id = :projectId AND active = 1
        ORDER BY role, id
        """,
    )
    fun observeAssignments(projectId: String): Flow<List<ProjectPartyAssignmentEntity>>

    @Upsert
    suspend fun upsertParties(rows: List<PartyEntity>)

    @Upsert
    suspend fun upsertAssignments(rows: List<ProjectPartyAssignmentEntity>)

    @Query("DELETE FROM parties WHERE organization_id = :organizationId")
    suspend fun deleteOrganizationParties(organizationId: String)

    @Query("DELETE FROM project_party_assignments WHERE project_id = :projectId")
    suspend fun deleteProjectAssignments(projectId: String)

    @Transaction
    suspend fun replaceDirectory(
        organizationId: String,
        projectId: String,
        parties: List<PartyEntity>,
        assignments: List<ProjectPartyAssignmentEntity>,
    ) {
        deleteOrganizationParties(organizationId)
        deleteProjectAssignments(projectId)
        if (parties.isNotEmpty()) upsertParties(parties)
        if (assignments.isNotEmpty()) upsertAssignments(assignments)
    }
}
