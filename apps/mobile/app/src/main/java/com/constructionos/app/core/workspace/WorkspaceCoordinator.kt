package com.constructionos.app.core.workspace

import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.constructionos.app.core.projects.ProjectRepository
import com.constructionos.app.core.projects.ProjectSelectionStore
import kotlinx.coroutines.flow.Flow

class WorkspaceCoordinator(
    private val repository: ProjectRepository,
    private val selectionStore: ProjectSelectionStore,
    private val syncScheduler: WorkspaceSyncScheduler,
) {
    fun projects(organizationId: String): Flow<List<ProjectEntity>> =
        repository.observeProjects(organizationId)

    fun onAuthenticated(context: SessionContextResponse) {
        syncScheduler.schedule()
    }

    fun selectedProjectId(organizationId: String): String? =
        selectionStore.selectedProjectId(organizationId)

    fun selectProject(organizationId: String, projectId: String) {
        selectionStore.select(organizationId, projectId)
    }

    fun clearProjectSelection(organizationId: String) {
        selectionStore.clear(organizationId)
    }

    suspend fun logout(organizationId: String) {
        syncScheduler.cancel()
        selectionStore.clear(organizationId)
        repository.clear(organizationId)
    }
}
