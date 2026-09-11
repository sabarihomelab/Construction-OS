package com.constructionos.app.core.workspace

import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.constructionos.app.core.offline.WorkspaceSyncService
import com.constructionos.app.core.projects.ProjectRepository
import com.constructionos.app.core.projects.ProjectSelectionStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withTimeoutOrNull

class WorkspaceCoordinator(
    private val repository: ProjectRepository,
    private val selectionStore: ProjectSelectionStore,
    private val syncScheduler: WorkspaceSyncScheduler,
    private val syncService: WorkspaceSyncService,
) {
    fun projects(organizationId: String): Flow<List<ProjectEntity>> =
        repository.observeProjects(organizationId)

    suspend fun onAuthenticated() {
        syncScheduler.disableLegacyPeriodicSync()
        if (!syncScheduler.isNetworkAvailable()) {
            syncScheduler.scheduleOnce()
            return
        }

        val completed = withTimeoutOrNull(STARTUP_SYNC_TIMEOUT_MS) {
            runCatching { syncService.syncNow() }.isSuccess
        } == true
        if (!completed) {
            syncScheduler.scheduleOnce()
        }
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

    companion object {
        private const val STARTUP_SYNC_TIMEOUT_MS = 4_000L
    }
}
