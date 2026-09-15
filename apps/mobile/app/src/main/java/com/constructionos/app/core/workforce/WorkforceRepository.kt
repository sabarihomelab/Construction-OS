package com.constructionos.app.core.workforce

import com.constructionos.app.core.database.WorkforceAssignmentEntity
import com.constructionos.app.core.database.WorkforceCrewDirectoryRow
import com.constructionos.app.core.database.WorkforceCrewEntity
import com.constructionos.app.core.database.WorkforceDao
import com.constructionos.app.core.database.WorkforceWorkerDirectoryRow
import com.constructionos.app.core.database.WorkforceWorkerEntity
import com.constructionos.app.core.network.WorkforceApi
import kotlinx.coroutines.flow.Flow

class WorkforceRepository(
    private val api: WorkforceApi,
    private val dao: WorkforceDao,
) {
    fun observeProjectWorkers(projectId: String, query: String): Flow<List<WorkforceWorkerDirectoryRow>> =
        dao.observeProjectWorkers(projectId, query.trim())

    fun observeCrews(
        organizationId: String,
        projectId: String,
        query: String,
    ): Flow<List<WorkforceCrewDirectoryRow>> =
        dao.observeCrews(organizationId, projectId, query.trim())

    suspend fun refresh(
        organizationId: String,
        projectId: String,
        canViewWorkers: Boolean,
        canViewCrews: Boolean,
        canViewAssignments: Boolean,
    ): Result<Unit> = runCatching {
        if (canViewWorkers) {
            val workers = api.workers().map { row ->
                WorkforceWorkerEntity(
                    id = row.id,
                    organizationId = row.organizationId,
                    workerNumber = row.workerNumber,
                    displayName = row.preferredName?.takeIf { it.isNotBlank() }
                        ?: listOf(row.firstName, row.lastName)
                            .filter { it.isNotBlank() }
                            .joinToString(" "),
                    jobTitle = row.jobTitle,
                    trade = row.trade,
                    status = row.status,
                    revision = row.revision,
                )
            }
            dao.replaceWorkers(organizationId, workers)
        }

        if (canViewCrews) {
            val crews = api.crews().map { row ->
                WorkforceCrewEntity(
                    id = row.id,
                    organizationId = row.organizationId,
                    name = row.name,
                    supervisorWorkerId = row.supervisorWorkerId,
                    status = row.status,
                    revision = row.revision,
                )
            }
            dao.replaceCrews(organizationId, crews)
        }

        if (canViewAssignments) {
            val assignments = api.assignments(projectId).map { row ->
                WorkforceAssignmentEntity(
                    id = row.id,
                    organizationId = row.organizationId,
                    projectId = row.projectId,
                    workerId = row.workerId,
                    crewId = row.crewId,
                    employerPartyId = row.employerPartyId,
                    engagementType = row.engagementType,
                    status = row.status,
                    projectRole = row.projectRole,
                    trade = row.trade,
                    defaultCostCode = row.defaultCostCode,
                    startDate = row.startDate,
                    endDate = row.endDate,
                    revision = row.revision,
                )
            }
            dao.replaceAssignments(projectId, assignments)
        }
    }
}
