package com.constructionos.app.core.offline

import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.projects.ProjectRepository

class WorkspaceSyncService(
    private val api: ConstructionOsApi,
    private val deviceRegistrar: DeviceRegistrar,
    private val projectRepository: ProjectRepository,
) {
    suspend fun syncNow() {
        val context = api.sessionContext()
        deviceRegistrar.register()
        projectRepository.refresh(context.organizationId)
    }
}
